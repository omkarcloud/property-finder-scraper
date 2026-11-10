"""Offline tests for the /property-finder/* request schemas.

    python -m pytest property_finder/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from property_finder import schemas  # noqa: E402


def _errors(schema, data):
    with pytest.raises(ValidationError) as info:
        schema().load(data)
    return info.value.normalized_messages()


# ---- locations -------------------------------------------------------------------------------

def test_locations_search_schema():
    loaded = schemas.LocationsSearchSchema().load({"query": " marina ", "type": "Community", "category": "rent"})
    assert loaded == {"query": "marina", "type": "COMMUNITY", "category": 2, "limit": 10, "country": "ae"}
    assert "query" in _errors(schemas.LocationsSearchSchema, {})
    assert "type" in _errors(schemas.LocationsSearchSchema, {"query": "x", "type": "street"})
    assert "limit" in _errors(schemas.LocationsSearchSchema, {"query": "x", "limit": "51"})
    assert "country" in _errors(schemas.LocationsSearchSchema, {"query": "x", "country": "us"})


# ---- properties -------------------------------------------------------------------------------

def test_properties_search_defaults():
    loaded = schemas.PropertiesSearchSchema().load({})
    assert loaded["location"] is None and loaded["category"] == 1 and loaded["sort"] == 0
    assert loaded["page"] == 1 and loaded["per_page"] == 25 and loaded["country"] == "ae"


def test_properties_search_filters_map_to_upstream_tokens():
    loaded = schemas.PropertiesSearchSchema().load({
        "location": "https://www.propertyfinder.ae/en/search?c=2&l=50&l=86", "category": "Rent",
        "property_type": "Villa", "bedrooms": "studio, 2, 7+", "bathrooms": "3", "min_price": "100000",
        "max_price": "250000.5", "rent_period": "yearly", "min_area": "500", "furnished": "partly-furnished",
        "completion_status": "off-plan", "amenities": "ba, Shared Pool, PA", "keywords": " sea view ",
        "listed_within": "30", "virtual_viewing": "360-tours", "deal_badge": "price-drop",
        "has_mortgage_cashback": "yes", "sort": "price-high", "page": "3", "per_page": "60", "country": "AE"})
    assert loaded["location"]["ids"] == [50, 86] and loaded["location"]["country"] == "ae"
    assert loaded["category"] == 2 and loaded["property_type"] == 35
    assert loaded["bedrooms"] == [0, 2, 8] and loaded["bathrooms"] == [3]
    assert loaded["min_price"] == 100000 and loaded["max_price"] == 250000.5
    assert loaded["furnished"] == 3 and loaded["completion_status"] == "off_plan"
    assert loaded["amenities"] == ["BA", "SP", "PA"] and loaded["keywords"] == "sea view"
    assert loaded["listed_within"] == 30 * 86400 and loaded["virtual_viewing"] == "360_tours"
    assert loaded["deal_badge"] == "price_drop" and loaded["has_mortgage_cashback"] is True
    assert loaded["sort"] == 3 and loaded["page"] == 3 and loaded["per_page"] == 60


def test_properties_search_location_forms():
    assert schemas.PropertiesSearchSchema().load({"location": "50"})["location"]["ids"] == [50]
    assert schemas.PropertiesSearchSchema().load({"location": "Dubai Marina"})["location"]["query"] == "Dubai Marina"
    link = schemas.PropertiesSearchSchema().load(
        {"location": "https://www.propertyfinder.ae/en/buy/dubai/properties-for-sale-dubai-marina.html"})["location"]
    assert link["slug"] == "dubai-marina" and link["city_slug"] == "dubai"


@pytest.mark.parametrize("bad,field", [
    ({"per_page": "61"}, "per_page"),
    ({"page": "0"}, "page"),
    ({"bedrooms": "9"}, "bedrooms"),
    ({"amenities": "jacuzzi-of-doom"}, "amenities"),
    ({"property_type": "castle"}, "property_type"),
    ({"sort": "cheapest"}, "sort"),
    ({"listed_within": "2"}, "listed_within"),
    ({"category": "new-projects"}, "category"),
    ({"location": "https://example.com/?l=50"}, "location"),
    ({"url": "x"}, "url"),
    ({"min_price": "-1"}, "min_price"),
])
def test_properties_search_rejects(bad, field):
    assert field in _errors(schemas.PropertiesSearchSchema, bad)


def test_property_schema():
    assert schemas.PropertySchema().load({"property": "164588946"}) == {"property": {"id": 164588946, "country": None}, "country": "ae"}
    loaded = schemas.PropertySchema().load({"property": "https://www.propertyfinder.sa/en/plp/buy/x-52173408.html"})
    assert loaded["property"] == {"id": 52173408, "country": "sa"}
    errors = _errors(schemas.PropertySchema, {"property": "villa"})
    assert errors["property"] == ["Must be a listing id (164588946) or a propertyfinder listing link."]
    assert "property" in _errors(schemas.PropertySchema, {})
    assert "id" in _errors(schemas.PropertySchema, {"property": "1", "id": "1"})     # no sibling params


def test_price_trends_schema():
    loaded = schemas.PriceTrendsSchema().load({"location": "4467", "bedrooms": "3", "property_type": "villa"})
    assert loaded["location"]["ids"] == [4467] and loaded["category"] == 1 and loaded["bedrooms"] == 3 and loaded["property_type"] == 35
    assert schemas.PriceTrendsSchema().load({"location": "4467", "bedrooms": "studio", "property_type": "apartment", "category": "rent"})["bedrooms"] == 0
    for missing in ({"location": "4467"}, {"location": "4467", "bedrooms": "3"}, {"bedrooms": "3", "property_type": "villa"}):
        with pytest.raises(ValidationError):
            schemas.PriceTrendsSchema().load(missing)


# ---- agents ------------------------------------------------------------------------------------

def test_agents_search_schema():
    loaded = schemas.AgentsSearchSchema().load({"language": "Russian", "nationality": "ru",
                                                "super_agent": "1", "sort": "listings-most",
                                                "location": "50", "category": "commercial-rent", "per_page": "100"})
    assert loaded["language"] == 6 and loaded["nationality"] == "RU" and loaded["super_agent"] is True
    assert loaded["sort"] == "-total_properties" and loaded["category"] == 4
    assert loaded["location"]["ids"] == [50] and loaded["per_page"] == 100
    assert schemas.AgentsSearchSchema().load({})["sort"] is None
    assert "language" in _errors(schemas.AgentsSearchSchema, {"language": "klingon"})
    assert "nationality" in _errors(schemas.AgentsSearchSchema, {"nationality": "xx"})
    assert "per_page" in _errors(schemas.AgentsSearchSchema, {"per_page": "101"})
    assert "sort" in _errors(schemas.AgentsSearchSchema, {"sort": "price"})
    # the API lists only agents with live listings and its `ranking` sort is the
    # featured order: neither is offered
    assert "has_listings" in _errors(schemas.AgentsSearchSchema, {"has_listings": "true"})
    assert "sort" in _errors(schemas.AgentsSearchSchema, {"sort": "ranking"})
    # Property Finder ignores the name when a place is set: refused together
    assert schemas.AgentsSearchSchema().load({"query": "nathan"})["query"] == "nathan"
    assert "query" in _errors(schemas.AgentsSearchSchema, {"query": "jordan", "location": "86"})


def test_agent_schemas():
    assert schemas.AgentSchema().load({"agent": "264476"})["agent"] == {"id": 264476, "country": None}
    assert schemas.AgentSchema().load({"agent": "https://www.propertyfinder.ae/en/agent/nathan-blake-264476"})["agent"] == {"id": 264476, "country": "ae"}
    assert "agent" in _errors(schemas.AgentSchema, {"agent": "nathan"})
    loaded = schemas.AgentListingsSchema().load({"agent": "264476", "category": "rent", "sort": "newest"})
    assert loaded["category"] == 2 and loaded["sort"] == 1 and loaded["per_page"] == 25
    assert schemas.AgentListingsSchema().load({"agent": "264476"})["category"] is None


# ---- companies ---------------------------------------------------------------------------------

def test_company_schemas():
    loaded = schemas.CompaniesSearchSchema().load({"sort": "listings-most", "location": "dubai"})
    assert loaded["sort"] == "-total_properties" and loaded["location"]["query"] == "dubai"
    assert schemas.CompaniesSearchSchema().load({"query": "barnes"})["query"] == "barnes"
    assert schemas.CompaniesSearchSchema().load({"sort": "featured"})["sort"] is None
    assert "sort" in _errors(schemas.CompaniesSearchSchema, {"sort": "name"})   # not alphabetical upstream
    assert "query" in _errors(schemas.CompaniesSearchSchema, {"query": "barnes", "location": "dubai"})
    assert schemas.CompanySchema().load({"company": "https://www.propertyfinder.ae/en/broker/barnes-international-realty-v2-4338-4338"})["company"] == {"id": 4338, "country": "ae"}
    assert "company" in _errors(schemas.CompanySchema, {"company": "barnes"})
    loaded = schemas.CompanyAgentsSchema().load({"company": "4338", "sort": "rent-listings", "page": "2"})
    assert loaded["sort"] == "-total_rental_properties" and loaded["page"] == 2
    assert "has_listings" in _errors(schemas.CompanyAgentsSchema, {"company": "4338", "has_listings": "true"})
    loaded = schemas.CompanyListingsSchema().load({"company": "4338", "category": "buy", "sort": "price-low"})
    assert loaded["category"] == 1 and loaded["sort"] == 2


# ---- projects / developers ------------------------------------------------------------------------

def test_projects_search_schema():
    loaded = schemas.ProjectsSearchSchema().load({
        "location": "1", "developer": "emaar-properties", "property_type": "Villa", "completion_status": "under-construction",
        "min_price": "1000000", "max_price": "5000000", "delivery_from": "2027-01-01", "has_dld_id": "true",
        "has_post_handover_payment_plan": "yes", "keywords": "creek", "per_page": "50"})
    assert loaded["developer"] == {"uuid": None, "slug": "emaar-properties", "country": None}
    assert loaded["property_type"] == "villa" and loaded["completion_status"] == "under_construction"
    assert loaded["delivery_from"] == "2027-01-01" and loaded["has_dld_id"] is True and loaded["per_page"] == 50
    assert schemas.ProjectsSearchSchema().load({})["per_page"] == 10
    assert "per_page" in _errors(schemas.ProjectsSearchSchema, {"per_page": "51"})
    assert "delivery_from" in _errors(schemas.ProjectsSearchSchema, {"delivery_from": "2027"})
    assert "property_type" in _errors(schemas.ProjectsSearchSchema, {"property_type": "office"})
    assert "developer" in _errors(schemas.ProjectsSearchSchema, {"developer": "https://example.com/dev/x"})


def test_project_and_developer_schemas():
    uuid = "d1294890-1250-48b7-99e3-4f34a371b967"
    assert schemas.ProjectSchema().load({"project": uuid})["project"]["uuid"] == uuid
    assert schemas.ProjectSchema().load({"project": "emaar-properties/valia-tower"})["project"]["slug"] == "emaar-properties/valia-tower"
    assert schemas.ProjectSchema().load({"project": "https://www.propertyfinder.ae/en/new-projects/emaar-properties/valia-tower"})["project"]["country"] == "ae"
    assert "project" in _errors(schemas.ProjectSchema, {"project": "valia"})
    assert schemas.DeveloperSchema().load({"developer": "Emaar-Properties"})["developer"]["slug"] == "emaar-properties"
    assert "developer" in _errors(schemas.DeveloperSchema, {"developer": "https://www.propertyfinder.ae/en/new-projects/emaar-properties/valia-tower"})
    loaded = schemas.DevelopersSearchSchema().load({"query": "emaar", "page": "2"})
    assert loaded == {"query": "emaar", "page": 2, "per_page": 20, "country": "ae"}
    assert schemas.DevelopersSearchSchema().load({})["query"] is None


# ---- transactions ------------------------------------------------------------------------------------

def test_transactions_schema():
    loaded = schemas.TransactionsSearchSchema().load({
        "location": "50", "type": "rented", "contract_status": "new", "bedrooms": "1,2", "property_type": "apartment",
        "min_price": "50000", "max_price": "300000", "sort": "price-desc", "per_page": "50"})
    assert loaded["type"] == 2 and loaded["contract_status"] == "new" and loaded["bedrooms"] == [1, 2]
    assert loaded["property_type"] == 1 and loaded["sort"] == "pd" and loaded["per_page"] == 50
    defaults = schemas.TransactionsSearchSchema().load({"location": "1"})
    # no type: the api layer reads sold, or rented from a transactions/rented/… link
    assert defaults["type"] is None and defaults["sort"] == "td" and defaults["per_page"] == 25 and defaults["period"] is None
    assert "location" in _errors(schemas.TransactionsSearchSchema, {"location": "86,50"})   # one place only
    assert "location" in _errors(schemas.PriceTrendsSchema, {"location": "86,50", "bedrooms": "2", "property_type": "villa"})
    assert "area" in _errors(schemas.AreaSchema, {"area": "86,50"})
    assert "area" in _errors(schemas.AreaReviewsSchema, {"area": "86,50"})
    dated = schemas.TransactionsSearchSchema().load({"location": "1", "date_from": "2026-01-01", "date_to": "2026-01-31"})
    assert dated["date_from"] == "2026-01-01" and dated["date_to"] == "2026-01-31"
    assert schemas.TransactionsSearchSchema().load({"location": "1", "period": "ytd"})["period"] == "ytd"


@pytest.mark.parametrize("bad,field", [
    ({}, "location"),
    ({"location": "1", "per_page": "51"}, "per_page"),
    ({"location": "1", "date_from": "2026-01-01"}, "date_from"),
    ({"location": "1", "date_from": "2026-02-01", "date_to": "2026-01-01"}, "date_from"),
    ({"location": "1", "period": "1y", "date_from": "2026-01-01", "date_to": "2026-01-31"}, "period"),
    ({"location": "1", "period": "2w"}, "period"),
    ({"location": "1", "sort": "newest"}, "sort"),
    ({"location": "1", "type": "leased"}, "type"),
    ({"location": "1", "date_from": "2999-01-01", "date_to": "2999-01-02"}, "date_from"),
])
def test_transactions_schema_rejects(bad, field):
    assert field in _errors(schemas.TransactionsSearchSchema, bad)


# ---- areas ------------------------------------------------------------------------------------------

def test_area_schemas():
    loaded = schemas.AreaSchema().load({"area": "https://www.propertyfinder.ae/en/area-insights/dubai/dubai-marina"})
    assert loaded["area"] == {"ids": None, "slug": "dubai-marina", "city_slug": "dubai", "query": None, "country": "ae"}
    assert schemas.AreaSchema().load({"area": "50"})["area"]["ids"] == [50]
    assert "area" in _errors(schemas.AreaSchema, {})
    loaded = schemas.AreaReviewsSchema().load({"area": "dubai marina", "sort": "rating_highest", "include_sublocations": "true", "per_page": "50"})
    assert loaded["sort"] == "rating_highest" and loaded["include_sublocations"] is True and loaded["per_page"] == 50
    defaults = schemas.AreaReviewsSchema().load({"area": "50"})
    assert defaults["sort"] == "newest" and defaults["include_sublocations"] is False and defaults["per_page"] == 20
    assert "sort" in _errors(schemas.AreaReviewsSchema, {"area": "50", "sort": "best"})
    assert "per_page" in _errors(schemas.AreaReviewsSchema, {"area": "50", "per_page": "51"})


def test_every_field_documents_itself():
    """Every public param carries a description (it becomes the docs)."""
    for name in dir(schemas):
        cls = getattr(schemas, name)
        if isinstance(cls, type) and issubclass(cls, schemas.BaseSchema) and cls is not schemas.BaseSchema:
            for field_name, field in cls().fields.items():
                assert field.metadata.get("description"), f"{name}.{field_name} has no description"
