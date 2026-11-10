"""Property Finder transport: plain curl_cffi with browser-impersonated TLS.
No browser, no cookies kept. Egress: the pod's own IP by default
(config.property_finder_proxy(), knob PROPERTY_FINDER_EXIT); a block moves
every NEW session to a sticky datacenter exit
(config.property_finder_fallback_proxy()) for PROPERTY_FINDER_BLOCK_HOLD_S
seconds, and the blocked thread drops its session at once so the retry
rides a fresh exit. Pod probe 2026-11-07: table in config.py's property
finder block.

Only the TLS fingerprint matters: a plain python UA answers AWS WAF 403 on
every host, curl_cffi chrome (and safari17_0 / edge101) pass everywhere
with no cookies (2026-11-07, direct + datacenter + residential exits).
The five storefronts (.ae .sa .qa .bh .eg) share the same apps and APIs.

Upstream surfaces (all GET, all cookie-free, `country` picks the host):

  * SEARCH       /property-api/web/v2/en/search  — listing cards, dotted
                 `filters.*` params (lists REPEATED, a CSV is 0 rows),
                 `sorting.sort` integer, `pagination.page/limit` (limit <= 60,
                 61 is 400). Also serves an agent's / brokerage's listings
                 (filters.agent_id / filters.client_id) and one card by id
                 (filters.listing_ids).
  * PROPERTY     /to/<id>/en -> 30x to the PLP page /en/plp/<cat>/<slug>-<id>.html
                 (~450 KB Next.js page, record in __NEXT_DATA__). An unknown
                 id is a real 404.
  * PRICE TRENDS /api/pwa/tower-insights/price-trends?locale=en&id=&categoryId=
                 &bedrooms=&propertyTypeId=&country= (every param required).
  * AGENTS       /pf-b2c-customer/en/agents (bare JSON list; totals in the
                 x-total / x-total-pages / x-page headers; per_page <= 100)
                 and /pf-b2c-customer/en/agents/<id> (404 for an unknown id).
  * BROKERAGES   /pf-b2c-customer/en/brokerages (same shape) and
                 /pf-b2c-customer/en/brokerages/<id>.
  * PROJECTS     /property-api/bilbo/search/projects (`filter.*`, limit <= 100,
                 `filter.location_ids` singular) and /property-api/bilbo/projects/<uuid>.
  * DEVELOPERS   /property-api/bilbo/developers (`filter.slug` / `filter.ids`;
                 `filter.name` is ignored) and /property-api/bilbo/developers/<uuid>.
  * TRANSACTIONS /b2c-transactions/api/v1/en/transactions/<locationId>
                 (DLD, Dubai only; size <= 50; 400 past 500 rows per query).
  * LOCATIONS    /b2c-location/api/v2/en/locations (filters.name / filters.ids
                 repeated / filters.types / filters.category_id).
  * AREA PAGE    /en/area-insights/<city>/<slug> (~2.4 MB Next.js page).
  * REVIEWS      https://growth.propertyfinder.com/bridge/public/location/<id>
                 ?locale=en&include=reviews&reviewsPage=&reviewsPageSize=&reviewsSort=
                 (X-PF-Country-Code header names the storefront).

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  PropertyFinderUpstreamError  transport failure / 5xx / odd payload  — retryable
  PropertyFinderBlocked        403 / 429 / WAF challenge page          — retryable
  PropertyFinderBadRequest     upstream 400                            — never retried
  PropertyFinderNotFound       404 / unknown id                        — never retried
"""
import os
import sys
import threading
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from property_finder import refs

IMPERSONATE = "chrome"
PAGE_TIMEOUT = 45     # the area-insights page is ~2.4 MB
API_TIMEOUT = 30

SEARCH_PATH = "/property-api/web/v2/en/search"
PRICE_TRENDS_PATH = "/api/pwa/tower-insights/price-trends"
AGENTS_PATH = "/pf-b2c-customer/en/agents"
BROKERAGES_PATH = "/pf-b2c-customer/en/brokerages"
PROJECTS_SEARCH_PATH = "/property-api/bilbo/search/projects"
PROJECTS_PATH = "/property-api/bilbo/projects"
DEVELOPERS_PATH = "/property-api/bilbo/developers"
TRANSACTIONS_PATH = "/b2c-transactions/api/v1/en/transactions"
LOCATIONS_PATH = "/b2c-location/api/v2/en/locations"
REVIEWS_PATH = "/bridge/public/location"

_CHALLENGE_MARKERS = ("awswaf", "challenge-container", "Request blocked", "errors.edgesuite.net",
                      "<title>403 Forbidden", "cf-chl")


class PropertyFinderUpstreamError(UpstreamError):
    """Transport failure, 5xx or an unexpected payload — retryable."""


class PropertyFinderBlocked(PropertyFinderUpstreamError, Blocked):
    """403 / 429 or a WAF challenge where JSON / a page was expected — retryable."""


class PropertyFinderBadRequest(BadRequest):
    """Upstream 400 — never retried."""


class PropertyFinderNotFound(NotFound):
    """Listing / agent / brokerage / project / developer / location does not exist — never retried."""


# ---- sessions --------------------------------------------------------------------
# One session per cheroot worker thread (a curl handle is not thread-safe).
# Process-wide: after a block on the default tier every new session rides
# the fallback tier until _fallback_until.
_local = threading.local()
_fallback_until = 0.0
_fallback_lock = threading.Lock()


def _proxy():
    proxy = config.property_finder_proxy()
    if proxy is None and time.time() < _fallback_until:
        proxy = config.property_finder_fallback_proxy()
    return proxy


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        proxy = _proxy()
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        sess.headers["accept-language"] = egress.accept_language(proxy)
        _local.session = sess
    # every surface answers a cookie-less request; nothing is kept
    try:
        sess.cookies.clear()
    except Exception:
        pass
    return sess


def _drop_session(blocked=False):
    """Close the thread's session (fresh exit next time); a block on the
    default tier also starts the fallback hold for every thread."""
    global _fallback_until
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass
    if blocked and config.property_finder_proxy() is None:
        with _fallback_lock:
            _fallback_until = time.time() + config.PROPERTY_FINDER_BLOCK_HOLD_S


def _retrying(fn):
    """Run fn() under the shared retry policy (retryable errors only;
    NotFound / BadRequest surface immediately)."""
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn()
        except PropertyFinderBlocked as e:
            last = e
            _drop_session(blocked=True)
        except PropertyFinderUpstreamError as e:
            last = e
            _drop_session()
        if attempt < config.MAX_RETRIES:
            time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


# ---- requests ----------------------------------------------------------------------

def _url(country, path, params=None, host=None):
    """Build the URL with repeated params (`[("filters.locations_ids", 50),
    ("filters.locations_ids", 86)]` or {"k": [1, 2]}); None values are dropped."""
    base = (host or refs.site(country)) + path
    if not params:
        return base
    items = params.items() if isinstance(params, dict) else params
    clean = []
    for key, value in items:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            clean += [(key, v) for v in value if v is not None]
        elif isinstance(value, bool):
            clean.append((key, "true" if value else "false"))
        else:
            clean.append((key, value))
    return base + ("?" + urlencode(clean, doseq=True) if clean else "")


def _headers(country, json_expected):
    headers = {
        "accept": "application/json, text/plain, */*" if json_expected else
                  "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "referer": refs.site(country) + "/en/",
    }
    if json_expected:
        headers["x-pf-country-code"] = (country or refs.DEFAULT_COUNTRY).upper()
    return headers


def _classify(resp, label):
    """Map an HTTP response to the error taxonomy; return the body text."""
    status = resp.status_code
    if status in (404, 204):   # price trends answer 204 for an unknown location
        raise PropertyFinderNotFound(f"{label} not found")
    if status in (400, 422):
        raise PropertyFinderBadRequest(_upstream_message(resp))
    if status in (401, 403, 429):
        raise PropertyFinderBlocked(f"HTTP {status} for {label}")
    if status in (301, 302, 303, 307, 308):
        raise PropertyFinderNotFound(f"{label} not found")
    if status != 200:
        raise PropertyFinderUpstreamError(f"HTTP {status} for {label}")
    text = resp.text
    head = text[:3000]
    if any(marker in head for marker in _CHALLENGE_MARKERS):
        raise PropertyFinderBlocked(f"challenge page for {label}")
    return text


def _upstream_message(resp):
    try:
        body = resp.json()
    except Exception:
        return resp.text[:200]
    if isinstance(body, dict):
        for key in ("message", "error", "detail", "title"):
            if isinstance(body.get(key), str):
                return body[key][:300]
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return str(first.get("detail") or first.get("message") or first)[:300]
            return str(first)[:300]
    return resp.text[:200]


def get_json(country, path, params=None, label="request", host=None):
    """GET a JSON surface -> (payload, response headers)."""
    url = _url(country, path, params, host)

    def once():
        try:
            resp = _session().get(url, headers=_headers(country, True), timeout=API_TIMEOUT)
        except Exception as e:
            raise PropertyFinderUpstreamError(f"request failed: {type(e).__name__}: {e}")
        text = _classify(resp, label)
        try:
            payload = resp.json()
        except Exception:
            raise PropertyFinderBlocked(f"non-JSON answer for {label}: {text[:120]!r}")
        return payload, dict(resp.headers)
    return _retrying(once)


def get_page(country, path, label="page", params=None, follow=True):
    """GET a server-rendered page -> HTML text."""
    url = _url(country, path, params)

    def once():
        try:
            resp = _session().get(url, headers=_headers(country, False), timeout=PAGE_TIMEOUT,
                                  allow_redirects=follow)
        except Exception as e:
            raise PropertyFinderUpstreamError(f"request failed: {type(e).__name__}: {e}")
        text = _classify(resp, label)
        if "__NEXT_DATA__" not in text:
            if "<title>" in text[:5000] and ("not found" in text[:5000].lower() or "404" in text[:5000]):
                raise PropertyFinderNotFound(f"{label} not found")
            raise PropertyFinderUpstreamError(f"no __NEXT_DATA__ in {label} ({len(text)} bytes)")
        return text
    return _retrying(once)


# ---- surfaces -------------------------------------------------------------------------

def fetch_search(country, params):
    """property-api/web/v2 search -> {"listings": [...], "meta": {...}}."""
    payload, _ = get_json(country, SEARCH_PATH, params, "search")
    if not isinstance(payload, dict) or "listings" not in payload:
        raise PropertyFinderUpstreamError("unexpected search payload shape")
    return payload


def fetch_property_page(country, property_id):
    """The listing's PLP page HTML (through the site's /to/<id>/en short link)."""
    return get_page(country, f"/to/{property_id}/en", f"listing {property_id}")


def fetch_price_trends(country, location_id, category_id, bedrooms, property_type_id):
    params = {"locale": "en", "id": location_id, "categoryId": category_id, "bedrooms": bedrooms,
              "propertyTypeId": property_type_id, "country": country}
    payload, _ = get_json(country, PRICE_TRENDS_PATH, params, f"price trends for location {location_id}")
    return payload


def _list_with_totals(country, path, params, label):
    payload, headers = get_json(country, path, params, label)
    if not isinstance(payload, list):
        raise PropertyFinderUpstreamError(f"unexpected {label} payload shape")
    lower = {k.lower(): v for k, v in headers.items()}

    def header_int(name):
        try:
            return int(lower.get(name))
        except (TypeError, ValueError):
            return None
    return payload, {"total": header_int("x-total"), "total_pages": header_int("x-total-pages"),
                     "page": header_int("x-page")}


def fetch_agents(country, params):
    """pf-b2c-customer agents -> (rows, {"total", "total_pages", "page"})."""
    return _list_with_totals(country, AGENTS_PATH, params, "agents")


def fetch_agent(country, agent_id):
    payload, _ = get_json(country, f"{AGENTS_PATH}/{agent_id}", None, f"agent {agent_id}")
    if not isinstance(payload, dict) or not payload.get("id"):
        raise PropertyFinderNotFound(f"agent {agent_id} not found")
    return payload


def fetch_brokerages(country, params):
    return _list_with_totals(country, BROKERAGES_PATH, params, "brokerages")


def fetch_brokerage(country, company_id):
    payload, _ = get_json(country, f"{BROKERAGES_PATH}/{company_id}", None, f"company {company_id}")
    if not isinstance(payload, dict) or not payload.get("id"):
        raise PropertyFinderNotFound(f"company {company_id} not found")
    return payload


def fetch_projects(country, params):
    """bilbo project search -> the full payload ({"data": {"projects": [...]}, "meta": ...})."""
    payload, _ = get_json(country, PROJECTS_SEARCH_PATH, params, "projects")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise PropertyFinderUpstreamError("unexpected projects payload shape")
    return payload


def fetch_project(country, uuid):
    payload, _ = get_json(country, f"{PROJECTS_PATH}/{uuid}", None, f"project {uuid}")
    project = (payload.get("data") or {}).get("project") if isinstance(payload, dict) else None
    if not project:
        raise PropertyFinderNotFound(f"project {uuid} not found")
    return project


def fetch_developers(country, params):
    payload, _ = get_json(country, DEVELOPERS_PATH, params, "developers")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise PropertyFinderUpstreamError("unexpected developers payload shape")
    return payload


def fetch_developer(country, uuid):
    payload, _ = get_json(country, f"{DEVELOPERS_PATH}/{uuid}", None, f"developer {uuid}")
    developer = (payload.get("data") or {}).get("developer") if isinstance(payload, dict) else None
    if not developer:
        raise PropertyFinderNotFound(f"developer {uuid} not found")
    return developer


def fetch_transactions(country, location_id, params):
    payload, _ = get_json(country, f"{TRANSACTIONS_PATH}/{location_id}", params,
                          f"transactions for location {location_id}")
    attributes = (payload.get("data") or {}).get("attributes") if isinstance(payload, dict) else None
    if not isinstance(attributes, dict):
        raise PropertyFinderUpstreamError("unexpected transactions payload shape")
    return attributes


def fetch_locations(country, params):
    payload, _ = get_json(country, LOCATIONS_PATH, params, "locations")
    if not isinstance(payload, dict) or "items" not in payload:
        raise PropertyFinderUpstreamError("unexpected locations payload shape")
    return payload


def fetch_area_page(country, insights_path):
    """The area-insights page HTML for a site-relative insights path."""
    return get_page(country, insights_path, f"area {insights_path}")


def fetch_reviews(country, location_id, params):
    payload, _ = get_json(country, f"{REVIEWS_PATH}/{location_id}", params,
                          f"reviews for location {location_id}", host=refs.GROWTH_HOST)
    if not isinstance(payload, dict) or "reviews" not in payload:
        raise PropertyFinderUpstreamError("unexpected reviews payload shape")
    return payload
