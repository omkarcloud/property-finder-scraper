"""Use the scraper straight from Python, no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. Params are validated by the same schemas the API uses, so a
listing id or a propertyfinder.ae link, a place name or a location id all work.
"""
import json
import os

from property_finder import api, schemas

os.makedirs("output", exist_ok=True)


def run(schema_cls, fn, **params):
    """Validate params like the API does, then call the scraper function."""
    return fn(**schema_cls().load(params))


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a listing id or any propertyfinder listing link
    save("property_palm_jumeirah_villa.json", run(schemas.PropertySchema, api.property_details,
                                                  property="167877493"))

    # Palm Jumeirah villas for sale, most expensive first (25 per page)
    save("search_palm_jumeirah_villas.json", run(schemas.PropertiesSearchSchema, api.properties_search,
                                                 location="Palm Jumeirah", property_type="villa", sort="price-high"))

    # Dubai Land Department sales in the Burj Khalifa, newest first
    save("transactions_burj_khalifa.json", run(schemas.TransactionsSearchSchema, api.transactions_search,
                                               location="Burj Khalifa"))
