"""Offline tests for the upstream query the /property-finder/* endpoints send
(the filter names below were each checked live on 2026-11-10: the API
silently ignores a wrong one and answers the unfiltered list).

    python -m pytest property_finder/test_api.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from property_finder import api  # noqa: E402


def _sent(params):
    return [(k, v) for k, v in params if v is not None]


def test_agent_filters_use_the_names_the_api_filters_on():
    sent = _sent(api._agents_params(1, 20, text="nathan", location_ids=[50, 86], category=2, language=6,
                                    nationality="GB", super_agent=True, sort="-total_properties"))
    assert ("language_ids", 6) in sent and ("is_superagent", "true") in sent
    # several places go as one comma list: a repeated location_ids keeps only the last
    assert ("location_ids", "50,86") in sent and [k for k, _ in sent].count("location_ids") == 1
    assert not {k for k, _ in sent} & {"languages", "superagent", "must_have_properties"}
    assert not {k for k, _ in _sent(api._agents_params(1, 20, super_agent=None))} & {"is_superagent"}


def test_companies_search_sends_one_location_id(monkeypatch):
    seen = {}

    def fake_fetch(country, params):
        seen["params"] = params
        return [], {"total": 0, "total_pages": 0}

    rows = [{"id": 86, "name": "Palm Jumeirah"}, {"id": 50, "name": "Dubai Marina"}]
    monkeypatch.setattr(api, "fetch_brokerages", fake_fetch)
    monkeypatch.setattr(api, "_resolve_location", lambda ref, country, required=True: ([86, 50], rows))
    out = api._companies_search("sotheby", {"ids": [86, 50]}, None, 1, 20, "ae")
    sent = _sent(seen["params"])
    assert ("location_id", 86) in sent and ("text", "sotheby") in sent
    assert not any(k in ("location_ids", "location_id") and v == 50 for k, v in sent)
    assert [r["id"] for r in out["location"]] == [86]


def test_agents_listing_sorts_stop_at_10000_results(monkeypatch):
    monkeypatch.setattr(api, "fetch_agents", lambda country, params: ([], {"total": 20140, "total_pages": 202}))
    capped = api._agents_response("ae", api._agents_params(1, 100, sort="-total_properties"), 1, 100)
    assert capped["pagination"]["total_pages"] == 100 and capped["pagination"]["total_count"] == 20140
    featured = api._agents_response("ae", api._agents_params(1, 100, sort="-trusted_score"), 1, 100)
    assert featured["pagination"]["total_pages"] == 202


def test_transactions_take_the_link_type_and_whole_number_bounds(monkeypatch):
    seen = {}

    def fake_fetch(country, location_id, params):
        seen["params"] = dict(params)
        return {"transactions": [], "total_items": 0, "total_pages": 0}

    monkeypatch.setattr(api, "fetch_transactions", fake_fetch)
    monkeypatch.setattr(api, "_resolve_location", lambda ref, country, required=True: ([2710], [{"id": 2710}]))
    rented_link = {"ids": None, "slug": "x", "city_slug": "dubai", "query": None, "country": "ae", "deal": "rented"}
    out = api._transactions_search(rented_link, None, None, None, None, None, None, 44458.56, 61277.81, 500.5, None,
                                   None, None, None, None, "td", 1, 25, "ae")
    assert seen["params"]["offering_type_id"] == 2 and out["type"] == "rented"
    assert seen["params"]["min_price"] == 44458 and seen["params"]["max_price"] == 61278 and seen["params"]["min_area"] == 500
    assert out["summary"] is None
    api._transactions_search({"ids": [2710]}, None, None, None, None, None, None, None, None, None, None,
                             None, None, None, None, "td", 1, 25, "ae")
    assert seen["params"]["offering_type_id"] == 1


def test_companies_search_without_location(monkeypatch):
    seen = {}

    def fake_fetch(country, params):
        seen["params"] = params
        return [], {}

    monkeypatch.setattr(api, "fetch_brokerages", fake_fetch)
    monkeypatch.setattr(api, "_resolve_location", lambda ref, country, required=True: (None, None))
    out = api._companies_search(None, None, "name", 1, 20, "ae")
    assert not any(k == "location_id" for k, _ in _sent(seen["params"]))
    assert out["location"] is None and out["results"] == []
