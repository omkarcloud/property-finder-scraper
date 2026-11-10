"""The /property-finder/* endpoint functions (route_glue's route_table calls
them with the schema's loaded kwargs).

Caching lives here (cache.cached_call, keyed on the validated params).
Reference lookups are cached on their own so a name, a slug and an id for
the same place share the work: a location name / slug resolves through the
site's autocomplete once a week (`property_finder.location_lookup`), a
project or developer slug through the bilbo filter once a day, and the
960-row developer directory is fetched once a day (10 upstream pages) and
searched locally. A record endpoint keyed on an id caches the parsed record
under the id alone, so a link and a bare id for the same record share one
row (and one upstream fetch).
"""
import math

import config
from cache import cached_call
from property_finder import cache_config as ttl
from property_finder import parsers, refs
from property_finder.fetch import (PropertyFinderNotFound, fetch_agent, fetch_agents, fetch_area_page,
                                   fetch_brokerage, fetch_brokerages, fetch_developer, fetch_developers,
                                   fetch_locations, fetch_price_trends, fetch_project, fetch_projects,
                                   fetch_property_page, fetch_reviews, fetch_search, fetch_transactions)

DEVELOPERS_DIRECTORY_PAGE = 100   # bilbo's own ceiling; 960 developers = 10 calls


def _pagination(page, per_page, total, pages=None):
    if total is None:
        return {"page": page, "items_per_page": per_page, "total_pages": pages, "total_count": None}
    if pages is None:
        pages = math.ceil(total / per_page) if per_page else 0
    return {"page": page, "items_per_page": per_page, "total_pages": pages, "total_count": total}


def _country(ref, country):
    """A link's own TLD wins over the `country` param."""
    return (ref or {}).get("country") or country or refs.DEFAULT_COUNTRY


# ---- locations -------------------------------------------------------------------------------

def _locations_search(query, type, category, limit, country):
    params = [("filters.name", query), ("pagination.limit", limit), ("filters.use_popularity", "true"),
              ("filters.types", type), ("filters.category_id", category)]
    parsed = parsers.parse_locations(fetch_locations(country, params), country)
    return {"query": query, "country": country, "count": len(parsed["results"]), "total": parsed["total"],
            "results": parsed["results"]}


def locations_search(**data):
    """Place autocomplete: the cities, communities, sub-communities and towers
    matching a name, with id, full path, coordinates, review score and the
    area-insights link. The ids feed every `location` / `area` param."""
    return cached_call("property_finder.locations_search", data, _locations_search, ttl.LOCATIONS_CACHE)


def _locations_by_ids(country, ids):
    params = [("filters.ids", i) for i in ids]
    return parsers.parse_locations(fetch_locations(country, params), country)["results"]


def _lookup_location(country, slug=None, query=None):
    """A slug ('dubai-marina') or a free-text name -> the best matching
    location record (the site's autocomplete, popularity-ranked)."""
    text = (slug or query or "").replace("-", " ").strip()
    params = [("filters.name", text), ("pagination.limit", 10), ("filters.use_popularity", "true")]
    rows = parsers.parse_locations(fetch_locations(country, params), country)["results"]
    if slug:
        for row in rows:
            if (row.get("slug") or "").lower() == slug.lower():
                return row
    return rows[0] if rows else None


def _resolve_location(ref, country, required=True):
    """A refs.resolve_location dict -> (ids, [location records]) through the
    cached lookups. NotFound when the site knows no such place."""
    if not ref:
        return None, None
    country = _country(ref, country)
    if ref.get("ids"):
        rows = cached_call("property_finder.locations_by_ids", {"country": country, "ids": ref["ids"]},
                           _locations_by_ids, ttl.LOCATION_LOOKUP_CACHE)
        if not rows and required:
            raise PropertyFinderNotFound(f"no location with id {', '.join(str(i) for i in ref['ids'])}")
        return ref["ids"], rows
    key = {"country": country, "slug": ref.get("slug"), "query": ref.get("query")}
    row = cached_call("property_finder.location_lookup", key, _lookup_location, ttl.LOCATION_LOOKUP_CACHE)
    if row is None:
        raise PropertyFinderNotFound(f"no location matches '{ref.get('slug') or ref.get('query')}'")
    return [row["id"]], [row]


def _location_context(rows):
    """The slice of a location record that a list response repeats."""
    out = []
    for row in rows or []:
        out.append({k: row.get(k) for k in ("id", "name", "full_name", "type", "slug", "coordinates", "link", "insights_link")})
    return out or None


# ---- properties ------------------------------------------------------------------------------

def _search_params(category, location_ids, property_type=None, bedrooms=None, bathrooms=None, min_price=None,
                   max_price=None, rent_period=None, min_area=None, max_area=None, furnished=None,
                   completion_status=None, amenities=None, keywords=None, listed_within=None,
                   virtual_viewing=None, deal_badge=None, has_mortgage_cashback=None, sort=0, page=1,
                   per_page=25, agent_id=None, client_id=None):
    params = [("filters.category_id", category)]
    params += [("filters.locations_ids", i) for i in (location_ids or [])]
    params += [("filters.number_of_bedrooms", b) for b in (bedrooms or [])]
    params += [("filters.number_of_bathrooms", b) for b in (bathrooms or [])]
    params += [("filters.amenities", a) for a in (amenities or [])]
    params += [
        ("filters.property_type_id", property_type),
        ("filters.min_price", _number(min_price)),
        ("filters.max_price", _number(max_price)),
        ("filters.price_type", rent_period if category in (2, 4) else None),
        ("filters.min_area", _number(min_area)),
        ("filters.max_area", _number(max_area)),
        ("filters.furnished", furnished),
        ("filters.completion_status", completion_status),
        ("filters.keywords", keywords),
        ("filters.listed_within", listed_within),
        ("filters.virtual_viewings", virtual_viewing),
        ("filters.deal_badges", deal_badge),
        ("filters.has_mortgage_cashback", "true" if has_mortgage_cashback else None),
        ("filters.agent_id", agent_id),
        ("filters.client_id", client_id),
        ("sorting.sort", sort),
        ("pagination.page", page),
        ("pagination.limit", per_page),
    ]
    return params


def _number(value):
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def _floor(value):
    return None if value is None else int(math.floor(value))


def _ceil(value):
    return None if value is None else int(math.ceil(value))


def _search_response(country, params, page, per_page):
    parsed = parsers.parse_search(fetch_search(country, params), country)
    return {
        "results": parsed["results"],
        "promoted_projects": parsed["promoted_projects"],
        "new_listings_count": parsed["new_count"],
        "price_range": parsed["price_range"],
        "pagination": _pagination(page, per_page, parsed["total"], parsed["pages"]),
    }


def _properties_search(location, category, page, per_page, country, **filters):
    country = _country(location, country)
    ids, rows = _resolve_location(location, country)
    params = _search_params(category, ids, page=page, per_page=per_page, **filters)
    out = _search_response(country, params, page, per_page)
    return {"country": country, "category": refs.CATEGORY_NAMES.get(category), "location": _location_context(rows), **out}


def properties_search(**data):
    """Sale, rent and commercial listings with every filter the site has (type,
    bedrooms, bathrooms, price, rent period, size, furnishing, completion,
    amenities, keywords, listing age, virtual viewings, deal badges, mortgage
    cashback) and its 8 sorts; 25 cards a page (max 60). The new-project cards
    the site slots between listings come apart in `promoted_projects`."""
    return cached_call("property_finder.properties_search", data, _properties_search, ttl.SEARCH_CACHE)


def _property_record(country, id):
    record = parsers.parse_property_page(fetch_property_page(country, id), country)
    if record is None:
        raise PropertyFinderNotFound(f"listing {id} not found")
    return record


def property_details(property, country):
    """Everything the listing page carries: the card, full gallery, permit /
    licence numbers, agent and company profiles, similar sale / rent
    transactions, the community vs tower price trend, price comparison and
    the community / building insight blocks."""
    country = _country(property, country)
    return cached_call("property_finder.property", {"country": country, "id": property["id"]},
                       _property_record, ttl.PROPERTY_CACHE)


def _price_trends(location, category, bedrooms, property_type, country):
    country = _country(location, country)
    ids, rows = _resolve_location(location, country)
    payload = fetch_price_trends(country, ids[0], category, bedrooms, property_type)
    trends = parsers.parse_price_trends(payload)
    if trends is None:
        raise PropertyFinderNotFound("no price trend for this location / bedrooms / property type")
    return {
        "country": country,
        "location": (_location_context(rows) or [None])[0],
        "category": refs.CATEGORY_NAMES.get(category),
        "bedrooms": bedrooms,
        "property_type": refs.PROPERTY_TYPE_NAMES.get(property_type),
        **trends,
    }


def properties_price_trends(**data):
    """Price per sqft over 1, 2 and 5 years for one bedroom count and property
    type in a community, sub-community or tower, side by side with its parent
    community."""
    return cached_call("property_finder.price_trends", data, _price_trends, ttl.PRICE_TRENDS_CACHE)


# ---- agents ------------------------------------------------------------------------------------

def _agents_params(page, per_page, text=None, location_ids=None, category=None, language=None, nationality=None,
                   super_agent=None, sort=None, broker_id=None):
    # `language_ids` / `is_superagent` are the names the API filters on; the
    # find-agent page's own `languages` / `superagent` query names are ignored
    # (2026-11-10). Every agent it lists has live listings, so it has no
    # listings filter to offer.
    # several places go as ONE comma list (their union); a repeated location_ids
    # keeps only the last one (2026-11-10)
    params = [("text", text), ("category_id", category), ("language_ids", language), ("nationality", nationality),
              ("is_superagent", "true" if super_agent else None),
              ("sort", sort), ("broker_id", broker_id), ("page", page), ("per_page", per_page),
              ("location_ids", ",".join(str(i) for i in location_ids) if location_ids else None)]
    return params


# Sorted by listing counts, the agents API serves the first 10,000 results only
# (page 101 of 100 is empty although total_pages says 202); the featured order
# pages to the end.
AGENTS_SORTED_WINDOW = 10_000


def _agents_response(country, params, page, per_page):
    rows, totals = fetch_agents(country, params)
    pages = totals.get("total_pages")
    sort = dict(params).get("sort")
    if pages is not None and sort not in (None, refs.AGENT_SORTS["featured"]):
        pages = min(pages, max(AGENTS_SORTED_WINDOW // per_page, 1))
    return {
        "results": [parsers.parse_agent(r, country) for r in rows],
        "pagination": _pagination(page, per_page, totals.get("total"), pages),
    }


def _agents_search(query, location, category, language, nationality, super_agent, sort, page, per_page, country):
    country = _country(location, country)
    ids, rows = _resolve_location(location, country)
    params = _agents_params(page, per_page, text=query, location_ids=ids, category=category, language=language,
                            nationality=nationality, super_agent=super_agent, sort=sort)
    return {"country": country, "query": query, "location": _location_context(rows), **_agents_response(country, params, page, per_page)}


def agents_search(**data):
    """The agent directory: search by name, location, category, language,
    nationality and SuperAgent status; 20 agents a page (max 100) with
    rating, listing counts, languages and company."""
    return cached_call("property_finder.agents_search", data, _agents_search, ttl.AGENTS_SEARCH_CACHE)


def _agent_record(country, id):
    return parsers.parse_agent(fetch_agent(country, id), country)


def agent_details(agent, country):
    """An agent's profile: bio, languages, nationality, licence (BRN), rating
    with its distribution, listing counts, claimed sale / rent deals, top
    locations and the company."""
    country = _country(agent, country)
    return cached_call("property_finder.agent", {"country": country, "id": agent["id"]}, _agent_record, ttl.AGENT_CACHE)


def _agent_listings(agent, category, sort, page, per_page, country):
    country = _country(agent, country)
    agent_details(agent, country)          # 404 for an unknown agent (cached)
    params = _search_params(category, None, sort=sort, page=page, per_page=per_page, agent_id=agent["id"])
    out = _search_response(country, params, page, per_page)
    return {"country": country, "agent_id": agent["id"], "agent_link": refs.agent_link(country, None, agent["id"]),
            "category": refs.CATEGORY_NAMES.get(category), **out}


def agent_listings(**data):
    """An agent's live listings (the properties/search cards), by category and
    sort; 25 a page (max 60)."""
    return cached_call("property_finder.agent_listings", data, _agent_listings, ttl.LISTINGS_CACHE)


# ---- companies ---------------------------------------------------------------------------------

def _companies_search(query, location, sort, page, per_page, country):
    country = _country(location, country)
    ids, rows = _resolve_location(location, country)
    # the brokerages API filters on ONE `location_id`: `location_ids` is ignored,
    # a repeated `location_id` keeps the last one and a CSV is a 400 (2026-11-10)
    params = [("text", query), ("sort", sort), ("page", page), ("per_page", per_page),
              ("location_id", ids[0] if ids else None)]
    data, totals = fetch_brokerages(country, params)
    return {
        "country": country, "query": query, "location": _location_context((rows or [])[:1]),
        "results": [parsers.parse_company(r, country) for r in data],
        "pagination": _pagination(page, per_page, totals.get("total"), totals.get("total_pages")),
    }


def companies_search(**data):
    """The real-estate company (brokerage) directory, by name and location; 20
    a page (max 100) with licence, contacts, listing and agent counts."""
    return cached_call("property_finder.companies_search", data, _companies_search, ttl.COMPANIES_SEARCH_CACHE)


def _company_record(country, id):
    return parsers.parse_company(fetch_brokerage(country, id), country)


def company_details(company, country):
    """A company's profile: licence, email, phone, address, description,
    listings per category, agent and SuperAgent counts, awards and branches."""
    country = _country(company, country)
    return cached_call("property_finder.company", {"country": country, "id": company["id"]}, _company_record,
                       ttl.COMPANY_CACHE)


def _company_agents(company, sort, page, per_page, country):
    country = _country(company, country)
    company_details(company, country)      # 404 for an unknown company (cached)
    params = _agents_params(page, per_page, sort=sort, broker_id=company["id"])
    return {"country": country, "company_id": company["id"],
            "company_link": refs.company_link(country, None, company["id"]),
            **_agents_response(country, params, page, per_page)}


def company_agents(**data):
    """A company's agents (the agents/search records); 20 a page (max 100)."""
    return cached_call("property_finder.company_agents", data, _company_agents, ttl.COMPANIES_SEARCH_CACHE)


def _company_listings(company, category, sort, page, per_page, country):
    country = _country(company, country)
    company_details(company, country)      # 404 for an unknown company (cached)
    params = _search_params(category, None, sort=sort, page=page, per_page=per_page, client_id=company["id"])
    out = _search_response(country, params, page, per_page)
    return {"country": country, "company_id": company["id"],
            "company_link": refs.company_link(country, None, company["id"]),
            "category": refs.CATEGORY_NAMES.get(category), **out}


def company_listings(**data):
    """A company's live listings (the properties/search cards), by category
    and sort; 25 a page (max 60)."""
    return cached_call("property_finder.company_listings", data, _company_listings, ttl.LISTINGS_CACHE)


# ---- projects / developers -----------------------------------------------------------------------

def _developer_by_slug(country, slug):
    payload = fetch_developers(country, [("filter.slug", slug), ("limit", 1)])
    rows = parsers.parse_developers(payload, country)["results"]
    if not rows:
        raise PropertyFinderNotFound(f"developer '{slug}' not found")
    return rows[0]


def _developer_record(country, id):
    return parsers.parse_developer(fetch_developer(country, id), country)


def _resolve_developer(ref, country):
    """A refs.resolve_developer dict -> the developer record (cached by slug and by uuid)."""
    country = _country(ref, country)
    if ref.get("uuid"):
        return cached_call("property_finder.developer", {"country": country, "id": ref["uuid"]}, _developer_record,
                           ttl.DEVELOPER_CACHE)
    return cached_call("property_finder.developer_by_slug", {"country": country, "slug": ref["slug"]},
                       _developer_by_slug, ttl.DEVELOPER_CACHE)


def _projects_search(location, developer, property_type, completion_status, min_price, max_price, delivery_from,
                     has_dld_id, has_post_handover_payment_plan, keywords, page, per_page, country):
    country = _country(location or developer, country)
    ids, rows = _resolve_location(location, country)
    dev = _resolve_developer(developer, country) if developer else None
    params = [("filter.location_ids", i) for i in (ids or [])]
    params += [
        ("filter.developer_ids", dev["id"] if dev else None),
        ("filter.property_type", property_type),
        ("filter.construction_phase", completion_status),
        ("filter.min_price", _number(min_price)),
        ("filter.max_price", _number(max_price)),
        ("filter.delivery_date_gte", f"{delivery_from}T00:00:00Z" if delivery_from else None),
        ("filter.has_dld_id", "true" if has_dld_id else None),
        ("filter.has_post_handover_payment_plan", "true" if has_post_handover_payment_plan else None),
        ("filter.keywords", keywords),
        ("page", page),
        ("limit", per_page),
    ]
    parsed = parsers.parse_projects(fetch_projects(country, params), country)
    return {
        "country": country,
        "location": _location_context(rows),
        "developer": {k: dev.get(k) for k in ("id", "name", "slug", "link")} if dev else None,
        "results": parsed["results"],
        "price_range": parsed["price_range"],
        "popular_locations": parsed["popular_locations"],
        "pagination": _pagination(page, per_page, parsed["total"], parsed["pages"]),
    }


def projects_search(**data):
    """New (off-plan) projects by location, developer, property type,
    construction phase, starting price, delivery date, DLD registration,
    post-handover payment plan and keywords; 10 a page (max 50)."""
    return cached_call("property_finder.projects_search", data, _projects_search, ttl.PROJECTS_SEARCH_CACHE)


def _project_record(country, id):
    return parsers.parse_project(fetch_project(country, id), country)


def _project_by_slug(country, slug):
    payload = fetch_projects(country, [("filter.slug", slug), ("limit", 1)])
    rows = [p for p in (payload.get("data") or {}).get("projects") or [] if isinstance(p, dict)]
    rows = [p for p in rows if (p.get("slug") or "").lower() == slug.lower()] or rows
    if not rows:
        raise PropertyFinderNotFound(f"project '{slug}' not found")
    return parsers.parse_project(rows[0], country)


def project_details(project, country):
    """The full bilbo record: units with floor plans, payment plans, construction
    and sales phases, amenities, FAQs, media, developer contacts."""
    country = _country(project, country)
    if project.get("uuid"):
        return cached_call("property_finder.project", {"country": country, "id": project["uuid"]}, _project_record,
                           ttl.PROJECT_CACHE)
    return cached_call("property_finder.project_by_slug", {"country": country, "slug": project["slug"]},
                       _project_by_slug, ttl.PROJECT_CACHE)


def _developers_directory(country):
    """Every developer (10 upstream pages of 100), for the name search."""
    out, page = [], 1
    while True:
        parsed = parsers.parse_developers(fetch_developers(country, [("page", page), ("limit", DEVELOPERS_DIRECTORY_PAGE)]), country)
        out += parsed["results"]
        if not parsed["results"] or (parsed["pages"] and page >= parsed["pages"]) or page >= 50:
            break
        page += 1
    return out


def _developers_search(query, page, per_page, country):
    if not query:
        parsed = parsers.parse_developers(fetch_developers(country, [("page", page), ("limit", per_page)]), country)
        return {"country": country, "query": None, "results": parsed["results"],
                "pagination": _pagination(page, per_page, parsed["total"], parsed["pages"])}
    rows = cached_call("property_finder.developers_directory", {"country": country}, _developers_directory,
                       ttl.DEVELOPERS_CACHE)
    needle = query.lower()
    hits = [d for d in rows if needle in (d.get("name") or "").lower() or needle in (d.get("slug") or "").lower()
            or needle in (d.get("name_ar") or "").lower()]
    start = (page - 1) * per_page
    return {"country": country, "query": query, "results": hits[start:start + per_page],
            "pagination": _pagination(page, per_page, len(hits))}


def developers_search(**data):
    """The developer directory, page by page or searched by name: logo,
    licence, contacts and project counts."""
    return cached_call("property_finder.developers_search", data, _developers_search, ttl.DEVELOPERS_CACHE)


def developer_details(developer, country):
    """A developer's profile: description, logo, licence, contacts, founding
    year, headquarters, projects online and delivered by phase."""
    return _resolve_developer(developer, country)


# ---- transactions ---------------------------------------------------------------------------------

def _transactions_search(location, type, period, date_from, date_to, property_type, bedrooms, min_price, max_price,
                         min_area, max_area, completion_status, contract_status, sold_by, unit_number, sort, page,
                         per_page, country):
    country = _country(location, country)
    ids, rows = _resolve_location(location, country)
    # no `type` given: a transactions/rented/… link means rentals, anything else sales
    type = type or (2 if (location or {}).get("deal") == "rented" else 1)
    cap_pages = max(config.PROPERTY_FINDER_TRANSACTIONS_ROW_CAP // per_page, 1)
    base = {"country": country, "location": (_location_context(rows) or [None])[0], "type": "rented" if type == 2 else "sold"}
    if page > cap_pages:
        # the site refuses any query past 500 rows; narrow by date to see more
        return {**base, "results": [], "summary": None, "similar_searches": None,
                "pagination": _pagination(page, per_page, None, cap_pages),
                "note": f"Property Finder serves at most {config.PROPERTY_FINDER_TRANSACTIONS_ROW_CAP} transactions per "
                        "query; narrow the dates (date_from / date_to or period) to reach older rows."}
    params = [
        ("offering_type_id", type), ("size", per_page), ("page", page), ("sort", sort), ("period", period),
        ("start_date", date_from), ("end_date", date_to), ("property_type_id", property_type),
        ("bedroom_ids", ",".join(str(b) for b in bedrooms) if bedrooms else None),
        # whole numbers only: a decimal bound is dropped upstream and the filter vanishes
        # (2026-11-10: min_price=44458.56 returned the whole day)
        ("min_price", _floor(min_price)), ("max_price", _ceil(max_price)),
        ("min_area", _floor(min_area)), ("max_area", _ceil(max_area)),
        ("completion_status", completion_status), ("contract_status", contract_status), ("sold_by", sold_by),
        ("unit_number", unit_number),
    ]
    parsed = parsers.parse_transactions(fetch_transactions(country, ids[0], params), type, country)
    pages = parsed["pages"]
    if pages is not None and pages > cap_pages:
        pages = cap_pages
    out = {**base, "results": parsed["results"], "summary": parsed["summary"],
           "similar_searches": parsed["similar_searches"],
           "pagination": _pagination(page, per_page, parsed["total"], pages)}
    if parsed["total"] and parsed["total"] > config.PROPERTY_FINDER_TRANSACTIONS_ROW_CAP:
        out["note"] = (f"Property Finder serves at most {config.PROPERTY_FINDER_TRANSACTIONS_ROW_CAP} of the "
                       f"{parsed['total']} matching transactions per query; narrow the dates to reach the rest.")
    return out


def transactions_search(**data):
    """Dubai Land Department sales and rentals in a Dubai community or tower:
    price, price per sqft, size, bedrooms, unit, previous price, rental yield,
    plus a market summary with a monthly trend. 25 a page (max 50); the site
    serves at most 500 rows per query."""
    return cached_call("property_finder.transactions_search", data, _transactions_search, ttl.TRANSACTIONS_CACHE)


# ---- areas ------------------------------------------------------------------------------------------

def _area_path(area, country):
    """The site-relative area-insights path for an area ref (+ the resolved id)."""
    if area.get("slug") and area.get("city_slug"):
        return f"/en/area-insights/{area['city_slug']}/{area['slug']}", None
    ids, rows = _resolve_location(area, country)
    row = (rows or [None])[0]
    link = (row or {}).get("insights_link")
    if not link:
        name = (row or {}).get("name") or ids[0]
        raise PropertyFinderNotFound(f"no area insights page for '{name}' (cities have none; try a community or tower)")
    return "/" + link.split("/", 3)[-1] if link.startswith("http") else link, ids[0]


def _area_record(country, path):
    record = parsers.parse_area_page(fetch_area_page(country, path), country)
    if record is None:
        raise PropertyFinderNotFound(f"area page {path} not found")
    return record


def area_details(area, country):
    """The area-insights page: guide texts, FAQs, house prices, points of
    interest, demographics, market stats, popular buildings, similar areas."""
    country = _country(area, country)
    path, _ = _area_path(area, country)
    return cached_call("property_finder.area", {"country": country, "path": path}, _area_record, ttl.AREA_CACHE)


def _area_reviews(area, sort, include_sublocations, page, per_page, country):
    country = _country(area, country)
    ids, rows = _resolve_location(area, country)
    params = [("locale", "en"), ("include", "reviews"), ("reviewsPage", page), ("reviewsPageSize", per_page),
              ("reviewsSort", sort)]
    parsed = parsers.parse_reviews(fetch_reviews(country, ids[0], params), children=bool(include_sublocations))
    return {
        "country": country,
        "location": {**(parsed["location"] or {}), "insights_link": ((rows or [{}])[0] or {}).get("insights_link")},
        "scope": "sublocations" if include_sublocations else "area",
        "score": parsed["score"],
        "scores": parsed["scores"],
        "categories": parsed["categories"],
        "sort": parsed["sort"] or sort,
        "sublocations": parsed["sublocations"],
        "results": parsed["results"],
        "pagination": _pagination(page, per_page, parsed["total"], parsed["pages"]),
    }


def area_reviews(**data):
    """Resident reviews of a community or tower: overall and per-category
    scores, review texts with rating, likes and persona; the reviews of its
    buildings / sub-communities with include_sublocations. 20 a page (max 50)."""
    return cached_call("property_finder.area_reviews", data, _area_reviews, ttl.REVIEWS_CACHE)
