"""Property Finder parsers: raw JSON / HTML -> clean dicts. Pure functions,
no I/O; every one tolerates a partial payload (missing keys -> null).

Fixtures (property_finder/fixtures/, captured 2026-11-07 from
www.propertyfinder.ae through fetch.py):

  search_buy_dubai_marina_newest.json   v2 search, 25 property cards
  search_rent_marina_2bed_monthly.json  rent, monthly price, furnished + amenities
  search_no_match.json                  0 listings
  search_agent_264476.json / search_company_4338_rent.json
  search_new_projects_cat5.json         category 5: `project` cards
  search_sa_buy.json                    the .sa storefront (SAR)
  property_164588946_buy.html           PLP page (villa for sale, ~446 KB)
  property_135146604_rent.html          PLP page (monthly rental)
  price_trends_4467_buy_3bed_villa.json
  agents_search_nathan.json / agents_broker_4338_page2.json /
  agents_filtered_marina_rent_russian.json / agents_no_match.json
                                        pf-b2c-customer agents ({"rows", "totals"})
  agent_264476.json                     agent profile
  brokerages_search_barnes.json / brokerages_marina_most_listings.json /
  brokerages_no_match.json / brokerage_4338.json
  projects_search_dubai_p1.json / projects_search_villa_filtered.json /
  projects_search_no_match.json / projects_search_slug_valia_tower.json
  project_valia_tower.json              bilbo project (data.project)
  developers_p1.json / developers_slug_emaar.json / developers_past_end.json
  developer_emaar.json
  transactions_marina_sold_1y_p1.json / transactions_marina_rented_filtered.json /
  transactions_unknown_location.json    (0 rows, empty summary)
  locations_marina.json / locations_ids_1_50_4467.json / locations_no_match.json /
  locations_sa_riyadh.json
  area_dubai_marina.html                community area-insights page (2.4 MB)
  area_tower_marina_gate.html           sub-community / tower page (1.5 MB)
  reviews_marina_p1.json / reviews_none_5629.json
"""
import html as html_lib
import json
import re

from property_finder import refs

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|section|tr|table)[^>]*>", re.I)


# ---- small helpers ------------------------------------------------------------------

def _none(value):
    """'' / 'N/A' / {} / [] of nothing -> None; everything else unchanged."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value and value.upper() not in ("N/A", "NULL", "NONE", "-") else None
    return value


def _missing(value):
    """None / '' / a bare boolean count as "no number" (0 does not)."""
    return value is None or value is True or value is False or (isinstance(value, str) and not value.strip())


def _int(value):
    if _missing(value):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value):
    if _missing(value):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        out = float(value)
        return int(out) if out.is_integer() and abs(out) < 1e15 else round(out, 4)
    except (TypeError, ValueError):
        return None


def _bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    low = str(value).strip().lower()
    if low in ("true", "1", "yes", "y"):
        return True
    if low in ("false", "0", "no", "n", ""):
        return False
    return None


def _date(value):
    """'2026-10-26T11:19:10Z' -> '2026-10-26'; a date is kept; else None."""
    value = _none(value)
    if not value or not isinstance(value, str):
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    if not match:
        return None
    day = match.group(1)
    return None if day.startswith("0001-") else day


def _datetime(value):
    """ISO instant kept as given ('2026-10-26T11:19:10Z'); '' -> None."""
    value = _none(value)
    if not value or not isinstance(value, str) or not re.match(r"\d{4}-\d{2}-\d{2}", value):
        return None
    return None if value.startswith("0001-") else value


def _text(value):
    """HTML fragment -> readable plain text (block tags -> newlines)."""
    value = _none(value)
    if not value or not isinstance(value, str):
        return None
    text = _BLOCK_TAG_RE.sub("\n", value)
    text = _TAG_RE.sub("", text)
    text = html_lib.unescape(text).replace("\xa0", " ")
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES_RE.sub("\n\n", text).strip()
    return text or None


def _en(value):
    """A {'en': .., 'ar': ..} pair -> the English string (or the value itself)."""
    if isinstance(value, dict):
        return _none(value.get("en")) or _none(value.get("ar"))
    return _none(value)


def _ar(value):
    return _none(value.get("ar")) if isinstance(value, dict) else None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _coordinates(value):
    value = _dict(value)
    lat, lon = _float(value.get("lat")), _float(value.get("lon", value.get("lng")))
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None
    return {"lat": lat, "lon": lon}


def _slug_label(value):
    """'under_construction' -> 'under-construction' style public tokens."""
    value = _none(value)
    return value.replace("_", "-").lower() if isinstance(value, str) else None


def next_data(page_html):
    """The Next.js `__NEXT_DATA__` object of a server-rendered page (or None)."""
    match = _NEXT_DATA_RE.search(page_html or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def page_props(page_html):
    data = next_data(page_html) or {}
    return _dict(_dict(data.get("props")).get("pageProps"))


# ---- locations ---------------------------------------------------------------------------

def _location_type(value):
    return _slug_label(value)


def _location_image(image):
    image = _dict(image)
    return {
        "category": _none(image.get("category_name")),
        "link": _none(image.get("full_url") or image.get("url")),
        "thumbnail": _none(image.get("thumb_url") or image.get("thumbnail_url")),
    }


def parse_location(item, country=refs.DEFAULT_COUNTRY):
    """One b2c-location v2 item -> a location record."""
    item = _dict(item)
    loc = _dict(item.get("location")) or item
    lid = _int(loc.get("id") or item.get("id"))
    name = _none(loc.get("name"))
    parent = _none(loc.get("path_name"))
    path = [int(p) for p in str(loc.get("path") or "").split(".") if p.isdigit()]
    review = _dict(loc.get("review"))
    insights = _none(loc.get("insights_url"))
    return {
        "id": lid,
        "name": name,
        "full_name": f"{name}, {parent}" if name and parent else name,
        "type": _location_type(loc.get("location_type")),
        "level": _int(loc.get("level")),
        "alias": _none(item.get("alias")),
        "parent_name": parent,
        "parent_id": path[-2] if len(path) >= 2 else None,
        "city_id": path[0] if path else None,
        "city_slug": _none(loc.get("url_city_slug")),
        "slug": _none(loc.get("url_slug") or loc.get("current_language_slug") or loc.get("slug")),
        "path": path or None,
        "coordinates": _coordinates(loc.get("coordinates")),
        "children_count": _int(loc.get("children_count")),
        "link": refs.search_link(country, 1, [lid]) if lid else None,
        "insights_link": refs.absolute(country, insights),
        "review": {"score": _float(review.get("score")) or None, "count": _int(review.get("count")) or 0,
                   "link": refs.absolute(country, _none(review.get("url")))} if review else None,
        "images": [_location_image(i) for i in _list(loc.get("images"))] or None,
        "is_published": _bool(loc.get("published")),
    }


def parse_locations(payload, country=refs.DEFAULT_COUNTRY):
    payload = _dict(payload)
    meta = _dict(payload.get("meta"))
    results = [parse_location(i, country) for i in _list(payload.get("items"))]
    return {
        "results": results,
        "total": _int(meta.get("total")) if results or meta.get("total") is not None else 0,
        "pages": _int(meta.get("pages")) if results or meta.get("pages") is not None else 0,
    }


# ---- listing cards ------------------------------------------------------------------------

def _price(price, country=refs.DEFAULT_COUNTRY):
    price = _dict(price)
    amount = _float(price.get("value"))
    period = _none(price.get("period"))
    return {
        "amount": None if _bool(price.get("is_hidden")) else amount,
        "currency": _none(price.get("currency")) or refs.currency(country),
        "period": None if period in (None, "sell") else period,
        "is_hidden": bool(price.get("is_hidden")),
    }


def _size(size):
    size = _dict(size)
    value = _float(size.get("value"))
    if value is None:
        return None
    return {"value": value, "unit": _none(size.get("unit")) or "sqft"}


def _card_location(loc, country):
    loc = _dict(loc)
    lid = _int(loc.get("id"))
    if lid is None and not loc.get("name"):
        return None
    return {
        "id": lid,
        "name": _none(loc.get("name")),
        "full_name": _none(loc.get("full_name")),
        "type": _location_type(loc.get("type")),
        "slug": _none(loc.get("slug")),
        "parent_name": _none(loc.get("path_name")),
        "path": [int(p) for p in str(loc.get("path") or "").split(".") if p.isdigit()] or None,
        "coordinates": _coordinates(loc.get("coordinates")),
        "insights_link": refs.absolute(country, _none(loc.get("insights_url"))),
    }


def _location_tree(tree, country):
    out = []
    for node in _list(tree):
        node = _dict(node)
        out.append({
            "id": _int(node.get("id")),
            "name": _none(node.get("name")),
            "type": _location_type(node.get("type")),
            "slug": _none(node.get("slug_en") or node.get("slug")),
            "level": _int(node.get("level")),
            "insights_link": refs.absolute(country, _none(node.get("insights_url"))),
        })
    return out or None


def _contacts(options):
    out = {"phone": None, "whatsapp": None, "whatsapp_link": None, "email": None}
    for opt in _list(options):
        opt = _dict(opt)
        kind, value, link = _none(opt.get("type")), _none(opt.get("value")), _none(opt.get("link"))
        if kind == "phone":
            out["phone"] = value or (link[4:] if link and link.startswith("tel:") and len(link) > 4 else None)
        elif kind == "whatsapp":
            out["whatsapp"] = value
            out["whatsapp_link"] = link
        elif kind == "email":
            out["email"] = value or (link[7:] if link and link.startswith("mailto:") and len(link) > 7 else None)
    return out


def _card_agent(agent, country):
    agent = _dict(agent)
    aid = _int(agent.get("id"))
    if aid is None and not agent.get("name"):
        return None
    languages = [_none(x) for x in _list(agent.get("languages"))]
    return {
        "id": aid,
        "name": _none(agent.get("name")),
        "link": refs.agent_link(country, _none(agent.get("slug")), aid) if aid else None,
        "image": _none(agent.get("image")),
        "is_super_agent": _bool(agent.get("is_super_agent")),
        "languages": [x for x in languages if x] or None,
        "email": _none(agent.get("email")),
    }


def _card_broker(broker, country):
    broker = _dict(broker)
    bid = _int(broker.get("id"))
    if bid is None and not broker.get("name"):
        return None
    return {
        "id": bid,
        "name": _none(broker.get("name")),
        "link": refs.company_link(country, _none(broker.get("slug")), bid) if bid else None,
        "logo": _none(broker.get("logo")),
        "address": _none(broker.get("address")),
        "email": _none(broker.get("email")),
        "phone": _none(broker.get("phone")),
    }


def _furnished(value):
    value = _none(value)
    if value is None:
        return None
    if isinstance(value, str):
        return refs.FURNISHED_NAMES.get(value.upper(), value.lower().replace("_", "-"))
    return None


def _bedrooms(card):
    value = card.get("bedrooms_value")
    if value is None:
        value = card.get("bedrooms")
    value = _int(value)
    return value


def _card_images(images):
    out = []
    for image in _list(images):
        image = _dict(image)
        if image.get("medium") or image.get("small"):
            out.append({"small": _none(image.get("small")), "medium": _none(image.get("medium")),
                        "label": _none(image.get("classification_label"))})
    return out or None


def _amenities(card):
    amenities = _list(card.get("amenities"))
    out = []
    for item in amenities:
        if isinstance(item, dict):
            code, name = _none(item.get("code")), _none(item.get("name"))
        else:
            code = _none(item)
            name = refs.AMENITIES.get(code) if code else None
        if code or name:
            out.append({"code": code, "name": name or (refs.AMENITIES.get(code) if code else None)})
    if not out:
        names = [_none(n) for n in _list(card.get("amenity_names"))]
        out = [{"code": refs.AMENITY_SLUGS.get(re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")), "name": n}
               for n in names if n]
    return out or None


def parse_property_card(card, country=refs.DEFAULT_COUNTRY):
    """One v2 `property` card -> a listing record (the fields every card has)."""
    card = _dict(card)
    pid = _int(card.get("id"))
    category_id = _int(card.get("category_id"))
    contacts = _contacts(card.get("contact_options"))
    rera = card.get("rera")
    permit = _none(rera) if isinstance(rera, str) else _none(_dict(rera).get("number"))
    return {
        "id": pid,
        "listing_type": "property",
        "link": refs.property_link(country, pid, _none(card.get("share_url"))) if pid else None,
        "title": _none(card.get("title")),
        "description": _none(card.get("description")),
        "category": refs.CATEGORY_NAMES.get(category_id),
        "offering_type": _none(card.get("offering_type")),
        "property_type": _none(card.get("property_type")),
        "property_type_id": _int(card.get("property_type_id")),
        "price": _price(card.get("price"), country),
        "price_per_sqft": _float(_dict(card.get("price_per_area")).get("price")),
        "bedrooms": _bedrooms(card),
        "bathrooms": _int(card.get("bathrooms_value") if card.get("bathrooms_value") is not None else card.get("bathrooms")),
        "size": _size(card.get("size")),
        "furnished": _furnished(card.get("furnished")),
        "completion_status": _slug_label(card.get("completion_status")),
        "reference": _none(card.get("reference")),
        "permit_number": permit,
        "listed_date": _datetime(card.get("listed_date")),
        "last_refreshed_at": _datetime(card.get("last_refreshed_at")),
        "available_from": _date(card.get("rental_availability_date")),
        "is_verified": _bool(card.get("is_verified")),
        "is_featured": _bool(card.get("is_featured")),
        "is_premium": _bool(card.get("is_premium")),
        "is_exclusive": _bool(card.get("is_exclusive")) or _bool(card.get("is_pf_exclusive")) or False,
        "is_spotlight": _bool(card.get("is_spotlight_listing")),
        "is_new": _bool(card.get("is_new_insert")),
        "is_new_construction": _bool(card.get("is_new_construction")),
        "is_direct_from_developer": _bool(card.get("is_direct_from_developer")),
        "is_available": _bool(card.get("is_available")),
        "is_great_value": _bool(card.get("is_great_value")),
        "is_high_demand": _bool(card.get("is_high_demand")),
        "has_video": bool(_none(card.get("video_url")) or _none(card.get("video_id"))),
        "has_360_view": bool(_bool(card.get("has_view_360")) or _none(card.get("view_360"))),
        "has_live_viewing": bool(card.get("live_viewing")),
        "listing_level": _none(card.get("listing_level")),
        "utilities_price_type": None if card.get("utilities_price_type") in (None, "", "notSelected") else card.get("utilities_price_type"),
        "payment_methods": [_none(x) for x in _list(card.get("payment_method")) if _none(x)] or None,
        "location": _card_location(card.get("location"), country),
        "location_tree": _location_tree(card.get("location_tree"), country),
        "images": _card_images(card.get("images")),
        "images_count": _int(card.get("images_count")),
        "amenities": _amenities(card),
        "agent": _card_agent(card.get("agent"), country),
        "company": _card_broker(card.get("broker") or card.get("client"), country),
        "contact": contacts,
        "listing_key": _none(card.get("listing_id")),
    }


def parse_project_card(card, country=refs.DEFAULT_COUNTRY):
    """A v2 `project` card (category 5 / mixed results) -> a slim project record."""
    card = _dict(card)
    dev = _dict(card.get("developer"))
    loc = _dict(card.get("location"))
    tree = _list(loc.get("tree"))
    leaf = _dict(tree[-1]) if tree else {}
    contacts = _contacts(card.get("contact_options"))
    agents = []
    for agent in _list(_dict(card.get("agent_preview")).get("agents")):
        agent = _dict(agent)
        aid = _int(agent.get("id"))
        agents.append({"id": aid, "name": _none(agent.get("name")),
                       "link": refs.absolute(country, _none(agent.get("detail_url"))) or (refs.agent_link(country, None, aid) if aid else None),
                       "is_super_agent": _bool(agent.get("is_super_agent")),
                       "position": _none(agent.get("position")),
                       "company": _card_broker(agent.get("broker"), country)})
    return {
        "id": _none(card.get("id")),
        "listing_type": "project",
        "name": _none(card.get("name")),
        "slug": _none(card.get("slug")),
        "link": refs.project_link(country, _none(card.get("slug"))),
        "developer": {"id": _none(dev.get("id")), "name": _none(dev.get("name")), "logo": _none(dev.get("logo"))} if dev else None,
        "location": {"id": _int(leaf.get("id")), "name": _none(leaf.get("name")), "type": _location_type(leaf.get("type")),
                     "full_name": _none(loc.get("full_name"))} if loc else None,
        "property_type": _none(card.get("property_type")),
        "bedrooms": [_int(b) for b in _list(card.get("bedrooms")) if _int(b) is not None] or None,
        "price_from": _float(_dict(card.get("price")).get("from")) or _float(card.get("effective_price")),
        "currency": refs.currency(country),
        "size_min": _size(card.get("min_size")),
        "size_max": _size(card.get("max_size")),
        "delivery_date": _date(card.get("delivery_date")),
        "construction_phase": _slug_label(card.get("construction_phase_key")),
        "stock_availability": _none(card.get("stock_availability")),
        "hotness_level": _int(card.get("hotness_level")),
        "is_sponsored": _bool(card.get("is_sponsored")),
        "images": [{"small": _none(i.get("small")), "medium": _none(i.get("medium"))} for i in _list(card.get("images")) if isinstance(i, dict)] or None,
        "contact": contacts,
        "agents": agents or None,
    }


def parse_listing(entry, country=refs.DEFAULT_COUNTRY):
    """One v2 `listings[]` entry (property / project / project_unit) -> a record."""
    entry = _dict(entry)
    kind = _none(entry.get("listing_type"))
    if kind == "project" and entry.get("project"):
        return parse_project_card(entry.get("project"), country)
    if entry.get("property"):
        return parse_property_card(entry.get("property"), country)
    if entry.get("project_unit"):
        unit = parse_property_card(_dict(entry.get("project_unit")).get("property") or entry.get("project_unit"), country)
        unit["listing_type"] = "project_unit"
        return unit
    return None


def parse_search(payload, country=refs.DEFAULT_COUNTRY):
    """v2 search payload -> {"results": [...], "total": n, "pages": n, "per_page": n, "page": n}."""
    payload = _dict(payload)
    meta = _dict(payload.get("meta"))
    records = [r for r in (parse_listing(e, country) for e in _list(payload.get("listings"))) if r]
    # the site slots promoted new-project cards between the listings (one
    # every sixth row); they are not part of the page count, so they ride
    # beside the results instead of inflating them
    results = [r for r in records if r.get("listing_type") != "project"]
    promoted = [r for r in records if r.get("listing_type") == "project"]
    total, pages = _int(meta.get("total_count")), _int(meta.get("page_count"))
    if total is None and not results:
        total, pages = 0, 0
    return {
        "results": results,
        "promoted_projects": promoted or None,
        "total": total,
        "pages": pages,
        "per_page": _int(meta.get("per_page")),
        "page": _int(meta.get("page")),
        "new_count": _int(meta.get("new_properties_count")),
        "price_range": {"min": _float(_dict(meta.get("min_max_price")).get("min")),
                        "max": _float(_dict(meta.get("min_max_price")).get("max"))} if meta.get("min_max_price") else None,
    }


# ---- property details (PLP page) ------------------------------------------------------------

def _detail_rows(rows):
    """property_details / regulatory_details -> [{id, label, value}] (English)."""
    out = []
    for row in _list(rows):
        row = _dict(row)
        value = _dict(_dict(_dict(_dict(row.get("values")).get("primary")).get("value")).get("localized_value"))
        text = _en(value) if value else None
        if row.get("id") or text:
            out.append({"id": _none(row.get("id")), "label": _en(row.get("label")), "value": text,
                        "format": _none(row.get("display_format"))})
    return out or None


def _full_images(images):
    out = []
    for image in _list(images):
        image = _dict(image)
        if image.get("full") or image.get("medium"):
            out.append({"thumbnail": _none(image.get("thumbnail")), "medium": _none(image.get("medium")),
                        "full": _none(image.get("full")), "label": _none(image.get("classification_label"))})
    return out or None


def _detail_agent(agent, country):
    base = _card_agent(agent, country)
    if base is None:
        return None
    agent = _dict(agent)
    breakdown = _dict(agent.get("rating_breakdown"))
    base.update({
        "position": _none(agent.get("position")),
        "years_of_experience": _int(agent.get("years_of_experience")),
        "listings_count": _int(agent.get("total_properties")),
        "response_time_minutes": _int(agent.get("avg_whatsapp_response_time")),
        "rating": {"average": _float(agent.get("avg_score")), "count": _int(agent.get("review_count")) or 0,
                   "distribution": {str(i): _int(breakdown.get(f"score{i}")) or 0 for i in range(1, 6)} if breakdown else None},
        "transactions_count": _int(agent.get("transactions_count")),
        "license_number": _none(agent.get("license_no")),
    })
    link = _none(agent.get("detail_url"))
    if link:
        base["link"] = refs.absolute(country, link)
    return base


def _detail_broker(broker, country):
    base = _card_broker(broker, country)
    if base is None:
        return None
    broker = _dict(broker)
    base.update({
        "license_number": _none(broker.get("license_number")),
        "listings_count": _int(broker.get("total_properties")),
        "agents_count": _int(broker.get("total_agents")),
        "super_agents_count": _int(broker.get("total_super_agents")),
        "is_exclusive_partner": _bool(broker.get("is_exclusive")),
    })
    return base


def _similar_transactions(block):
    block = _dict(block)
    out = {}
    for key in ("buy", "rent"):
        rows = []
        for row in _list(block.get(key)):
            row = _dict(row)
            rows.append({"date": _date(row.get("date")), "amount": _float(row.get("amount")), "size": _float(row.get("size"))})
        out[key] = rows or None
    return out if (out.get("buy") or out.get("rent")) else None


def _price_trends(block):
    block = _dict(block)
    graph = _dict(block.get("graph"))
    if not graph:
        return None
    series = {}
    for frame, points in graph.items():
        rows = []
        for point in _list(points):
            point = _dict(point)
            row = {"date": _date(point.get("date")), "period": _none(point.get("period")),
                   "community_price": _float(point.get("communityPrice", point.get("community_price"))),
                   "tower_price": _float(point.get("towerPrice", point.get("tower_price")))}
            if point.get("bedroom_id") is not None:
                row["bedrooms"] = _int(point.get("bedroom_id"))
            rows.append(row)
        series[frame] = rows
    return {
        "unit": _none(block.get("axisLabel")),
        "community_name": _none(block.get("communityName")),
        "tower_name": _none(block.get("towerName")),
        "series": series,
    }


def _price_comparison(block):
    attrs = _dict(_dict(block).get("attributes"))
    overview, investor = _dict(attrs.get("overview")), _dict(attrs.get("investor"))
    if not overview and not investor:
        return None
    return {
        "location_name": _none(overview.get("locationName")),
        "currency": _none(overview.get("priceUnit")),
        "average_price": _float(overview.get("priceAverage") or investor.get("averagePrice")),
        "average_area": _float(overview.get("areaAverage") or investor.get("averageArea")),
        "average_price_per_area": _float(investor.get("averagePricePerArea")),
        "price_difference_pct": _float(overview.get("priceDifference")),
        "area_difference_pct": _float(overview.get("areaDifference")),
        "is_cheaper": _bool(overview.get("cheaper")),
        "is_smaller": _bool(overview.get("smaller")),
    }


def _insight_reviews(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        out.append({"user_name": _none(row.get("user_name")), "date": _none(row.get("date")),
                    "language": _none(row.get("language")), "body": _none(row.get("body")),
                    "score": _float(_dict(row.get("scores")).get("overall_score"))})
    return out or None


def _location_insight(block, country):
    block = _dict(block)
    if not block:
        return None
    return {
        "id": _int(block.get("communityId")),
        "name": _none(block.get("name")),
        "parent_name": _none(block.get("parentLocationName")),
        "insights_link": refs.absolute(country, _none(block.get("insightsUrl"))),
        "image": _none(block.get("imageUrl")),
        "active_listings": _int(block.get("activeListings")),
        "buildings_count": _int(block.get("numberOfBuildings")),
        "average_price": _float(block.get("avgPrice")),
        "price_min": _float(block.get("priceMin")),
        "price_max": _float(block.get("priceMax")),
        "size_min": _float(block.get("sizeRangeMin")),
        "size_max": _float(block.get("sizeRangeMax")),
        "available_bedrooms": [_int(b) for b in _list(block.get("availableBedrooms")) if _int(b) is not None] or None,
        "property_types": block.get("propertyTypes") or None,
        "score": _float(block.get("overallScore")),
        "score_breakdown": {k: _float(v) for k, v in _dict(block.get("scoreBreakdown")).items()} or None,
        "reviews_count": _int(block.get("reviewsCount")),
        "reviews": _insight_reviews(block.get("reviews")),
    }


def _mortgage_products(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        out.append({"residency_status": _none(row.get("residencyStatus")), "interest_rate": _float(row.get("interestRate")),
                    **{k: v for k, v in row.items() if k not in ("residencyStatus", "interestRate")}})
    return out or None


def parse_property_page(page_html, country=refs.DEFAULT_COUNTRY):
    """The PLP page -> the full listing record (card fields + everything the
    page adds). Returns None when the page carries no property."""
    props = page_props(page_html)
    prop = _dict(_dict(props.get("propertyResult")).get("property"))
    if not prop.get("id"):
        return None
    record = parse_property_card(prop, country)
    rera = _dict(prop.get("rera"))
    images = _dict(prop.get("images"))
    ppa = _dict(prop.get("price_per_area"))
    licenses = [{"type": _none(l.get("license_type")), "number": _none(l.get("license_number")),
                 "link": _none(l.get("license_url"))} for l in _list(prop.get("licenses")) if isinstance(l, dict)]
    record.update({
        "images": _full_images(images.get("property")) if images else record["images"],
        "community_images": _full_images(images.get("community")),
        "tower_images": _full_images(images.get("tower")),
        "floor_plans": [_none(x) if not isinstance(x, dict) else x for x in _list(prop.get("floor_plans"))] or None,
        "price_per_sqft": _float(ppa.get("price")) or record["price_per_sqft"],
        "price_per_area": {"price": _float(ppa.get("price")), "unit": _none(ppa.get("unit")),
                           "built_up_area": _float(ppa.get("built_up_area")), "plot": _float(ppa.get("plot"))} if ppa else None,
        "built_up_area": _float(prop.get("built_up_area")),
        "plot_size": _float(prop.get("plot_size")),
        "zone_name": _none(prop.get("zone_name")),
        "mortgage_cashback": _float(prop.get("mortgage_cashback")),
        "is_luxe": _bool(prop.get("is_luxe")),
        "is_upgraded": _bool(prop.get("is_upgraded")),
        "is_extended": _bool(prop.get("is_extended")),
        "is_landscaped": _bool(prop.get("is_landscaped")),
        "is_pay_monthly": _bool(_dict(prop.get("rnpm")).get("enabled")),
        "permit": {
            "number": _none(rera.get("number")) or record["permit_number"],
            "validation_link": _none(rera.get("permit_validation_url")),
            "authority_name": _none(rera.get("authority_name")),
            "issued_license_number": _none(rera.get("issued_license_number")),
        } if rera else None,
        "licenses": licenses or None,
        "property_details": _detail_rows(prop.get("property_details")),
        "regulatory_details": _detail_rows(prop.get("regulatory_details")),
        "agent": _detail_agent(prop.get("agent"), country),
        "company": _detail_broker(prop.get("broker") or prop.get("client"), country),
        "similar_transactions": _similar_transactions(prop.get("similar_price_transactions")),
        "price_trends": _price_trends(props.get("priceTrendsData")),
        "price_comparison": _price_comparison(props.get("priceComparisonsData")),
        "location_insights": {
            "building": _location_insight(_dict(props.get("locationInsightsData")).get("building"), country),
            "community": _location_insight(_dict(props.get("locationInsightsData")).get("community"), country),
        } if props.get("locationInsightsData") else None,
        "mortgage_products": _mortgage_products(props.get("mortgageProducts")),
        "mortgage_rate": _float(props.get("mortgageRate")),
    })
    record.pop("permit_number", None)
    return record


def parse_price_trends(payload):
    return _price_trends(payload)


# ---- agents / brokerages (pf-b2c-customer, camelCase) ------------------------------------------

def _image_link(image):
    """An agent / broker image object -> one URL (desktop, then any)."""
    if isinstance(image, str):
        return _none(image)
    links = _dict(_dict(image).get("links"))
    for key in ("desktop", "desktop2x", "agentCard", "propertyCard", "mobile"):
        if _none(links.get(key)):
            return links[key]
    for value in links.values():
        if _none(value):
            return value
    return None


def _claimed_transactions(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        loc = _dict(row.get("location"))
        out.append({
            "deal_type": _none(row.get("dealType")),
            "price": _float(row.get("price")),
            "date": _date(row.get("date")),
            "property_type": _none(row.get("propertyType")),
            "bedrooms": _int(row.get("bedroom")),
            "location": {"community": _none(loc.get("community")), "tower": _none(loc.get("tower")),
                         "path": [int(p) for p in str(loc.get("path") or "").split(".") if p.isdigit()] or None},
        })
    return out or None


def parse_agent(agent, country=refs.DEFAULT_COUNTRY):
    """A pf-b2c-customer agent row / profile -> an agent record."""
    agent = _dict(agent)
    aid = _int(agent.get("id"))
    broker = _dict(agent.get("broker"))
    bid = _int(broker.get("id") or broker.get("clientId"))
    nationality = _dict(agent.get("nationality"))
    distribution = _dict(agent.get("ratingDistribution"))
    compliances = {_none(c.get("type")): _none(c.get("value")) for c in _list(agent.get("compliances")) if isinstance(c, dict)}
    return {
        "id": aid,
        "name": _none(agent.get("name")),
        "link": refs.agent_link(country, _none(agent.get("slug")), aid) if aid else None,
        "slug": _none(agent.get("slug")),
        "image": _image_link(agent.get("image")),
        "position": _none(agent.get("position")),
        "bio": _none(agent.get("bio")),
        "is_super_agent": _bool(agent.get("superagent")),
        "is_verified": _bool(agent.get("verified")),
        "email": _none(agent.get("email")),
        "phone": _none(agent.get("phone")),
        "whatsapp": _none(agent.get("whatsappPhone")),
        "linkedin": _none(agent.get("linkedinAddress")),
        "nationality": {"code": _none(nationality.get("code")), "name": _none(nationality.get("name"))} if nationality else None,
        "languages": [_none(l.get("name")) if isinstance(l, dict) else _none(l) for l in _list(agent.get("languages"))] or None,
        "license_number": _none(agent.get("licenseNumber")) or compliances.get("brn"),
        "licenses": {k: v for k, v in compliances.items() if k} or None,
        "experience_since": _int(agent.get("experienceSince")),
        "response_time_minutes": _int(agent.get("avgWhatsappResponseTime")),
        "ranking": _float(agent.get("ranking")),
        "listing_quality": _int(agent.get("medianListingQuality")),
        "listings": {
            "total": _int(agent.get("totalProperties")),
            "residential_sale": _int(agent.get("propertiesResidentialForSaleCount")),
            "residential_rent": _int(agent.get("propertiesResidentialForRentCount")),
            "commercial_sale": _int(agent.get("propertiesCommercialForSaleCount")),
            "commercial_rent": _int(agent.get("propertiesCommercialForRentCount")),
        },
        "rating": {
            "average": _float(agent.get("averageRating")),
            "count": _int(agent.get("reviewCount")) or 0,
            "distribution": {str(i): _int(distribution.get(f"score{i}")) or 0 for i in range(1, 6)} if distribution else None,
        },
        "transactions": {
            "count": _int(agent.get("transactionsCount")),
            "is_visible": _bool(agent.get("isTransactionsVisible")),
            "claimed_sales": _int(agent.get("claimedTransactionsSale")),
            "claimed_rentals": _int(agent.get("claimedTransactionsRent")),
            "deal_volume": _float(agent.get("claimedTransactionsDealVolume")),
            "sale_total": _float(agent.get("claimedTransactionsSaleTotalAmount")),
            "rent_total": _float(agent.get("claimedTransactionsRentTotalAmount")),
            "sale_average": _float(agent.get("claimedTransactionsSaleAVGAmount")),
            "rent_average": _float(agent.get("claimedTransactionsRentAVGAmount")),
            "currency": refs.currency(country),
            "list": _claimed_transactions(agent.get("claimedTransactionsList")),
        },
        "top_locations": [{"id": _int(l.get("id")), "name": _none(l.get("name"))} for l in _list(agent.get("topLocations")) if isinstance(l, dict)] or None,
        "award_image": _none(agent.get("superAgentAwardImageUrl")),
        "company": {
            "id": bid,
            "name": _none(broker.get("name")),
            "link": refs.company_link(country, _none(broker.get("slug")), bid) if bid else None,
            "logo": _image_link(broker.get("logo")),
            "address": _none(broker.get("address")),
            "location": _none(broker.get("location")),
        } if broker else None,
    }


def parse_company(broker, country=refs.DEFAULT_COUNTRY):
    """A pf-b2c-customer brokerage row / profile -> a company record."""
    broker = _dict(broker)
    bid = _int(broker.get("id") or broker.get("clientId"))
    return {
        "id": bid,
        "name": _none(broker.get("name")),
        "link": refs.company_link(country, _none(broker.get("urlSlug") or broker.get("slug")), bid) if bid else None,
        "slug": _none(broker.get("urlSlug") or broker.get("slug")),
        "logo": _image_link(broker.get("logo")),
        "description": _none(broker.get("description")),
        "email": _none(broker.get("email")),
        "phone": _none(broker.get("phone")),
        "address": _none(broker.get("address")),
        "location": {"id": _int(broker.get("locationId")), "name": _none(broker.get("location"))}
        if (broker.get("location") or broker.get("locationId")) else None,
        "license": {"number": _none(broker.get("licenseNumber")), "authority": _none(broker.get("licenseLabel"))}
        if (broker.get("licenseNumber") or broker.get("licenseLabel")) else None,
        "type": _none(broker.get("clientType")),
        "is_verified": _bool(broker.get("isVerified")),
        "ranking": _float(broker.get("ranking")),
        "listings": {
            "total": _int(broker.get("totalProperties")),
            "residential_sale": _int(broker.get("propertiesResidentialForSaleCount")),
            "residential_rent": _int(broker.get("propertiesResidentialForRentCount")),
            "commercial_sale": _int(broker.get("propertiesCommercialForSaleCount")),
            "commercial_rent": _int(broker.get("propertiesCommercialForRentCount")),
        },
        "agents_count": _int(broker.get("totalAgents")),
        "super_agents_count": _int(broker.get("totalSuperAgents")),
        "transactions_count": _int(broker.get("transactionsCount")),
        "awards": [_none(a) if not isinstance(a, dict) else (_none(a.get("image") or a.get("url")) or a) for a in _list(broker.get("awards"))] or None,
        "branches": {"is_main_branch": _bool(broker.get("isMainBranch")), "total": _int(broker.get("totalBranches")),
                     "parent_id": _int(broker.get("parentId")) or None},
    }


# ---- new projects / developers (bilbo) --------------------------------------------------------

def _media_links(items, variant=None):
    """bilbo media list -> [{"link", "big", "thumbnail"}] (or plain links)."""
    out = []
    for item in _list(items):
        item = _dict(item)
        src = _none(item.get("src"))
        if not src:
            continue
        variants = _dict(item.get("variants"))
        out.append({"link": src, "big": _none(variants.get("big")), "thumbnail": _none(variants.get("thumbnail") or variants.get("small"))})
    return out or None


def _first_link(items):
    links = _media_links(items)
    return links[0]["link"] if links else None


def _communication(block):
    block = _dict(block)
    direct, lead = _dict(block.get("direct")), _dict(block.get("lead"))
    phones = [_none(direct.get("primary_phone_number"))] + [_none(p) for p in _list(direct.get("additional_phone_numbers"))]
    emails = [_none(direct.get("primary_email"))] + [_none(e) for e in _list(direct.get("additional_emails"))]
    whatsapp = _dict(block.get("whatsapp_links"))
    return {
        "phone": phones[0],
        "phones": [p for p in phones if p] or None,
        "email": emails[0],
        "emails": [e for e in emails if e] or None,
        "lead_phone": _none(lead.get("primary_phone_number")),
        "lead_email": _none(lead.get("primary_email")),
        "website": _none(block.get("website")),
        "whatsapp_link": _en(whatsapp) if whatsapp else None,
    }


def _phases(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        out.append({
            "title": _en(row.get("title")),
            "key": _none(row.get("phase_key")),
            "group": _none(row.get("phase_group_key")),
            "milestone": _none(row.get("mile_stone")),
            "progress_pct": _float(row.get("progress_percentage")),
            "estimated_at": _date(row.get("estimated_at")),
            "estimated_at_type": _none(row.get("estimated_at_type")),
            "transitioned_at": _date(row.get("transitioned_at")),
            "is_current": _bool(row.get("current")),
        })
    return out or None


def _payment_plans(rows):
    """phases_per_category.payment -> plans grouped by title with their milestones."""
    plans = {}
    for row in _list(rows):
        row = _dict(row)
        title = _en(row.get("title")) or "Payment plan"
        plan = plans.setdefault(title, {"name": title, "milestones": []})
        plan["milestones"].append({
            "stage": _none(row.get("phase_group_key")),
            "kind": _none(row.get("phase_key")),
            "percentage": _float(row.get("progress_percentage")),
            "milestone": _none(row.get("mile_stone")),
            "estimated_at": _date(row.get("estimated_at")),
            "is_current": _bool(row.get("current")),
        })
    for plan in plans.values():
        plan["total_pct"] = round(sum(m["percentage"] or 0 for m in plan["milestones"]), 2)
    return list(plans.values()) or None


def _units(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        area = _float(row.get("area"))
        out.append({
            "id": _none(row.get("id")),
            "title": _en(row.get("title")),
            "layout_type": _none(row.get("layout_type")),
            "property_type": _en(row.get("property_type")),
            "description": _text(_en(row.get("description"))),
            "bedrooms": _int(row.get("bedrooms")),
            "bathrooms": _int(row.get("bathrooms")),
            "area": {"value": area, "unit": "sqm"} if area else None,
            "starting_price": _float(row.get("starting_price")),
            "view": _none(row.get("view")),
            "stock_status": _none(row.get("stock_status")),
            "floor_plans": _media_links(_dict(row.get("media")).get("floor_plan")),
        })
    return out or None


def _bilbo_location(loc, country):
    loc = _dict(loc)
    if not loc:
        return None
    point = None
    for feature in _list(_dict(loc.get("geo_json")).get("features")):
        geometry = _dict(_dict(feature).get("geometry"))
        coords = _list(geometry.get("coordinates"))
        if geometry.get("type") == "Point" and len(coords) == 2:
            point = {"lat": _float(coords[1]), "lon": _float(coords[0])}
            break
    tree = []
    for node in _list(loc.get("location_tree")):
        node = _dict(node)
        tree.append({"id": _int(node.get("id")), "name": _en(node.get("name")), "type": _location_type(node.get("type"))})
    return {
        "id": _int(loc.get("id")),
        "name": _en(loc.get("name")),
        "full_name": _en(loc.get("full_name")),
        "type": _location_type(loc.get("type")),
        "slug": _none(loc.get("slug")),
        "level": _int(loc.get("level")),
        "path": [int(p) for p in str(loc.get("path") or "").split(".") if p.isdigit()] or None,
        "coordinates": point,
        "tree": tree or None,
    }


def parse_developer(dev, country=refs.DEFAULT_COUNTRY, brief=False):
    """A bilbo developer record -> a developer record (brief = the slice a
    project card carries)."""
    dev = _dict(dev)
    if not dev:
        return None
    phases = _dict(dev.get("construction_phase"))
    out = {
        "id": _none(dev.get("id")),
        "name": _en(dev.get("name")),
        "name_ar": _ar(dev.get("name")),
        "slug": _none(dev.get("slug")),
        "link": refs.developer_link(country, _none(dev.get("slug"))) if _bool(dev.get("dev_page_enabled")) is not False else None,
        "logo": _first_link(_dict(dev.get("media")).get("logo")) or _first_link(_dict(dev.get("media")).get("gallery")),
        "company_id": _int(dev.get("pf_client_id")),
        "license_number": _none(dev.get("license_number")),
        "established_since": _date(dev.get("established_since")),
        "contact": _communication(dev.get("communication")),
        "projects": {
            "online": _int(dev.get("num_projects_online")),
            "delivered": _int(dev.get("num_projects_delivered")),
            "by_phase": {k: _int(v) for k, v in phases.items()} or None,
        },
    }
    if brief:
        return out
    out.update({
        "description": _text(_en(dev.get("description"))),
        "headquarters_country": _none(dev.get("hq_country")),
        "operation_countries": [_none(c) for c in _list(dev.get("operation_countries")) if _none(c)] or None,
        "average_building_weeks": _int(dev.get("average_building_weeks")),
        "building_types": [_none(b) for b in _list(dev.get("building_types")) if _none(b)] or None,
        "development_classes": [_none(c) for c in _list(dev.get("development_classes")) if _none(c)] or None,
        "gallery": _media_links(_dict(dev.get("media")).get("gallery")),
        "has_developer_page": _bool(dev.get("dev_page_enabled")),
    })
    by_location = {}
    for lid, counts in _dict(dev.get("construction_phase_per_location")).items():
        by_location[str(lid)] = {k: _int(v) for k, v in _dict(counts).items()}
    out["projects"]["by_city"] = by_location or None
    return out


def parse_project(project, country=refs.DEFAULT_COUNTRY, brief=False):
    """A bilbo project (search card or data.project) -> a project record. The
    search card already carries the full record; `brief` trims units /
    faqs / descriptions for list responses."""
    project = _dict(project)
    if not project:
        return None
    media = _dict(project.get("media"))
    phases = _dict(project.get("phases_per_category"))
    units = _list(project.get("units"))
    bedrooms = sorted({_int(u.get("bedrooms")) for u in units if isinstance(u, dict) and _int(u.get("bedrooms")) is not None})
    unit_types = sorted({_en(_dict(u).get("property_type")) for u in units if _en(_dict(u).get("property_type"))})
    slug = _none(project.get("slug"))
    out = {
        "id": _none(project.get("id")),
        "name": _en(project.get("title")),
        "name_ar": _ar(project.get("title")),
        "slug": slug,
        "link": refs.project_link(country, slug),
        "developer": parse_developer(project.get("developer"), country, brief=True),
        "location": _bilbo_location(project.get("location"), country),
        "project_type": _none(project.get("project_type")),
        "property_types": unit_types or None,
        "bedrooms": bedrooms or None,
        "starting_price": _float(project.get("starting_price")),
        "effective_price": _float(project.get("effective_price")),
        "min_resale_price": _float(project.get("min_resale_price")),
        "currency": refs.currency(country),
        "ownership_type": _none(project.get("ownership_type")),
        "dld_id": _none(project.get("dld_id")),
        "construction": {
            "phase": _none(project.get("construction_phase_key")),
            "completion_date": _date(project.get("construction_completed_date")),
            "progress_pct": _float(project.get("construction_progress")),
            "last_inspection_date": _date(project.get("last_inspection_date")),
            "phases": _phases(phases.get("construction")),
        },
        "sales": {
            "phase": _none(project.get("sales_phase_key")),
            "start_date": _date(project.get("sales_start_date")),
            "phases": _phases(phases.get("sales")),
        },
        "payment_plans": _payment_plans(phases.get("payment")),
        "has_post_handover_payment_plan": any((_dict(r).get("phase_group_key") or "") == "post_handover" for r in _list(phases.get("payment"))) or False,
        "units_count": len(units),
        "hotness_level": _int(project.get("hotness_level")),
        "has_active_campaign": _bool(project.get("has_active_campaign")),
        "campaign_type": _none(project.get("campaign_type")),
        "logo": _first_link(media.get("logo")),
        "image": _first_link(media.get("gallery")) or _first_link(media.get("mobile_image")),
        "contact": _communication(project.get("communication")),
    }
    if brief:
        out["amenities"] = [_en(_dict(a).get("name")) for a in _list(project.get("amenities")) if _en(_dict(a).get("name"))] or None
        return out
    out.update({
        "description": _text(_en(project.get("description"))),
        "master_plan_description": _text(_en(project.get("master_plan_description"))),
        "units": _units(units),
        "amenities": [{"name": _en(_dict(a).get("name")), "category": _none(_dict(a).get("category")), "slug": _none(_dict(a).get("slug"))}
                      for a in _list(project.get("amenities")) if _en(_dict(a).get("name"))] or None,
        "faqs": [{"question": _en(_dict(f).get("question")), "answer": _text(_en(_dict(f).get("answer")))}
                 for f in _list(project.get("faqs")) if _en(_dict(f).get("question"))] or None,
        "media": {
            "gallery": _media_links(media.get("gallery")),
            "brochures": [m["link"] for m in _media_links(media.get("brochure")) or []] or None,
            "master_plans": _media_links(media.get("master_plan")),
            "logo": _first_link(media.get("logo")),
        },
        "permits": [p for p in _list(project.get("permits")) if p] or None,
        "inspections": [i for i in _list(project.get("inspections")) if i] or None,
        "buildings": [b for b in _list(project.get("buildings")) if b] or None,
        "exposure_status": _none(project.get("ad_campaigns_exposure_status")),
    })
    return out


def parse_projects(payload, country=refs.DEFAULT_COUNTRY):
    """bilbo search payload -> {"results", "total", "pages", "page", "price_range", "locations", "aggregation_links"}."""
    payload = _dict(payload)
    data, meta = _dict(payload.get("data")), _dict(payload.get("meta"))
    pagination = _dict(meta.get("pagination"))
    bracket = _dict(data.get("price_bracket"))
    return {
        "results": [parse_project(p, country, brief=True) for p in _list(data.get("projects")) if isinstance(p, dict)],
        "total": _int(meta.get("count")),
        "pages": _int(pagination.get("total")),
        "page": _int(pagination.get("page")),
        "price_range": {"min": _float(bracket.get("min")), "max": _float(bracket.get("max"))} if bracket else None,
        "locations": [{"id": _int(l.get("id")), "name": _none(l.get("name")), "type": _location_type(l.get("type"))}
                      for l in _list(data.get("locations")) if isinstance(l, dict)] or None,
        "popular_locations": [{"id": _int(l.get("id")), "name": _none(l.get("name")), "slug": _none(l.get("slug")),
                               "city_slug": _none(l.get("city_slug")), "projects_count": _int(l.get("count"))}
                              for l in _list(data.get("aggregation_links")) if isinstance(l, dict)] or None,
    }


def parse_developers(payload, country=refs.DEFAULT_COUNTRY):
    payload = _dict(payload)
    data, meta = _dict(payload.get("data")), _dict(payload.get("meta"))
    pagination = _dict(meta.get("pagination"))
    return {
        "results": [parse_developer(d, country) for d in _list(data.get("developers")) if isinstance(d, dict)],
        "total": _int(meta.get("count")),
        "pages": _int(pagination.get("total")),
        "page": _int(pagination.get("page")),
    }


# ---- transactions (DLD) ------------------------------------------------------------------------

def parse_transaction(row, offering_type_id=1, country=refs.DEFAULT_COUNTRY):
    row = _dict(row)
    kind = "rented" if _int(offering_type_id) == 2 else "sold"
    return {
        "id": _none(row.get("id")),
        "type": kind,
        "date": _date(row.get("transaction_date")),
        "status": _none(row.get("status")),
        "completion_status": _slug_label(row.get("completion_status")),
        "price": {"amount": _float(row.get("price")), "currency": refs.currency(country)},
        "price_per_sqft": _float(row.get("price_per_sqft")),
        "property": {
            "id": _int(row.get("property_id")),
            "number": _none(row.get("property_number")),
            "type": _none(row.get("property_type")),
            "bedrooms": _int(row.get("bedrooms")),
            "size": _float(row.get("property_size")),
            "built_up_area": _float(row.get("builtup_area")),
            "plot_area": _float(row.get("plot_area")),
            "balcony_area": _float(row.get("balcony_area")),
            "unit": "sqft",
        },
        "location": {
            "id": _int(row.get("location_id")),
            "name": _none(row.get("location_name")),
            "community": _none(row.get("high_level_location_name")),
            "parent_name": _none(row.get("location_path_name")),
            "slug": _none(row.get("location_slug")),
            "coordinates": _coordinates(row.get("coordinates")),
        },
        "developer_name": _none(row.get("developer_name")),
        "sold_by": _none(row.get("sold_by")),
        "contract": {
            "start_date": _date(row.get("contract_start_date")),
            "end_date": _date(row.get("contract_end_date")),
            "duration_months": _int(row.get("contract_duration")),
            "status": _none(row.get("contract_status")),
            "ejari_id": _none(row.get("ejari_id")),
        } if kind == "rented" or row.get("contract_start_date") else None,
        "previous": {
            "price": _float(row.get("previous_price")),
            "date": _date(row.get("previous_transaction_date")),
            "contract_duration_months": _int(row.get("previous_contract_duration_months")),
            "price_change_pct": _float(row.get("price_change_pct")),
            "months_since": _int(row.get("months_since_previous")),
        } if row.get("previous_price") is not None or row.get("previous_transaction_date") else None,
        "rental_yield_pct": _float(row.get("rental_yield_pct")),
        "is_bulk_deal": _bool(row.get("bulk_transaction")),
        "bulk_deal": {"id": _none(row.get("bulk_deal_id")), "size": _int(row.get("bulk_deal_size"))} if _bool(row.get("bulk_transaction")) else None,
    }


def _trend_row(row, prefix):
    row = _dict(row)
    out = {
        "period": _none(row.get("period")),
        "is_partial": _bool(row.get("partial")),
        "volume": _int(row.get("volume")),
        "average_price": _float(row.get(f"{prefix}_avg_price")),
        "average_price_per_sqft": _float(row.get(f"{prefix}_avg_price_per_sqft")),
    }
    if prefix == "sale":
        out.update({
            "p25_price": _float(row.get("sale_p25_price")), "median_price": _float(row.get("sale_median_price")),
            "p75_price": _float(row.get("sale_p75_price")),
            "p25_price_per_sqft": _float(row.get("sale_p25_price_per_sqft")),
            "median_price_per_sqft": _float(row.get("sale_median_price_per_sqft")),
            "p75_price_per_sqft": _float(row.get("sale_p75_price_per_sqft")),
        })
    else:
        for contract in ("new", "renew"):
            label = "new_contracts" if contract == "new" else "renewed_contracts"
            out[label] = {
                "average_price": _float(row.get(f"rent_{contract}_avg_price")),
                "p25_price": _float(row.get(f"rent_{contract}_p25_price")),
                "median_price": _float(row.get(f"rent_{contract}_median_price")),
                "p75_price": _float(row.get(f"rent_{contract}_p75_price")),
                "p25_price_per_sqft": _float(row.get(f"rent_{contract}_p25_price_per_sqft")),
                "median_price_per_sqft": _float(row.get(f"rent_{contract}_median_price_per_sqft")),
                "p75_price_per_sqft": _float(row.get(f"rent_{contract}_p75_price_per_sqft")),
            }
    return out


def parse_transactions_summary(summary, offering_type_id=1, country=refs.DEFAULT_COUNTRY):
    summary = _dict(summary)
    if not summary:
        return None
    prefix = "rent" if _int(offering_type_id) == 2 else "sale"
    content = _dict(summary.get("content"))
    by_bedrooms = []
    for row in _list(content.get("by_bedrooms")):
        row = _dict(row)
        by_bedrooms.append({"bedrooms": _int(row.get("bedrooms")), "count": _int(row.get("count")),
                            "average_price": _float(row.get(f"{prefix}_avg_price"))})
    by_type = []
    for row in _list(content.get("by_property_type")):
        row = _dict(row)
        by_type.append({"property_type_id": _int(row.get("property_type_id")), "property_type": _none(row.get("property_type")),
                        "count": _int(row.get("count")), "average_price": _float(row.get(f"{prefix}_avg_price"))})
    return {
        "currency": refs.currency(country),
        "average_price": _float(summary.get(f"{prefix}_avg_price")),
        "average_price_change_pct": _float(summary.get(f"{prefix}_avg_price_change")),
        "average_price_per_sqft": _float(summary.get(f"{prefix}_avg_price_per_sqft")),
        "average_price_per_sqft_change_pct": _float(summary.get(f"{prefix}_avg_price_per_sqft_change")),
        "p25_price": _float(summary.get(f"{prefix}_p25_price")),
        "median_price": _float(summary.get(f"{prefix}_median_price")),
        "p75_price": _float(summary.get(f"{prefix}_p75_price")),
        "median_price_per_sqft": _float(summary.get(f"{prefix}_median_price_per_sqft")),
        "price_range": {"min": _float(content.get(f"{prefix}_min_price")), "max": _float(content.get(f"{prefix}_max_price"))} if content else None,
        "roi_pct": _float(summary.get("roi")),
        "total_value": _float(summary.get("total_value")),
        "total_value_change_pct": _float(summary.get("total_value_change")),
        "volume_change_pct": _float(summary.get("volume")),
        "most_common_bedrooms": {"bedrooms": _int(content.get("most_common_bedrooms")), "pct": _float(content.get("most_common_bedrooms_pct"))}
        if content.get("most_common_bedrooms") is not None else None,
        "by_bedrooms": by_bedrooms or None,
        "by_property_type": by_type or None,
        "trend_interval": _none(summary.get("trend_interval")),
        "trend": [_trend_row(r, prefix) for r in _list(summary.get("trend"))] or None,
    }


def parse_transactions(attributes, offering_type_id=1, country=refs.DEFAULT_COUNTRY):
    attributes = _dict(attributes)
    links = _dict(attributes.get("internal_links"))
    results = [parse_transaction(r, offering_type_id, country) for r in _list(attributes.get("transactions")) if isinstance(r, dict)]
    total, pages = _int(attributes.get("total_items")), _int(attributes.get("total_pages"))
    if total is None and not results:
        total, pages = 0, 0
    return {
        "results": results,
        "page": _int(attributes.get("page")),
        "pages": pages,
        "total": total,
        "summary": parse_transactions_summary(attributes.get("summary"), offering_type_id, country),
        "similar_searches": [{"title": _none(l.get("title")), "link": refs.absolute(country, _none(l.get("link"))), "count": _int(l.get("count"))}
                             for l in _list(links.get("similar_searches")) if isinstance(l, dict)] or None,
    }


# ---- area insights page -----------------------------------------------------------------------

def _poi_items(rows, limit=10):
    out = []
    for row in _list(rows)[:limit]:
        row = _dict(row)
        driving, walking = _dict(row.get("driving")), _dict(row.get("walking"))
        out.append({
            "name": _en(row.get("name")),
            "kind": _none(row.get("rubric")),
            "coordinates": _coordinates({"lat": row.get("lat"), "lon": row.get("lon")}),
            "distance_m": _float(row.get("straightLineMeters")),
            "driving": {"distance_m": _float(driving.get("distanceMeters")), "duration_s": _float(driving.get("durationSeconds"))} if driving else None,
            "walking": {"distance_m": _float(walking.get("distanceMeters")), "duration_s": _float(walking.get("durationSeconds"))} if walking else None,
        })
    return out or None


def _poi(block):
    block = _dict(block)
    if not block:
        return None
    stats = _dict(block.get("stats"))
    schools = _dict(block.get("schoolsStats"))
    nearby = {}
    for key, rows in block.items():
        if key in ("stats", "schoolsStats") or not isinstance(rows, list):
            continue
        items = _poi_items(rows)
        if items:
            nearby[re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()] = items
    return {
        "counts": {re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower(): _int(v) for k, v in stats.items()} or None,
        "schools": {
            "count": _int(schools.get("count")),
            "average_annual_fees": _float(schools.get("averageAnnualFees")),
            "fee_range": {"min": _float(_dict(schools.get("feeRange")).get("min")), "max": _float(_dict(schools.get("feeRange")).get("max"))} if schools.get("feeRange") else None,
            "most_common_curriculum": _none(schools.get("mostCommonCurriculum")),
            "nearest": [{"curriculum": _none(s.get("curriculum")), "distance_m": _float(s.get("distanceMeters")),
                         "fee_range": {"min": _float(_dict(s.get("feeRange")).get("min")), "max": _float(_dict(s.get("feeRange")).get("max"))} if s.get("feeRange") else None,
                         "name": _en(s.get("name")) if s.get("name") else None}
                        for s in _list(schools.get("nearest")) if isinstance(s, dict)] or None,
        } if schools else None,
        "nearby": nearby or None,
    }


def _demographics(block):
    block = _dict(block)
    if not block:
        return None
    family = _dict(block.get("familyProfile"))
    renters = _dict(block.get("renterDemographics"))
    lifestyle = _dict(block.get("lifestyleCompatibility"))
    return {
        "renter_nationalities": [{"rank": _int(n.get("rank")), "country_code": _none(n.get("countryCode")), "name": _en(n.get("name")), "pct": _float(n.get("pct"))}
                                 for n in _list(renters.get("topNationalities")) if isinstance(n, dict)] or None,
        "lifestyle_fit": [{"key": _none(l.get("key")), "label": _en(l.get("label")), "pct": _float(l.get("pct"))}
                          for l in _list(lifestyle.get("data")) if isinstance(l, dict)] or None,
        "profile": {
            "primary_use": _none(family.get("primaryUse")),
            "price_bracket": _none(family.get("priceBracket")),
            "average_sale_price": _float(family.get("avgSalePrice")),
            "residential_count": _int(family.get("residentialCount")),
            "commercial_count": _int(family.get("commercialCount")),
            "dominant_property_type": _none(family.get("dominantPropertyType")),
            "dominant_bedrooms": _none(family.get("dominantBedroomCount")),
            "bedroom_distribution": [{"bedrooms": _none(b.get("bedrooms")), "count": _int(b.get("count"))} for b in _list(family.get("bedroomDistribution")) if isinstance(b, dict)] or None,
            "property_type_distribution": [{"type": _none(t.get("type")), "count": _int(t.get("count"))} for t in _list(family.get("propertyTypeDistribution")) if isinstance(t, dict)] or None,
        } if family else None,
    }


def _market(block, country):
    block = _dict(block)
    if not block:
        return None
    insights = _dict(block.get("marketInsights"))
    tenure = _dict(block.get("averageTenure"))
    offerings = {}
    for key in ("buy", "rent", "newProjects"):
        offer = _dict(insights.get(key))
        if not offer:
            continue
        overview = _dict(offer.get("overview"))
        rng = _dict(overview.get("priceRange"))
        props = _dict(offer.get("propertyInsights"))
        tx = _dict(_dict(_dict(_dict(offer.get("transactions")).get("data")).get("attributes")).get("summary"))
        offerings[re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()] = {
            "median_price": _float(overview.get("medianPrice")),
            "price_range": {"min": _float(rng.get("min")), "max": _float(rng.get("max")), "currency": _none(rng.get("currency"))} if rng else None,
            "listings_available": _int(_dict(props.get("listingsAvailable")).get("value")),
            "listings_added_30d": _int(_dict(props.get("addedLast30d")).get("value")),
            "verified_listings": {"count": _int(_dict(props.get("verifiedProperties")).get("count")), "pct": _float(_dict(props.get("verifiedProperties")).get("pct"))} if props.get("verifiedProperties") else None,
            "super_agent_listings": {"count": _int(_dict(props.get("superAgentProperties")).get("count")), "pct": _float(_dict(props.get("superAgentProperties")).get("pct"))} if props.get("superAgentProperties") else None,
            "transactions_summary": parse_transactions_summary(tx, 2 if key == "rent" else 1, country) if tx else None,
        }
    trends = _dict(block.get("priceTrends"))
    graph = _dict(trends.get("graph"))
    series = {}
    for frame, points in graph.items():
        rows = []
        for point in _list(points):
            point = _dict(point)
            rows.append({"date": _date(point.get("date")), "period": _none(point.get("period")), "bedrooms": _int(point.get("bedroom_id")),
                         "community_price": _float(point.get("community_price")), "tower_price": _float(point.get("tower_price"))})
        series[frame] = rows
    return {
        "average_tenure": {"days": _int(tenure.get("tenureDays")), "years": _float(tenure.get("tenureYears"))} if tenure else None,
        "offerings": offerings or None,
        "price_trends_per_sqft": series or None,
    }


def _area_cards(rows, country):
    out = []
    for row in _list(rows):
        row = _dict(row)
        rating = _dict(row.get("rating"))
        out.append({
            "id": _int(row.get("id")),
            "name": _none(row.get("name")),
            "insights_link": refs.absolute(country, _none(row.get("explore_url") or row.get("link"))),
            "search_link": refs.absolute(country, _none(row.get("search_url"))),
            "image": _none(row.get("image_url") or row.get("imageUrl")),
            "price_range": _none(row.get("price_range")),
            "listings_count": _int(row.get("properties_count")),
            "review": {"score": _float(rating.get("score") if rating else row.get("reviewScore")),
                       "count": _int(rating.get("count") if rating else row.get("reviewCount"))},
        })
    return out or None


def _house_prices(block):
    out = []
    for row in _list(_dict(block).get("data")):
        row = _dict(row)
        out.append({
            "category": refs.CATEGORY_NAMES.get(_int(row.get("category"))),
            "property_type": refs.PROPERTY_TYPE_NAMES.get(_int(row.get("propertyType"))),
            "property_type_id": _int(row.get("propertyType")),
            "bedrooms": _int(row.get("bedroomId")),
            "price": _float(row.get("price")),
        })
    return out or None


def _review_row(row):
    row = _dict(row)
    loc = _dict(row.get("location"))
    return {
        "id": _none(row.get("id")),
        "date": _datetime(row.get("review_date")),
        "user_name": _en(row.get("user_name")),
        "persona": _en(row.get("persona")),
        "language": _none(row.get("language")),
        "body": _en(row.get("body")),
        "body_ar": _ar(row.get("body")),
        "score": _float(_dict(row.get("scores")).get("overall_score")),
        "scores": {k: _float(v) for k, v in _dict(row.get("scores")).items() if k != "overall_score"} or None,
        "likes": _int(row.get("like_count")) or 0,
        "location": {"id": _int(loc.get("location_id")), "name": _en(loc.get("name"))} if loc else None,
    }


def parse_reviews(payload, children=False):
    """growth bridge location payload -> the reviews of the location itself
    (or, with children=True, of its sub-locations)."""
    payload = _dict(payload)
    block = _dict(payload.get("children" if children else "reviews"))
    aggregate = _dict(block.get("aggregate"))
    return {
        "location": {"id": _int(payload.get("location_id")), "name": _en(payload.get("name")),
                     "parent_id": _int(payload.get("parent_location_id")), "level": _int(payload.get("level"))},
        "categories": {k: _en(v) for k, v in _dict(payload.get("categories")).items()} or None,
        "score": _float(aggregate.get("overall_score")),
        "scores": {k: _float(v) for k, v in aggregate.items() if k != "overall_score"} or None,
        "total": _int(block.get("count")) or 0,
        "page": _int(block.get("page")),
        "pages": _int(block.get("pageCount")),
        "per_page": _int(block.get("pageSize")),
        "sort": _none(block.get("sort")),
        "results": [_review_row(r) for r in _list(block.get("reviews"))],
        "sublocations": [{"id": _int(l.get("location_id")), "name": _en(l.get("name"))} for l in _list(block.get("location_names")) if isinstance(l, dict)] or None,
    }


def parse_area_page(page_html, country=refs.DEFAULT_COUNTRY):
    """An area-insights page -> the area record. None when no location."""
    props = page_props(page_html)
    current = _dict(props.get("currentLocation"))
    details = _dict(props.get("details"))
    if not current.get("id") and not details.get("name"):
        return None
    dcl = _dict(props.get("dailyConvenienceLifestyle"))
    insights = _dict(props.get("insights"))
    reviews = _dict(props.get("locationReviews"))
    agg = _dict(_dict(reviews.get("reviews")).get("aggregate"))
    tree = _list(_dict(props.get("locationTree")).get("en"))
    top = _dict(props.get("topLocation"))
    lid = _int(current.get("id"))
    path = [int(p) for p in str(current.get("path") or "").split(".") if p.isdigit()]
    content = _dict(dcl.get("content"))
    poi_summaries = {re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower(): _en(_dict(v).get("body")) for k, v in _dict(content.get("poiSummaries")).items()}
    histogram = None
    for query in _list(_dict(props.get("dehydratedState")).get("queries")):
        key = _list(_dict(query).get("queryKey"))
        if key and key[0] == "marketPriceHistogram":
            rows = _list(_dict(_dict(query).get("state")).get("data"))
            histogram = [{"from": _float(_dict(r).get("step_start")), "count": _int(_dict(r).get("count"))} for r in rows] or None
    return {
        "id": lid,
        "name": _none(current.get("name")) or _none(details.get("name")),
        "type": _location_type(current.get("location_type") or props.get("pageType")),
        "level": _int(current.get("level")),
        "slug": _none(current.get("slug")),
        "link": _none(props.get("canonicalUrl")) or refs.absolute(country, _none(current.get("insights_url"))),
        "city": {"id": _int(props.get("cityId")), "name": _none(props.get("cityName")), "slug": _none(props.get("citySlug"))},
        "parent": {"id": _int(top.get("id")), "name": _none(top.get("name")), "insights_link": refs.absolute(country, _none(top.get("insights_url")))} if top else None,
        "parent_name": _none(current.get("path_name")),
        "path": path or None,
        "tree": [{"id": _int(n.get("id")), "name": _none(n.get("name")), "type": _location_type(n.get("type") or n.get("location_type")),
                  "insights_link": refs.absolute(country, _none(n.get("insights_url")))} for n in tree if isinstance(n, dict)] or None,
        "coordinates": _coordinates(details.get("coordinates")) or _coordinates(_dict(dcl.get("geo")).get("coordinates")),
        "title": _none(details.get("title")),
        "description": _text(details.get("description")) or _text(insights.get("neighbourhood")),
        "tags": [_none(t) for t in _list(details.get("tags") or insights.get("tags")) if _none(t)] or None,
        "key_facts": [_none(f) for f in _list(insights.get("keyFacts")) if _none(f)] or None,
        "video_link": _none(details.get("videoUrl")),
        "images": [{"category": _none(i.get("categoryName")), "link": _none(i.get("url")), "thumbnail": _none(i.get("thumbnailUrl"))}
                   for i in _list(details.get("images")) if isinstance(i, dict)] or None,
        "review": {
            "score": _float(details.get("reviewScore")) if details.get("reviewScore") is not None else _float(agg.get("overall_score")),
            "count": _int(details.get("reviewCount")) if details.get("reviewCount") is not None else _int(_dict(reviews.get("reviews")).get("count")),
            "scores": {k: _float(v) for k, v in agg.items() if k != "overall_score"} or None,
            "sublocation_reviews_count": _int(_dict(reviews.get("children")).get("count")),
        },
        "faqs": [{"question": _none(f.get("title")), "answer": _text(f.get("content"))} for f in _list(details.get("faqs") or insights.get("faqs")) if isinstance(f, dict)] or None,
        "guide": {
            "neighbourhood": _text(insights.get("neighbourhood")),
            "getting_around": _text(insights.get("gettingAround")),
            "car_access": _text(insights.get("gettingAroundCarAccess")),
            "public_transport": _text(insights.get("gettingAroundPublicTransport")),
            "location_and_amenities": _text(insights.get("locationAndAmenities")),
            "schools": _text(insights.get("schools")),
            "lifestyle_fit": _text(insights.get("lifestyleFit")),
            "market_buy": _text(insights.get("marketInsightsBuy")),
            "market_rent": _text(insights.get("marketInsightsRent")),
            "market_new_projects": _text(insights.get("marketInsightsNewProjects")),
            "transactions": _text(insights.get("transactions")),
            "property_types": [{"title": _none(p.get("title")), "content": _text(p.get("content"))} for p in _list(insights.get("properties")) if isinstance(p, dict)] or None,
            "places": [{"category": _none(p.get("category")), "content": _text(p.get("content"))} for p in _list(insights.get("pois")) if isinstance(p, dict)] or None,
            "poi_summaries": {k: v for k, v in poi_summaries.items() if v} or None,
        } if (insights or poi_summaries) else None,
        "house_prices": _house_prices(props.get("housePrices")),
        "price_histogram": histogram,
        "points_of_interest": _poi(dcl.get("poi")),
        "demographics": _demographics(dcl.get("demographics")),
        "market": _market(dcl.get("market"), country),
        "popular_buildings": {
            "buy": _area_cards(_dict(props.get("popularBuildings")).get("buyAreas"), country),
            "rent": _area_cards(_dict(props.get("popularBuildings")).get("rentAreas"), country),
        } if props.get("popularBuildings") else None,
        "popular_locations": _area_cards(props.get("popularLocations"), country),
        "similar_communities": [{"id": _int(c.get("id")), "name": _none(c.get("name")), "insights_link": refs.absolute(country, _none(c.get("link"))),
                                 "image": _none(c.get("imageUrl")), "review": {"score": _float(c.get("reviewScore")), "count": _int(c.get("reviewCount"))}}
                                for c in _list(_dict(props.get("similarCommunities")).get("data")) if isinstance(c, dict)] or None,
        "people_also_search": {
            "buy": _area_cards(_dict(props.get("peopleAlsoSearchAreas")).get("buyAreas"), country),
            "rent": _area_cards(_dict(props.get("peopleAlsoSearchAreas")).get("rentAreas"), country),
        } if props.get("peopleAlsoSearchAreas") else None,
        "listings": {
            "buy_link": refs.absolute(country, _none(_dict(props.get("properties")).get("seeAllLinkSale"))),
            "rent_link": refs.absolute(country, _none(_dict(props.get("properties")).get("seeAllLinkRent"))),
        } if props.get("properties") else None,
    }
