"""Offline tests for the Property Finder parsers and reference resolvers.

    python -m pytest property_finder/test_parsers.py -q

Fixtures are real www.propertyfinder.ae answers captured 2026-11-07 through
property_finder/fetch.py (property_finder/fixtures/, listed in parsers.py's
docstring). No network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from property_finder import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


# ---- refs ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("164588946", {"id": 164588946, "country": None}),
    (" 164588946 ", {"id": 164588946, "country": None}),
    ("https://www.propertyfinder.ae/en/plp/buy/villa-for-sale-dubai-the-springs-springs-8-164588946.html",
     {"id": 164588946, "country": "ae"}),
    ("https://www.propertyfinder.sa/en/plp/rent/x-52173408.html?utm=1", {"id": 52173408, "country": "sa"}),
    ("https://www.propertyfinder.ae/to/164588946/en", {"id": 164588946, "country": "ae"}),
    ("www.propertyfinder.ae/ar/plp/buy/x-164588946.html", {"id": 164588946, "country": "ae"}),
])
def test_resolve_property(value, expected):
    assert refs.resolve_property(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "https://example.com/en/plp/buy/x-1.html",
                                   "https://www.propertyfinder.ae/en/agent/nathan-blake-264476"])
def test_resolve_property_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_property(value)


def test_resolve_agent_and_company():
    assert refs.resolve_agent("264476") == {"id": 264476, "country": None}
    assert refs.resolve_agent("https://www.propertyfinder.ae/en/agent/nathan-blake-264476") == {"id": 264476, "country": "ae"}
    assert refs.resolve_company("4338") == {"id": 4338, "country": None}
    assert refs.resolve_company("https://www.propertyfinder.ae/en/broker/barnes-international-realty-v2-4338") == \
        {"id": 4338, "country": "ae"}
    # the partner app prints the id twice
    assert refs.resolve_company("https://www.propertyfinder.ae/en/broker/barnes-international-realty-v2-4338-4338") == \
        {"id": 4338, "country": "ae"}
    with pytest.raises(ValueError):
        refs.resolve_agent("https://www.propertyfinder.ae/en/broker/x-4338")
    with pytest.raises(ValueError):
        refs.resolve_company("barnes")


def test_resolve_project_and_developer():
    uuid = "d1294890-1250-48b7-99e3-4f34a371b967"
    assert refs.resolve_project(uuid) == {"uuid": uuid, "slug": None, "country": None}
    assert refs.resolve_project("emaar-properties/valia-tower") == {"uuid": None, "slug": "emaar-properties/valia-tower", "country": None}
    assert refs.resolve_project("https://www.propertyfinder.ae/en/new-projects/emaar-properties/valia-tower") == \
        {"uuid": None, "slug": "emaar-properties/valia-tower", "country": "ae"}
    with pytest.raises(ValueError):
        refs.resolve_project("valia-tower")
    with pytest.raises(ValueError):
        refs.resolve_project("https://www.propertyfinder.ae/en/new-projects/dev/emaar-properties")
    assert refs.resolve_developer("emaar-properties") == {"uuid": None, "slug": "emaar-properties", "country": None}
    assert refs.resolve_developer("https://www.propertyfinder.ae/en/new-projects/dev/emaar-properties") == \
        {"uuid": None, "slug": "emaar-properties", "country": "ae"}
    assert refs.resolve_developer("79ca4333-9975-4672-b05f-bb7329de75e9")["uuid"] == "79ca4333-9975-4672-b05f-bb7329de75e9"
    with pytest.raises(ValueError):
        refs.resolve_developer("1234")


@pytest.mark.parametrize("value,expected", [
    ("50", {"ids": [50], "slug": None, "city_slug": None, "query": None, "country": None}),
    ("50, 86", {"ids": [50, 86], "slug": None, "city_slug": None, "query": None, "country": None}),
    ("dubai marina", {"ids": None, "slug": None, "city_slug": None, "query": "dubai marina", "country": None}),
    ("https://www.propertyfinder.ae/en/search?c=1&l=50&l=86&ob=mr", {"ids": [50, 86], "slug": None, "city_slug": None, "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/area-insights/dubai/dubai-marina", {"ids": None, "slug": "dubai-marina", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/transactions/sold/dubai/dubai-marina-marina-gate?page=2",
     {"ids": None, "slug": "dubai-marina-marina-gate", "city_slug": "dubai", "query": None, "country": "ae", "deal": "sold"}),
    ("https://www.propertyfinder.ae/en/transactions/rented/dubai/1-bedroom-apartments-downtown-dubai-burj-khalifa-area-burj-khalifa",
     {"ids": None, "slug": "downtown-dubai-burj-khalifa-area-burj-khalifa", "city_slug": "dubai", "query": None, "country": "ae",
      "deal": "rented"}),
    # the "Hotel & Hotel Apartments" similar-search link of the transactions fixtures
    ("https://www.propertyfinder.ae/en/transactions/rented/dubai/hotels-hotel-apartments-dubai-marina",
     {"ids": None, "slug": "dubai-marina", "city_slug": "dubai", "query": None, "country": "ae", "deal": "rented"}),
    # a city page keeps its deal type too
    ("https://www.propertyfinder.ae/en/transactions/rented/dubai",
     {"ids": None, "slug": "dubai", "city_slug": "dubai", "query": None, "country": "ae", "deal": "rented"}),
    ("https://www.propertyfinder.ae/en/buy/dubai/properties-for-sale-dubai-marina.html", {"ids": None, "slug": "dubai-marina", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/buy/dubai/villas-for-sale-palm-jumeirah.html", {"ids": None, "slug": "palm-jumeirah", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/rent/dubai/apartments-for-rent-dubai-marina.html", {"ids": None, "slug": "dubai-marina", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/rent/dubai/properties-for-rent.html", {"ids": None, "slug": "dubai", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/building-reviews/dubai/dubai-marina-damac-heights.html",
     {"ids": None, "slug": "dubai-marina-damac-heights", "city_slug": "dubai", "query": None, "country": "ae"}),
    ("https://www.propertyfinder.ae/en/new-projects/lp/dubai/jumeirah-village-circle",
     {"ids": None, "slug": "jumeirah-village-circle", "city_slug": "dubai", "query": None, "country": "ae"}),
])
def test_resolve_location(value, expected):
    assert refs.resolve_location(value) == expected


def test_resolve_location_rejects():
    for value in ("", "https://example.com/?l=50", "https://www.propertyfinder.ae/en/agent/x-1", "x" * 121):
        with pytest.raises(ValueError):
            refs.resolve_location(value)


def test_link_builders():
    assert refs.agent_link("ae", "nathan-blake", 264476) == "https://www.propertyfinder.ae/en/agent/nathan-blake-264476"
    assert refs.company_link("sa", "x-4338", 4338) == "https://www.propertyfinder.sa/en/broker/x-4338"
    assert refs.company_link("ae", None, 4338) == "https://www.propertyfinder.ae/en/broker/4338"
    assert refs.absolute("ae", "/en/area-insights/dubai/dubai-marina") == "https://www.propertyfinder.ae/en/area-insights/dubai/dubai-marina"
    assert refs.absolute("ae", None) is None
    assert refs.currency("eg") == "EGP" and refs.site("qa") == "https://www.propertyfinder.qa"


# ---- helpers --------------------------------------------------------------------------------------

def test_number_helpers_keep_zero():
    assert P._int(0) == 0 and P._float(0) == 0 and P._int("0") == 0
    assert P._int(None) is None and P._int("") is None and P._int(True) is None
    assert P._float("1,234.50") == 1234.5 and P._float("157.37774976") == 157.3777
    assert P._date("2026-10-26T11:19:10Z") == "2026-10-26" and P._date("") is None and P._date("0001-01-01T00:00:00Z") is None
    assert P._text("<p>Hello&nbsp;<b>world</b></p><p>Next</p>") == "Hello world\n\nNext"
    assert P._text("line<br>two") == "line\ntwo" and P._text("") is None
    assert P._coordinates({"lat": 0, "lon": 0}) is None


# ---- search --------------------------------------------------------------------------------------

def test_parse_search_cards():
    parsed = P.parse_search(fixture("search_buy_dubai_marina_newest.json"))
    assert parsed["total"] == 3981 and parsed["pages"] == 160 and parsed["per_page"] == 25
    assert len(parsed["results"]) == 25            # the 5 promoted project cards ride beside the results
    assert len(parsed["promoted_projects"]) == 5
    assert all(r["listing_type"] == "property" for r in parsed["results"])
    card = parsed["results"][0]
    assert card["id"] == 170163909 and card["category"] == "buy"
    assert card["link"].startswith("https://www.propertyfinder.ae/en/plp/buy/")
    assert card["price"] == {"amount": 1150000, "currency": "AED", "period": None, "is_hidden": False}
    assert card["bedrooms"] == 1 and card["bathrooms"] == 2 and card["size"] == {"value": 778, "unit": "sqft"}
    assert card["furnished"] == "unfurnished" and card["completion_status"] == "completed"
    assert card["location"]["id"] and card["location"]["coordinates"]["lat"] > 24
    assert card["location_tree"][0]["type"] == "city"
    assert card["agent"]["link"].startswith("https://www.propertyfinder.ae/en/agent/")
    assert card["company"]["link"].startswith("https://www.propertyfinder.ae/en/broker/")
    assert card["contact"]["phone"] and card["contact"]["whatsapp_link"]
    assert card["images"] and card["images"][0]["medium"].startswith("https://")
    assert card["listed_date"].startswith("2026-")
    assert "listing_id" not in card and "ranking_factors" not in card
    promo = parsed["promoted_projects"][0]
    assert promo["listing_type"] == "project" and promo["link"].startswith("https://www.propertyfinder.ae/en/new-projects/")


def test_parse_search_rent_monthly():
    parsed = P.parse_search(fixture("search_rent_marina_2bed_monthly.json"))
    card = parsed["results"][0]
    assert card["category"] == "rent" and card["price"]["period"] == "monthly"
    assert card["furnished"] == "furnished"
    assert {"code": "BA", "name": "Balcony"} in card["amenities"]


def test_parse_search_empty_and_sa():
    empty = P.parse_search(fixture("search_no_match.json"))
    assert empty["results"] == [] and empty["total"] == 0 and empty["pages"] == 0
    sa = P.parse_search(fixture("search_sa_buy.json"), "sa")
    assert sa["results"][0]["price"]["currency"] == "SAR"
    assert sa["results"][0]["link"].startswith("https://www.propertyfinder.sa/")
    assert sa["results"][0]["agent"]["link"].startswith("https://www.propertyfinder.sa/en/agent/")


def test_parse_search_project_cards():
    parsed = P.parse_search(fixture("search_new_projects_cat5.json"))
    assert parsed["results"] == [] and len(parsed["promoted_projects"]) == 5
    card = parsed["promoted_projects"][0]
    assert card["name"] == "Podium Villas" and card["developer"]["name"] == "Nakheel"
    assert card["bedrooms"] == [2, 3, 4] and card["price_from"] == 5300000 and card["delivery_date"] == "2027-01-01"
    assert card["construction_phase"] == "under-construction" and card["agents"][0]["company"]["id"]


def test_parse_search_partial_payload():
    assert P.parse_search({})["results"] == []
    assert P.parse_search({"listings": [{"listing_type": "property", "property": {"id": "1"}}]})["results"][0]["id"] == 1
    assert P.parse_listing({"listing_type": "x"}) is None


# ---- property page -------------------------------------------------------------------------------

def test_parse_property_page_buy():
    record = P.parse_property_page(fixture("property_164588946_buy.html"))
    assert record["id"] == 164588946 and record["category"] == "buy" and record["property_type"] == "Villa"
    assert record["price"]["amount"] == 7649000 and record["price_per_sqft"] == 2127
    assert record["bedrooms"] == 3 and record["built_up_area"] == 2285 and record["plot_size"] == 3595
    assert len(record["images"]) == 26 and record["images"][0]["full"].startswith("https://")
    assert record["community_images"] and record["tower_images"] is None
    assert record["permit"]["validation_link"].startswith("https://trakheesi.dubailand.gov.ae/")
    assert record["permit"]["authority_name"] == "ARABIAN LIFESTYLE REALESTATE L.L.C"
    assert record["licenses"] == [{"type": "brn", "number": "46187", "link": None}]
    assert record["agent"]["rating"] == {"average": 5, "count": 4, "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 4}}
    assert record["agent"]["years_of_experience"] == 11 and record["agent"]["transactions_count"] == 5
    assert record["company"]["license_number"] == "26077" and record["company"]["agents_count"] == 73
    assert record["similar_transactions"]["buy"][0]["amount"] == 4999999
    assert record["price_trends"]["unit"] == "AED/Sqft" and len(record["price_trends"]["series"]["1Y"]) == 11
    assert record["price_trends"]["series"]["1Y"][0] == {"date": "2025-11-01", "period": "Nov 2025", "community_price": 2152, "tower_price": 2451}
    assert record["price_comparison"]["location_name"] == "The Springs" and record["price_comparison"]["is_cheaper"] is False
    assert record["location_insights"]["community"]["score"] == 4.4 and record["location_insights"]["community"]["reviews_count"] == 2
    assert record["location_insights"]["building"]["active_listings"] == 12
    assert record["mortgage_products"][0]["interest_rate"] == 4.24
    assert record["zone_name"] == "Al Thanayah Fourth" and record["mortgage_cashback"] == 17000
    assert record["is_high_demand"] is True and record["is_great_value"] is False
    assert record["property_details"][0] == {"id": "detail_property_type", "label": "Property Type", "value": "Villa", "format": "text"}
    assert any(r["id"] == "regulatory_broker_license" and r["value"] == "26077" for r in record["regulatory_details"])
    assert "permit_number" not in record


def test_parse_property_page_rent():
    record = P.parse_property_page(fixture("property_135146604_rent.html"))
    assert record["category"] == "rent" and record["price"] == {"amount": 10000, "currency": "AED", "period": "monthly", "is_hidden": False}
    assert record["available_from"] == "2024-03-06" and record["furnished"] == "furnished"
    assert record["link"].startswith("https://www.propertyfinder.ae/en/plp/rent/")


def test_parse_property_page_without_property():
    assert P.parse_property_page("<html><body>nothing</body></html>") is None
    assert P.parse_property_page('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>') is None


def test_parse_price_trends():
    trends = P.parse_price_trends(fixture("price_trends_4467_buy_3bed_villa.json"))
    assert trends["community_name"] == "The Springs" and trends["tower_name"] == "Springs 8"
    assert set(trends["series"]) == {"1Y", "2Y", "5Y"} and trends["series"]["5Y"][0]["period"] == "2022"
    assert P.parse_price_trends({}) is None


# ---- agents / companies ---------------------------------------------------------------------------

def test_parse_agent_profile():
    agent = P.parse_agent(fixture("agent_264476.json"))
    assert agent["id"] == 264476 and agent["name"] == "Nathan Blake"
    assert agent["link"] == "https://www.propertyfinder.ae/en/agent/nathan-blake-264476"
    assert agent["email"] is None and agent["phone"] is None          # the site publishes neither
    assert agent["nationality"] == {"code": "GB", "name": "United Kingdom"} and agent["languages"] == ["English"]
    assert agent["license_number"] == "46187" and agent["licenses"] == {"brn": "46187"}
    assert agent["experience_since"] == 2016 and agent["response_time_minutes"] == 19
    assert agent["listings"]["total"] == 7 and agent["listings"]["residential_sale"] == 7
    assert agent["rating"]["average"] == 5 and agent["rating"]["distribution"]["5"] == 4
    assert agent["transactions"]["claimed_sales"] == 5 and agent["transactions"]["deal_volume"] == 25230000
    assert agent["transactions"]["list"][0]["deal_type"] == "Sale" and agent["transactions"]["list"][0]["location"]["tower"] == "Springs 7"
    assert agent["top_locations"] == [{"id": 89, "name": "The Springs"}, {"id": 4466, "name": "Springs 7"}] or agent["top_locations"][0]["id"] == 89
    assert agent["company"]["id"] == 4338 and agent["company"]["link"] == "https://www.propertyfinder.ae/en/broker/barnes-international-realty-v2-4338"
    assert agent["image"].startswith("https://")


def test_parse_agent_rows():
    rows = fixture("agents_search_nathan.json")
    assert rows["totals"] == {"total": 19, "total_pages": 4, "page": 1}
    parsed = [P.parse_agent(r) for r in rows["rows"]]
    assert len(parsed) == 5 and all(p["id"] and p["link"] for p in parsed)
    filtered = fixture("agents_filtered_marina_rent_russian.json")
    assert all(P.parse_agent(r)["nationality"]["code"] == "RU" for r in filtered["rows"])
    assert fixture("agents_no_match.json") == {"rows": [], "totals": {"total": 0, "total_pages": 0, "page": 1}}
    assert P.parse_agent({})["id"] is None and P.parse_agent({})["company"] is None


def test_parse_company_profile():
    company = P.parse_company(fixture("brokerage_4338.json"))
    assert company["id"] == 4338 and company["name"] == "Barnes International Realty"
    assert company["link"] == "https://www.propertyfinder.ae/en/broker/barnes-international-realty-v2-4338"
    assert company["email"] == "danial@arabianestates.ae" and company["phone"] == "+971585566633"
    assert company["license"] == {"number": "26077", "authority": "RERA"}
    assert company["location"] == {"id": 1, "name": "Dubai"}
    assert company["listings"]["total"] >= 1000 and company["listings"]["residential_rent"] >= 400
    assert company["agents_count"] == 73 and company["super_agents_count"] == 70
    assert company["awards"][0].startswith("https://") and company["branches"]["is_main_branch"] is True
    assert company["logo"].startswith("https://")


def test_parse_company_rows():
    rows = fixture("brokerages_marina_most_listings.json")
    parsed = [P.parse_company(r) for r in rows["rows"]]
    assert [p["listings"]["total"] for p in parsed] == [8403, 6871, 4993]
    assert parsed[0]["link"] == "https://www.propertyfinder.ae/en/broker/white-co-real-estate-4372-4246"
    assert P.parse_company({})["id"] is None


# ---- projects / developers --------------------------------------------------------------------------

def test_parse_project_full():
    project = P.parse_project(fixture("project_valia_tower.json"))
    assert project["id"] == "d1294890-1250-48b7-99e3-4f34a371b967" and project["name"] == "Valia Tower"
    assert project["link"] == "https://www.propertyfinder.ae/en/new-projects/emaar-properties/valia-tower"
    assert project["developer"]["name"] == "Emaar Properties" and project["developer"]["license_number"] == "500353"
    assert project["developer"]["link"] == "https://www.propertyfinder.ae/en/new-projects/dev/emaar-properties"
    assert project["location"]["id"] == 19813 and project["location"]["coordinates"] == {"lat": 25.1947, "lon": 55.3592}
    assert project["location"]["tree"][0] == {"id": 1, "name": "Dubai", "type": "city"}
    assert project["starting_price"] == 2060000 and project["currency"] == "AED" and project["dld_id"] == "4448"
    assert project["construction"]["phase"] == "under_construction" and project["construction"]["completion_date"] == "2030-08-31"
    assert project["payment_plans"][0]["name"] == "Standard" and project["payment_plans"][0]["total_pct"] == 100
    assert project["units_count"] == 14 and project["units"][0]["bedrooms"] == 3
    assert project["units"][0]["area"] == {"value": 157.3777, "unit": "sqm"} and project["units"][0]["floor_plans"][0]["link"].startswith("https://")
    assert project["units"][0]["size"] == {"value": round(157.3777 * 10.7639, 2), "unit": "sqft"}
    assert project["bedrooms"] == [1, 2, 3, 4] and project["property_types"] == ["apartment", "villa"]
    assert project["amenities"][0]["name"] == "Indoor Swimming Pool"
    assert project["faqs"][0]["question"].startswith("Is Valia Tower") and "<" not in project["faqs"][0]["answer"]
    assert project["description"].startswith("Project Description") and "<p>" not in project["description"]
    assert project["media"]["brochures"][0].endswith(".pdf") and project["media"]["gallery"]
    assert project["contact"]["whatsapp_link"].startswith("https://wa.me/")


def test_unit_sizes_follow_the_storefront():
    # the project page shows raw x 10.7639: sqft on .ae, sqm elsewhere (2026-11-10)
    ae = P._units([{"area": 74.42, "bedrooms": 1}], "ae")[0]
    assert ae["area"] == {"value": 74.42, "unit": "sqm"} and ae["size"] == {"value": 801.05, "unit": "sqft"}
    eg = P._units([{"area": 2.88, "bedrooms": 0}], "eg")[0]
    assert eg["area"] == {"value": 31.0, "unit": "sqm"} and eg["size"] == {"value": 31.0, "unit": "sqm"}
    assert P._units([{"area": None}], "sa")[0]["area"] is None


def test_post_handover_flag_reads_after_handover():
    plan = {"phases_per_category": {"payment": [{"title": {"en": "Plan"}, "phase_group_key": "during_construction", "progress_percentage": 70},
                                                {"title": {"en": "Plan"}, "phase_group_key": "after_handover", "progress_percentage": 30}]}}
    assert P.parse_project(plan)["has_post_handover_payment_plan"] is True
    plan["phases_per_category"]["payment"].pop()
    assert P.parse_project(plan)["has_post_handover_payment_plan"] is False


def test_whatsapp_links_without_a_number_are_dropped():
    assert P._whatsapp_link("https://wa.me/?text=Hello") is None
    assert P._whatsapp_link("https://api.whatsapp.com/send?phone=&text=Hello") is None
    assert P._whatsapp_link("https://wa.me/971501234567?text=Hello") == "https://wa.me/971501234567?text=Hello"
    assert P._whatsapp_link("https://api.whatsapp.com/send?phone=+97144550887&text=Hi") == "https://api.whatsapp.com/send?phone=+97144550887&text=Hi"
    assert P._whatsapp_link(None) is None


def test_project_location_name_falls_back_to_english():
    loc = {"id": 5, "name": {"en": "سمو بوليفارد"}, "location_tree": [{"id": 1, "name": {"en": "Cairo"}, "type": "CITY"},
                                                                  {"id": 5, "name": {"en": "Sumou Boulebvard"}, "type": "TOWER"}]}
    assert P._bilbo_location(loc, "eg")["name"] == "Sumou Boulebvard"
    assert P._bilbo_location({"id": 7, "name": {"en": "Valia Tower"}}, "ae")["name"] == "Valia Tower"


def test_embedded_developer_drops_zero_project_counts():
    project = P.parse_project({"developer": {"name": {"en": "Emaar Properties"}, "slug": "emaar-properties", "num_projects_online": 0,
                                             "num_projects_delivered": 0, "construction_phase": {"completed": 0}}})
    assert project["developer"]["name"] == "Emaar Properties" and project["developer"]["projects"] is None
    assert P.parse_developer({"name": {"en": "Emaar"}, "num_projects_online": 214})["projects"]["online"] == 214


def test_parse_projects_search():
    parsed = P.parse_projects(fixture("projects_search_dubai_p1.json"))
    assert parsed["total"] == 2394 and parsed["pages"] == 240 and len(parsed["results"]) == 10
    assert parsed["price_range"] == {"min": 310000, "max": 330000000}
    assert parsed["locations"] == [{"id": 1, "name": "Dubai", "type": "city"}]
    assert parsed["popular_locations"][0]["name"] == "Jumeirah Village Circle"
    card = parsed["results"][0]
    assert card["name"] == "Podium Villas" and "units" not in card and "faqs" not in card
    assert card["developer"]["slug"] == "nakheel" and card["amenities"]
    assert P.parse_projects({"data": {}, "meta": {}})["results"] == []


def test_parse_developer():
    dev = P.parse_developer(fixture("developer_emaar.json"))
    assert dev["name"] == "Emaar Properties" and dev["slug"] == "emaar-properties"
    assert dev["link"] == "https://www.propertyfinder.ae/en/new-projects/dev/emaar-properties"
    assert dev["established_since"] == "1997-01-03" and dev["license_number"] == "500353"
    assert dev["projects"]["online"] == 214 and dev["projects"]["by_phase"]["under_construction"] == 157
    assert dev["projects"]["by_city"]["1"]["completed"] == 56
    assert dev["contact"]["email"] and dev["contact"]["whatsapp_link"].startswith("https://wa.me/")
    assert dev["description"].startswith("Emaar") and "<" not in dev["description"]
    assert dev["logo"].startswith("https://")
    listing = P.parse_developers(fixture("developers_p1.json"))
    assert listing["total"] == 960 and listing["pages"] == 96 and len(listing["results"]) == 10
    past = P.parse_developers(fixture("developers_past_end.json"))
    assert past["results"] == [] and past["total"] == 960 and past["page"] == 500


# ---- transactions ----------------------------------------------------------------------------------

def test_parse_transactions_sold():
    parsed = P.parse_transactions(fixture("transactions_marina_sold_1y_p1.json"), 1)
    assert parsed["total"] == 2150 and parsed["pages"] == 50 and len(parsed["results"]) == 10
    row = parsed["results"][0]
    assert row["type"] == "sold" and row["date"] == "2026-11-06" and row["price"] == {"amount": 2529548, "currency": "AED"}
    assert row["property"]["number"] == "1002" and row["property"]["bedrooms"] == 1 and row["property"]["balcony_area"] == 75.35
    assert row["location"]["id"] == 13378 and row["location"]["community"] == "Dubai Marina"
    assert row["contract"] is None and row["is_bulk_deal"] is False
    summary = parsed["summary"]
    assert summary["average_price"] > 2_000_000 and summary["roi_pct"] == 5.8816
    assert summary["by_bedrooms"][0]["bedrooms"] == 0           # studios keep their zero
    assert summary["by_property_type"][0]["property_type"] == "Apartment"
    assert summary["trend"][0]["period"] == "2025-11" and summary["trend"][0]["is_partial"] is True
    assert summary["trend"][0]["median_price"] and "new_contracts" not in summary["trend"][0]
    assert parsed["similar_searches"][0]["link"].startswith("https://www.propertyfinder.ae/en/transactions/")


def test_parse_transactions_rented():
    parsed = P.parse_transactions(fixture("transactions_marina_rented_filtered.json"), 2)
    row = parsed["results"][0]
    assert row["type"] == "rented" and row["contract"]["start_date"] == "2026-07-10" and row["contract"]["ejari_id"]
    assert row["rental_yield_pct"] == 6.94
    assert parsed["summary"]["trend"][0]["new_contracts"]["median_price"]


def test_parse_rental_contract_fields():
    row = fixture("transactions_marina_rented_filtered.json")["transactions"][0]
    tx = P.parse_transaction(row, 2)
    assert tx["contract"]["duration_months"] == 36 and tx["contract"]["term"] == "Long term"
    assert tx["contract"]["status"] == "New" and tx["contract"]["ejari_id"] == "608460267"
    assert tx["property"]["parking_spaces"] == 1 and tx["property"]["completion_year"] is None


def test_agent_rating_and_noise_fields():
    one_review = P.parse_agent({"id": 1, "averageRating": 0, "reviewCount": 1, "ratingDistribution": {"score5": 1},
                                "avgWhatsappResponseTime": -935, "experienceSince": 0})
    assert one_review["rating"]["average"] == 5.0 and one_review["rating"]["count"] == 1
    assert one_review["response_time_minutes"] is None and one_review["experience_since"] is None
    no_reviews = P.parse_agent({"id": 2, "averageRating": 0, "reviewCount": 0, "ratingDistribution": {"score5": 0}})
    assert no_reviews["rating"]["average"] is None
    rated = P.parse_agent({"id": 3, "averageRating": 4.4, "reviewCount": 7, "avgWhatsappResponseTime": 2, "experienceSince": 2019})
    assert rated["rating"]["average"] == 4.4 and rated["response_time_minutes"] == 2 and rated["experience_since"] == 2019


def test_company_address_and_dead_counts():
    company = P.parse_company({"id": 1144, "address": "Office G-05, Emaar Business Park, Dubai,", "transactionsCount": 0, "totalBranches": 0})
    assert company["address"] == "Office G-05, Emaar Business Park, Dubai"
    assert company["transactions_count"] is None and company["branches"]["total"] is None


def test_parse_transactions_empty():
    parsed = P.parse_transactions(fixture("transactions_unknown_location.json"), 1)
    assert parsed["results"] == [] and parsed["total"] == 0 and parsed["pages"] == 0
    assert parsed["summary"] is None   # upstream sends an all-null summary
    assert P.parse_transactions({})["results"] == []


# ---- locations ---------------------------------------------------------------------------------------

def test_parse_locations():
    parsed = P.parse_locations(fixture("locations_marina.json"))
    assert parsed["total"] == 504 and parsed["pages"] == 51
    marina = parsed["results"][0]
    assert marina["id"] == 50 and marina["name"] == "Dubai Marina" and marina["type"] == "community"
    assert marina["full_name"] == "Dubai Marina, Dubai" and marina["path"] == [1, 50] and marina["city_id"] == 1
    assert marina["insights_link"] == "https://www.propertyfinder.ae/en/area-insights/dubai/dubai-marina"
    assert marina["link"] == "https://www.propertyfinder.ae/en/search?c=1&l=50"
    assert marina["review"]["count"] == 1138 and marina["children_count"] == 278
    by_ids = P.parse_locations(fixture("locations_ids_1_50_4467.json"))["results"]
    assert [(r["id"], r["type"]) for r in by_ids] == [(50, "community"), (4467, "subcommunity"), (1, "city")]
    assert by_ids[2]["insights_link"] is None
    empty = P.parse_locations(fixture("locations_no_match.json"))
    assert empty == {"results": [], "total": 0, "pages": 0}
    sa = P.parse_locations(fixture("locations_sa_riyadh.json"), "sa")
    assert sa["results"][0]["link"].startswith("https://www.propertyfinder.sa/")


# ---- areas / reviews -----------------------------------------------------------------------------------

def test_parse_area_page_community():
    area = P.parse_area_page(fixture("area_dubai_marina.html"))
    assert area["id"] == 50 and area["name"] == "Dubai Marina" and area["type"] == "community"
    assert area["link"] == "https://www.propertyfinder.ae/en/area-insights/dubai/dubai-marina"
    assert area["city"] == {"id": 1, "name": "Dubai", "slug": "dubai"} and area["path"] == [1, 50]
    assert area["coordinates"] == {"lat": 25.0784, "lon": 55.1404}
    assert area["tags"] == ["Luxury", "Expats", "Near Metro"] and len(area["key_facts"]) == 7
    assert area["review"]["score"] == 3.9 and area["review"]["count"] == 1138 and area["review"]["scores"]["amenities"] == 4.2
    assert area["review"]["sublocation_reviews_count"] == 1126
    assert len(area["faqs"]) == 9 and "<" not in area["faqs"][0]["answer"]
    assert area["description"].startswith("It doesn") and area["guide"]["public_transport"].startswith("For the closest")
    assert area["guide"]["poi_summaries"]["metro_stations"].startswith("Dub")
    assert area["house_prices"][0] == {"category": "buy", "property_type": "Apartment", "property_type_id": 1, "bedrooms": 0, "price": 1164000}
    assert area["price_histogram"][0] == {"from": 400000, "count": 526}
    poi = area["points_of_interest"]
    assert poi["counts"]["metro_stations"] == 4 and poi["counts"]["total"] == 504
    assert poi["schools"]["count"] == 14 and poi["schools"]["nearest"][0]["name"] == "Emirates International School Meadows"
    assert poi["nearby"]["metro_stations"][0]["name"] == "DMCC" and poi["nearby"]["metro_stations"][0]["walking"]["distance_m"] == 1484.6
    assert area["demographics"]["renter_nationalities"][0] == {"rank": 1, "country_code": "GB", "name": "United Kingdom", "pct": 14.24}
    assert area["demographics"]["profile"]["dominant_property_type"] == "Apartment"
    assert area["market"]["average_tenure"] == {"days": 402, "years": 1.1}
    assert area["market"]["offerings"]["buy"]["median_price"] == 2515535 and area["market"]["offerings"]["buy"]["listings_available"] == 3981
    assert area["market"]["offerings"]["buy"]["transactions_summary"]["roi_pct"] == 5.8816
    assert set(area["market"]["price_trends_per_sqft"]) == {"1Y", "2Y", "5Y"}
    assert area["popular_buildings"]["buy"][0]["name"] == "Marina Gate" and area["popular_buildings"]["buy"][0]["review"]["score"] == 3.6
    assert area["similar_communities"][0]["name"] == "Jumeirah Lake Towers"
    assert area["people_also_search"]["buy"][0]["id"] == 73
    assert area["listings"]["buy_link"].startswith("https://www.propertyfinder.ae/en/buy/")


def test_parse_area_page_tower():
    tower = P.parse_area_page(fixture("area_tower_marina_gate.html"))
    assert tower["id"] == 733 and tower["name"] == "Marina Gate" and tower["type"] == "subcommunity"
    assert tower["parent"]["id"] == 50 and tower["parent"]["insights_link"].endswith("/dubai-marina")
    assert tower["review"]["score"] == 3.6 and tower["description"] is None and tower["key_facts"] is None
    assert tower["house_prices"] and tower["market"]["offerings"]["buy"]
    assert tower["guide"]["poi_summaries"]["gyms"]


def test_parse_area_page_without_location():
    assert P.parse_area_page("<html></html>") is None


def test_parse_reviews():
    parsed = P.parse_reviews(fixture("reviews_marina_p1.json"))
    assert parsed["location"] == {"id": 50, "name": "Dubai Marina", "parent_id": 1, "level": 1}
    assert parsed["total"] == 12 and parsed["pages"] == 2 and parsed["score"] == 3.9
    assert parsed["categories"]["parking_area"] == "Parking"
    review = parsed["results"][0]
    assert review["user_name"] == "Yosef" and review["persona"] == "Resident" and review["score"] == 3.7
    assert review["body"].startswith("Dubai Marina is a beautiful") and review["body_ar"]
    assert review["scores"]["amenities"] == 5 and review["likes"] == 4 and review["location"]["id"] == 50
    children = P.parse_reviews(fixture("reviews_marina_p1.json"), children=True)
    assert children["total"] == 1126 and children["pages"] == 113 and children["sublocations"][0]["name"] == "DEC Towers"
    none = P.parse_reviews(fixture("reviews_none_5629.json"))
    assert none["total"] == 0 and none["results"] == [] and none["score"] is None
    assert P.parse_reviews({})["results"] == []
