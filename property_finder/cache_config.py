"""Cache TTL per /property-finder/* endpoint (cache.py, keyed on the
validated params). Listings churn by the hour, directories by the day, DLD
data daily."""
from datetime import timedelta

# Autocomplete rows (ids, names, insights links) change only when the site adds places.
LOCATIONS_CACHE = timedelta(days=7)
# A name / slug -> location id lookup is as stable as the directory above.
LOCATION_LOOKUP_CACHE = timedelta(days=7)
# Listing search: new listings land every minute, counts and prices move within the hour.
SEARCH_CACHE = timedelta(minutes=15)
# One listing's page: price edits are rare within a day; the agent's rating is slow too.
PROPERTY_CACHE = timedelta(hours=6)
# Monthly AED/sqft series.
PRICE_TRENDS_CACHE = timedelta(hours=24)
# Agent directory pages: rankings and listing counts move slowly.
AGENTS_SEARCH_CACHE = timedelta(hours=6)
# One agent's profile (bio, counts, claimed transactions).
AGENT_CACHE = timedelta(hours=24)
# An agent's / company's live listings: same churn as search, a little slower.
LISTINGS_CACHE = timedelta(hours=1)
# Brokerage directory and profiles.
COMPANIES_SEARCH_CACHE = timedelta(hours=12)
COMPANY_CACHE = timedelta(hours=24)
# New projects: campaign updates land daily.
PROJECTS_SEARCH_CACHE = timedelta(hours=6)
PROJECT_CACHE = timedelta(hours=24)
# The 960-row developer directory (10 upstream pages) and one developer record.
DEVELOPERS_CACHE = timedelta(hours=24)
DEVELOPER_CACHE = timedelta(hours=24)
# DLD transactions are published once a day.
TRANSACTIONS_CACHE = timedelta(hours=6)
# Area insights page (2.4 MB upstream; CMS content + monthly stats).
AREA_CACHE = timedelta(hours=24)
# Area reviews: a handful land per day across the whole site.
REVIEWS_CACHE = timedelta(hours=12)
