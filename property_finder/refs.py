"""Reference resolvers, link builders and the site's vocabularies for
/property-finder/*.

ONE param per input (tripadvisor QueryOrIdField convention): every
`<thing>` param accepts a bare id OR any propertyfinder.<cc> link for the
same record, and a link also fixes the `country` (the TLD). Resolvers raise
ValueError with a user-facing message (RefField turns it into a 400) and
return small dicts the api layer finishes (a location name or slug still
needs the site's own autocomplete to become an id).

Record identifiers on the site (captured 2026-11-07):
  * property   numeric id; link /en/plp/<buy|rent|...>/<slug>-<id>.html,
               short link /to/<id>/en
  * agent      numeric id; link /en/agent/<slug>-<id>
  * brokerage  numeric id; link /en/broker/<slug>-<id> (the partner app also
               prints /en/broker/<slug>-<id>-<id>)
  * project    uuid; slug "<developer-slug>/<project-slug>"; link
               /en/new-projects/<developer-slug>/<project-slug>
  * developer  uuid; slug; link /en/new-projects/dev/<slug>
  * location   numeric id (Dubai 1, Dubai Marina 50, Abu Dhabi 6); links
               /en/search?l=<id>, the SEO listing pages
               /en/buy/<city>/properties-for-sale-<slug>.html,
               /en/transactions/<sold|rented>/<city>/<slug>,
               /en/area-insights/<city>/<slug>; anything else is a name

The vocabularies (property types, amenities, languages, sorts) are the
site's own filter catalogs, read from the search page's
filterCapabilities.catalog and the find-agent page's options on 2026-11-07.
"""
import re
from urllib.parse import parse_qs, unquote, urlparse

# ---- countries ------------------------------------------------------------------

# country code -> (host TLD, currency). Every storefront runs the same apps
# and APIs; "ae" is the default and by far the largest.
COUNTRIES = {
    "ae": ("ae", "AED"),
    "sa": ("sa", "SAR"),
    "qa": ("qa", "QAR"),
    "bh": ("bh", "BHD"),
    "eg": ("eg", "EGP"),
}
DEFAULT_COUNTRY = "ae"
GROWTH_HOST = "https://growth.propertyfinder.com"


def site(country=DEFAULT_COUNTRY):
    tld = COUNTRIES.get(country or DEFAULT_COUNTRY, COUNTRIES[DEFAULT_COUNTRY])[0]
    return f"https://www.propertyfinder.{tld}"


def currency(country=DEFAULT_COUNTRY):
    return COUNTRIES.get(country or DEFAULT_COUNTRY, COUNTRIES[DEFAULT_COUNTRY])[1]


# ---- vocabularies ---------------------------------------------------------------

# public value -> the site's category_id
CATEGORIES = {
    "buy": 1,
    "rent": 2,
    "commercial-buy": 3,
    "commercial-rent": 4,
    "new-projects": 5,
}
# the listing categories alone (new projects have their own /projects/* routes);
# a literal, not a comprehension, so the publish tooling's AST reader sees it
LISTING_CATEGORIES = {
    "buy": 1,
    "rent": 2,
    "commercial-buy": 3,
    "commercial-rent": 4,
}
CATEGORY_NAMES = {v: k for k, v in CATEGORIES.items()}
CATEGORY_LABELS = {1: "Residential for Sale", 2: "Residential for Rent",
                   3: "Commercial for Sale", 4: "Commercial for Rent", 5: "New Projects"}

# public slug -> property_type_id (the search page's filter[property_type_id])
PROPERTY_TYPES = {
    "apartment": 1, "villa": 35, "townhouse": 22, "penthouse": 20, "compound": 42,
    "duplex": 24, "full-floor": 18, "half-floor": 29, "whole-building": 10, "land": 5,
    "bulk-sale-unit": 30, "bungalow": 31, "hotel-apartment": 45, "bulk-rent-unit": 34,
    "office": 4, "retail": 27, "warehouse": 13, "shop": 21, "show-room": 12, "factory": 44,
    "labor-camp": 11, "staff-accommodation": 43, "business-centre": 48, "co-working": 49,
    "farm": 50,
}
PROPERTY_TYPE_NAMES = {
    1: "Apartment", 35: "Villa", 22: "Townhouse", 20: "Penthouse", 42: "Compound", 24: "Duplex",
    18: "Full Floor", 29: "Half Floor", 10: "Whole Building", 5: "Land", 30: "Bulk Sale Unit",
    31: "Bungalow", 45: "Hotel & Hotel Apartment", 34: "Bulk Rent Unit", 4: "Office Space",
    27: "Retail", 13: "Warehouse", 21: "Shop", 12: "Show Room", 44: "Factory", 11: "Labor Camp",
    43: "Staff Accommodation", 48: "Business Centre", 49: "Co-working space", 50: "Farm",
}

# the new-projects API speaks property type words, not ids
PROJECT_PROPERTY_TYPES = ("apartment", "villa", "townhouse", "penthouse", "duplex", "land")

# bedrooms: "studio" = 0, "7+" = 8 (the site's own bucket for seven or more)
BEDROOMS = {"studio": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "7+": 8}
BATHROOMS = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "7+": 8}

# amenity code -> label (filter[amenities]); the API filters by code
AMENITIES = {
    "AC": "Central A/C", "MR": "Maids Room", "BA": "Balcony", "SP": "Shared Pool", "SS": "Shared Spa",
    "SY": "Shared Gym", "CS": "Concierge Service", "CP": "Covered Parking", "VW": "View of Water",
    "BL": "View of Landmark", "PA": "Pets Allowed", "ST": "Study", "PG": "Private Garden",
    "PP": "Private Pool", "PY": "Private Gym", "PJ": "Private Jacuzzi", "BW": "Built in Wardrobes",
    "WC": "Walk-in Closet", "BK": "Built in Kitchen Appliances", "MS": "Maid Service",
    "PR": "Children's Play Area", "CO": "Children's Pool", "BR": "Barbecue Area",
}
# the same amenities by a slug of their label, so callers may write either
AMENITY_SLUGS = {re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"): code for code, label in AMENITIES.items()}

FURNISHED = {"furnished": 1, "unfurnished": 2, "partly-furnished": 3}
FURNISHED_NAMES = {"YES": "furnished", "NO": "unfurnished", "PARTLY": "partly-furnished"}
COMPLETION_STATUS = ("completed", "off_plan")
RENT_PERIODS = ("yearly", "monthly", "weekly", "daily")
VIRTUAL_VIEWINGS = {"floor-plan": "floor_plan", "360-tours": "360_tours", "video": "video", "live": "live"}
DEAL_BADGES = {"great-value": "great_value", "high-demand": "high_demand", "price-drop": "price_drop"}

# listed_within is sent in SECONDS; the public param is days
LISTED_WITHIN_DAYS = (1, 7, 15, 30, 90)

# sorting.sort integer enum of property-api/web/v2 (the site's ob= codes in
# the same order: mr nd pa pd ba bd da dd)
SEARCH_SORTS = {
    "featured": 0, "newest": 1, "price-low": 2, "price-high": 3,
    "beds-least": 4, "beds-most": 5, "delivery-earliest": 6, "delivery-latest": 7,
}

# pf-b2c-customer/agents `sort` (its `ranking` sort returned the very same order
# as `-trusted_score` with and without filters on 2026-11-10, so it is not offered)
AGENT_SORTS = {"featured": "-trusted_score", "listings-most": "-total_properties",
               "listings-least": "total_properties", "sale-listings": "-total_sales_properties",
               "rent-listings": "-total_rental_properties"}
# pf-b2c-customer/brokerages `sort` (its `name` sort is not alphabetical in either
# direction — SOLACE HOMES, NEXT HERITAGE, THE AJS … on 2026-11-10 — so it is not offered)
COMPANY_SORTS = {"featured": None, "listings-most": "-total_properties"}

# agent languages: label -> id (find-agent page options, 64 rows)
LANGUAGES = {
    "afrikaans": 35, "albanian": 44, "amharic": 45, "arabic": 2, "azerbaijani": 26, "bahasa-melayu": 41,
    "baluchi": 46, "belarusian": 47, "bengali": 14, "berber": 48, "bulgarian": 32, "cantonese": 40,
    "catalan": 49, "croatian": 9, "czech": 50, "danish": 37, "dutch": 24, "english": 1, "finnish": 51,
    "french": 3, "german": 5, "greek": 12, "gujarati": 29, "hindi": 7, "hungarian": 25, "italian": 22,
    "japanese": 52, "javanese": 53, "kannada": 54, "kazakh": 20, "korean": 55, "kurdi": 56, "kyrgyz": 18,
    "latvian": 57, "malay": 58, "malayalam": 16, "mandarin": 21, "memon": 28, "norwegian": 39, "pashto": 43,
    "persian": 11, "farsi": 11, "polish": 4, "portuguese": 23, "punjabi": 36, "romanian": 34, "russian": 6,
    "serbian": 38, "shona": 42, "sinhalese": 59, "slovak": 60, "slovene": 61, "somali": 62, "spanish": 10,
    "sudanese": 63, "swahili": 64, "swedish": 33, "tagalog": 13, "tamil": 15, "telugu": 65, "thai": 66,
    "turkish": 27, "ukrainian": 30, "urdu": 8, "uzbek": 19,
}

LOCATION_TYPES = {"city": "CITY", "community": "COMMUNITY", "subcommunity": "SUBCOMMUNITY", "tower": "TOWER"}

# transactions
TRANSACTION_TYPES = {"sold": 1, "rented": 2}
TRANSACTION_PERIODS = ("1w", "1m", "3m", "6m", "ytd", "1y", "3y", "5y", "10y")
TRANSACTION_SORTS = {"date-desc": "td", "date-asc": "ta", "price-asc": "pa", "price-desc": "pd"}
CONTRACT_STATUS = ("new", "renewed")
SOLD_BY = ("developer", "individual")

# project construction phases (bilbo filter.construction_phase)
PROJECT_PHASES = ("completed", "under_construction", "not_started")

REVIEW_SORTS = ("newest", "oldest", "rating_lowest", "rating_highest")


# ---- link parsing ---------------------------------------------------------------

_HOST_RE = re.compile(r"^(?:www\.)?propertyfinder\.(ae|sa|qa|bh|eg)$", re.I)
_ID_TAIL_RE = re.compile(r"-(\d+)$")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", re.I)


def _is_link(value):
    return value.startswith(("http://", "https://", "//")) or value.lower().startswith("www.propertyfinder.")


def _parse_link(value):
    """A propertyfinder link -> (country, path segments, query dict). Raises
    ValueError for another site."""
    url = value if value.startswith(("http://", "https://")) else "https:" + (value if value.startswith("//") else "//" + value)
    parts = urlparse(url)
    match = _HOST_RE.match((parts.hostname or "").lower())
    if not match:
        raise ValueError("Must be a propertyfinder.ae (.sa/.qa/.bh/.eg) link.")
    segments = [unquote(s) for s in parts.path.split("/") if s]
    if segments and segments[0] in ("en", "ar"):
        segments = segments[1:]
    return match.group(1).lower(), segments, parse_qs(parts.query)


def _ref(**kw):
    return {k: v for k, v in kw.items()}


def _numeric(value):
    return value.isdigit()


def _id_from_slug(segment):
    """'nathan-blake-264476' / 'barnes-international-realty-v2-4338-4338' -> 264476 / 4338."""
    segment = segment.rsplit(".html", 1)[0]
    if segment.isdigit():
        return int(segment)
    match = _ID_TAIL_RE.search(segment)
    return int(match.group(1)) if match else None


# ---- resolvers ----------------------------------------------------------------------

def resolve_property(value):
    """Listing id or a listing link -> {"id", "country"} (country None for a bare id)."""
    value = (value or "").strip()
    if _numeric(value):
        return _ref(id=int(value), country=None)
    if _is_link(value):
        country, segments, _ = _parse_link(value)
        # /plp/<category>/<slug>-<id>.html  |  /to/<id>/en
        if len(segments) >= 2 and segments[0] == "to" and segments[1].isdigit():
            return _ref(id=int(segments[1]), country=country)
        if len(segments) >= 3 and segments[0] == "plp":
            pid = _id_from_slug(segments[-1])
            if pid:
                return _ref(id=pid, country=country)
        raise ValueError("Must be a propertyfinder listing link (/en/plp/buy/<slug>-<id>.html).")
    raise ValueError("Must be a listing id (164588946) or a propertyfinder listing link.")


def resolve_agent(value):
    """Agent id or /en/agent/<slug>-<id> link -> {"id", "country"}."""
    value = (value or "").strip()
    if _numeric(value):
        return _ref(id=int(value), country=None)
    if _is_link(value):
        country, segments, _ = _parse_link(value)
        if len(segments) >= 2 and segments[0] == "agent":
            aid = _id_from_slug(segments[1])
            if aid:
                return _ref(id=aid, country=country)
        raise ValueError("Must be a propertyfinder agent link (/en/agent/<name>-<id>).")
    raise ValueError("Must be an agent id (264476) or a propertyfinder agent link.")


def resolve_company(value):
    """Brokerage id or /en/broker/<slug>-<id> link -> {"id", "country"}."""
    value = (value or "").strip()
    if _numeric(value):
        return _ref(id=int(value), country=None)
    if _is_link(value):
        country, segments, _ = _parse_link(value)
        if len(segments) >= 2 and segments[0] == "broker":
            cid = _id_from_slug(segments[1])
            if cid:
                return _ref(id=cid, country=country)
        raise ValueError("Must be a propertyfinder company link (/en/broker/<name>-<id>).")
    raise ValueError("Must be a company id (4338) or a propertyfinder broker link.")


def resolve_project(value):
    """Project uuid, '<developer>/<project>' slug or /en/new-projects/<dev>/<proj>
    link -> {"uuid" | "slug", "country"}."""
    value = (value or "").strip().strip("/")
    if _UUID_RE.match(value):
        return _ref(uuid=value.lower(), slug=None, country=None)
    if _is_link(value):
        country, segments, _ = _parse_link(value)
        if len(segments) >= 3 and segments[0] == "new-projects" and segments[1] != "dev":
            return _ref(uuid=None, slug=f"{segments[1]}/{segments[2]}".lower(), country=country)
        raise ValueError("Must be a propertyfinder project link (/en/new-projects/<developer>/<project>).")
    parts = value.split("/")
    if len(parts) == 2 and all(_SLUG_RE.match(p) for p in parts):
        return _ref(uuid=None, slug=value.lower(), country=None)
    raise ValueError("Must be a project uuid, a '<developer-slug>/<project-slug>' pair "
                     "(emaar-properties/valia-tower) or a propertyfinder project link.")


def resolve_developer(value):
    """Developer uuid, slug or /en/new-projects/dev/<slug> link -> {"uuid" | "slug", "country"}."""
    value = (value or "").strip().strip("/")
    if _UUID_RE.match(value):
        return _ref(uuid=value.lower(), slug=None, country=None)
    if _is_link(value):
        country, segments, _ = _parse_link(value)
        if len(segments) >= 3 and segments[0] == "new-projects" and segments[1] == "dev":
            return _ref(uuid=None, slug=segments[2].lower(), country=country)
        raise ValueError("Must be a propertyfinder developer link (/en/new-projects/dev/<slug>).")
    if _SLUG_RE.match(value) and not value.isdigit():
        return _ref(uuid=None, slug=value.lower(), country=None)
    raise ValueError("Must be a developer uuid, slug (emaar-properties) or a propertyfinder developer link.")


# /en/buy/dubai/<what>-for-sale[-<place>].html: properties-, villas-, apartments-,
# 1-bedroom-apartments- … all name the place after for-sale / for-rent
_SEO_SLUG_RE = re.compile(r"^[a-z0-9-]*?-?for-(?:sale|rent)(?:-(.+))?\.html$")
# /en/transactions/<sold|rented>/<city>/<what>-<place>: the similar-search links put
# bedrooms and a property type before the place (1-bedroom-apartments-downtown-dubai)
_TX_PREFIX_RE = re.compile(
    r"^(?:(?:studio|\d+-bedrooms?)-)?(?:hotel-)?(?:apartments|villas|townhouses|penthouses|duplexes|compounds|"
    r"bungalows|lands|plots|offices|shops|warehouses|full-floors|half-floors|whole-buildings)-")


def resolve_location(value):
    """Location id(s), a propertyfinder link or a place name ->
    {"ids": [int] | None, "slug": str | None, "city_slug": str | None,
    "query": str | None, "country"}. Only one of ids / slug / query is set;
    the api layer turns a slug or a query into an id through the site's own
    autocomplete."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")

    def slug_ref(country, slug, city=None):
        return _ref(ids=None, slug=slug.rsplit(".html", 1)[0].lower(), city_slug=(city or "").lower() or None,
                    query=None, country=country)

    if _is_link(value):
        country, segments, query = _parse_link(value)
        ids = []
        for raw in query.get("l", []) + query.get("l[]", []):
            for part in raw.split(","):
                if part.strip().isdigit():
                    ids.append(int(part.strip()))
        if ids:
            return _ref(ids=ids, slug=None, city_slug=None, query=None, country=country)
        if len(segments) >= 3 and segments[0] in ("area-insights", "building-reviews"):
            return slug_ref(country, segments[2], segments[1])
        if len(segments) >= 4 and segments[0] == "transactions":
            ref = slug_ref(country, _TX_PREFIX_RE.sub("", segments[3]), segments[2])
            # the link's own deal type, for transactions/search when `type` is not given
            ref["deal"] = segments[1] if segments[1] in ("sold", "rented") else None
            return ref
        if len(segments) >= 3 and segments[0] in ("buy", "rent", "commercial-buy", "commercial-rent"):
            match = _SEO_SLUG_RE.match(segments[2])
            if match and match.group(1):
                return slug_ref(country, match.group(1), segments[1])
            # /en/buy/dubai/properties-for-sale.html -> the city itself
            return slug_ref(country, segments[1], segments[1])
        if len(segments) >= 2 and segments[0] in ("area-insights", "transactions"):
            return slug_ref(country, segments[-1], segments[-1])
        # a new-projects area page: /en/new-projects/lp/<city>/<area> (or /lp/<city>)
        if len(segments) >= 3 and segments[0] == "new-projects" and segments[1] == "lp":
            return slug_ref(country, segments[-1], segments[2])
        raise ValueError("Must be a propertyfinder search page (/en/search?… or /en/buy/…), transactions, "
                         "area-insights or new-projects area link that names a location.")
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if parts and all(p.isdigit() for p in parts):
        return _ref(ids=[int(p) for p in parts][:10], slug=None, city_slug=None, query=None, country=None)
    if len(value) > 120:
        raise ValueError("Location name too long (120 characters max).")
    return _ref(ids=None, slug=None, city_slug=None, query=value, country=None)


# ---- link builders ---------------------------------------------------------------------

def agent_link(country, slug, agent_id):
    slug = f"{slug}-{agent_id}" if slug else str(agent_id)
    return f"{site(country)}/en/agent/{slug}"


def company_link(country, slug, company_id):
    """/en/broker/<slug>-<id>; a bare id serves the page too (/en/broker/4338)."""
    if not slug:
        return f"{site(country)}/en/broker/{company_id}"
    if not slug.endswith(f"-{company_id}"):
        slug = f"{slug}-{company_id}"
    return f"{site(country)}/en/broker/{slug}"


def property_link(country, property_id, share_url=None):
    if share_url:
        return share_url
    return f"{site(country)}/to/{property_id}/en"


def project_link(country, slug):
    return f"{site(country)}/en/new-projects/{slug}" if slug else None


def developer_link(country, slug):
    return f"{site(country)}/en/new-projects/dev/{slug}" if slug else None


def absolute(country, path):
    """A site-relative path ('/en/area-insights/dubai/dubai-marina') -> absolute link."""
    if not path:
        return None
    if path.startswith("http"):
        return path
    return site(country) + (path if path.startswith("/") else "/" + path)


def search_link(country, category_id, location_ids=None):
    query = f"c={category_id}"
    for lid in location_ids or []:
        query += f"&l={lid}"
    return f"{site(country)}/en/search?{query}"


def transactions_link(country, offering_type_id, city_slug, slug=None):
    kind = "sold" if offering_type_id == 1 else "rented"
    path = f"/en/transactions/{kind}/{city_slug}" if city_slug else f"/en/transactions/{kind}"
    if slug and slug != city_slug:
        path += f"/{slug}"
    return site(country) + path
