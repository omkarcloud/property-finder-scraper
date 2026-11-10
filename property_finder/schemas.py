"""Marshmallow request schemas for every /property-finder/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair):

    location   a location id (Dubai Marina = 50), several ids comma-separated,
               a place name ("dubai marina", resolved through the site's own
               autocomplete) OR any propertyfinder link that names a location
               (search ?l=, SEO listing page, transactions, area-insights)
    property   a listing id OR a listing link
    agent      an agent id OR an agent link (/en/agent/<name>-<id>)
    company    a brokerage id OR a broker link (/en/broker/<name>-<id>)
    project    a project uuid, "<developer>/<project>" slug OR a project link
    developer  a developer uuid, slug OR a developer link
    area       same forms as `location` (area-insights pages)
    country    the storefront: ae (default), sa, qa, bh, eg — a link's TLD wins

Vocabularies (property types, amenities, languages, sorts) live in
property_finder/refs.py; every field carries a `description` because it
becomes the public docs.

Fields are declared inline with literal bounds and defaults (no
argument-taking field helpers): the publish tooling reads this file with the
AST, and only an inline constructor call shows it the required flag, the
choices, the default and the page-size limits.
"""
from marshmallow import ValidationError, missing, validates_schema

from schema_fields import (BaseSchema, ChoiceField, CommaListField, CountryCodeField, DateField, Flag,
                           NonNegativeNumber, PageField, PageSizeField, Price, QueryField, RefField,
                           StrippedString)
from property_finder import refs

MAX_SEARCH_PAGE_SIZE = 60        # property-api/web/v2: pagination.limit 61 is a 400
MAX_SEARCH_PAGE = 2000           # page 2000 of a 189K result set still answers
MAX_PAGE = 1000                  # every other paginated list
MAX_PROJECTS_PAGE = 500
MAX_TRANSACTIONS_PAGE = 500      # the 500-row cap ends paging far earlier (api.py)
MAX_AGENTS_PAGE_SIZE = 100       # pf-b2c-customer per_page ceiling
MAX_PROJECTS_PAGE_SIZE = 50      # bilbo serves 100, but a project card is ~70 KB upstream
MAX_TRANSACTIONS_PAGE_SIZE = 50  # b2c-transactions size ceiling (60 is a 400)
MAX_REVIEWS_PAGE_SIZE = 50


def _max_length(n):
    """validate.Length(max=n) that tolerates the None StrippedString returns
    for an empty optional value."""
    def check(value):
        if value is not None and len(value) > n:
            raise ValidationError(f"Longer than maximum length {n}.")
    return check


def _optional_text(description, n=200):
    return StrippedString(required=False, load_default=None, validate=_max_length(n),
                          metadata={"description": description})


def _country():
    # "ae" spelled out (= refs.DEFAULT_COUNTRY) so the AST reader sees the default
    return ChoiceField(list(refs.COUNTRIES), load_default="ae", metadata={
        "description": "storefront: ae (UAE, default), sa, qa, bh or eg; a propertyfinder link's own TLD wins"})


EVERY_CATEGORY = "buy, rent, commercial-buy or commercial-rent (default: every category)"
PAGE = "page number (1-based)"


# ---- reference fields -------------------------------------------------------------------

class LocationField(RefField):
    resolver = staticmethod(refs.resolve_location)


class PropertyRefField(RefField):
    resolver = staticmethod(refs.resolve_property)


class AgentRefField(RefField):
    resolver = staticmethod(refs.resolve_agent)


class CompanyRefField(RefField):
    resolver = staticmethod(refs.resolve_company)


class ProjectRefField(RefField):
    resolver = staticmethod(refs.resolve_project)


class DeveloperRefField(RefField):
    resolver = staticmethod(refs.resolve_developer)


LOCATION_DESCRIPTION = ("location id (Dubai Marina = 50; several comma-separated), a place name, or a "
                        "propertyfinder link that names the location (search, listing page, transactions "
                        "or area-insights link)")


_AMENITY_MAP = {**{code: code for code in refs.AMENITIES}, **refs.AMENITY_SLUGS}


class AmenitiesField(CommaListField):
    """Amenity codes (BA) or names in any spelling ('Shared Pool', shared_pool)
    -> the site's codes."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_items", len(refs.AMENITIES))
        super().__init__(value_map=_AMENITY_MAP, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        items = []
        for raw in str(value).split(","):
            item = raw.strip()
            if not item:
                continue
            items.append(item if item.upper() in refs.AMENITIES else
                         __import__("re").sub(r"[^a-z0-9]+", "-", item.lower()).strip("-"))
        return super()._deserialize(",".join(items), attr, data, **kwargs)


# ---- locations -----------------------------------------------------------------------------

class LocationsSearchSchema(BaseSchema):
    query = QueryField(max_length=120, metadata={"description": "place name to look up (city, community, sub-community or tower)"})
    type = ChoiceField(refs.LOCATION_TYPES, metadata={"description": "only this kind of place: city, community, subcommunity or tower"})
    category = ChoiceField(refs.CATEGORIES, metadata={
        "description": "buy, rent, commercial-buy, commercial-rent or new-projects (default: every category)"})
    limit = PageSizeField(default=10, max_size=50, metadata={"description": "max results (default 10, max 50)"})
    country = _country()


# ---- properties -----------------------------------------------------------------------------

class PropertiesSearchSchema(BaseSchema):
    location = LocationField(required=False, load_default=None, metadata={"description": LOCATION_DESCRIPTION})
    category = ChoiceField(refs.LISTING_CATEGORIES, load_default=1, metadata={
        "description": "buy (default), rent, commercial-buy or commercial-rent"})
    property_type = ChoiceField(refs.PROPERTY_TYPES, metadata={
        "description": "apartment, villa, townhouse, penthouse, duplex, land, office, retail, warehouse, shop ... "
                       "(refs.PROPERTY_TYPES)"})
    bedrooms = CommaListField(value_map=refs.BEDROOMS, max_items=9, metadata={
        "description": "comma-separated: studio, 1 ... 7, 7+"})
    bathrooms = CommaListField(value_map=refs.BATHROOMS, max_items=8, metadata={"description": "comma-separated: 1 ... 7, 7+"})
    min_price = Price(metadata={"description": "minimum price in the storefront currency (AED for ae)"})
    max_price = Price(metadata={"description": "maximum price"})
    rent_period = ChoiceField(list(refs.RENT_PERIODS), metadata={
        "description": "rent listings only: yearly, monthly, weekly or daily — the price the min/max apply to"})
    min_area = NonNegativeNumber(metadata={"description": "minimum size in sqft"})
    max_area = NonNegativeNumber(metadata={"description": "maximum size in sqft"})
    furnished = ChoiceField(refs.FURNISHED, metadata={"description": "furnished, unfurnished or partly-furnished"})
    completion_status = ChoiceField({"completed": "completed", "off-plan": "off_plan"}, metadata={
        "description": "completed (ready) or off-plan"})
    amenities = AmenitiesField(metadata={
        "description": "comma-separated amenity codes or names: BA/balcony, SP/shared-pool, CP/covered-parking, "
                       "PA/pets-allowed, MR/maids-room, PP/private-pool, PG/private-garden, ST/study ..."})
    keywords = _optional_text("free-text keywords matched in the listing")
    listed_within = ChoiceField({str(d): d * 86400 for d in refs.LISTED_WITHIN_DAYS}, metadata={
        "description": "only listings added in the last N days: 1, 7, 15, 30 or 90"})
    virtual_viewing = ChoiceField(refs.VIRTUAL_VIEWINGS, metadata={
        "description": "only listings with a floor-plan, 360-tours, video or live viewing"})
    deal_badge = ChoiceField(refs.DEAL_BADGES, metadata={"description": "great-value, high-demand or price-drop badge"})
    has_mortgage_cashback = Flag(metadata={"description": "true: only listings with a mortgage cashback offer"})
    sort = ChoiceField(refs.SEARCH_SORTS, load_default=0, metadata={
        "description": "featured (default), newest, price-low, price-high, beds-least, beds-most, "
                       "delivery-earliest, delivery-latest"})
    page = PageField(max_page=MAX_SEARCH_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=25, max_size=MAX_SEARCH_PAGE_SIZE, metadata={
        "description": "results per page (default 25, max 60)"})
    country = _country()


class PropertySchema(BaseSchema):
    property = PropertyRefField(metadata={"description": "listing id (164588946) or a propertyfinder listing link"})
    country = _country()


class PriceTrendsSchema(BaseSchema):
    location = LocationField(metadata={"description": "location id, name or link of the community / sub-community / tower"})
    category = ChoiceField({"buy": 1, "rent": 2}, load_default=1, metadata={"description": "buy (default) or rent"})
    bedrooms = ChoiceField(refs.BEDROOMS, required=True, load_default=missing, metadata={
        "description": "studio, 1 ... 7 or 7+"})
    property_type = ChoiceField(refs.PROPERTY_TYPES, required=True, load_default=missing, metadata={
        "description": "apartment, villa, townhouse, penthouse ..."})
    country = _country()


# ---- agents ---------------------------------------------------------------------------------

class AgentsSearchSchema(BaseSchema):
    query = _optional_text("agent name to search for", 100)
    location = LocationField(required=False, load_default=None, metadata={
        "description": "location id, name or link the agents list in"})
    category = ChoiceField(refs.LISTING_CATEGORIES, metadata={"description": EVERY_CATEGORY})
    language = ChoiceField(refs.LANGUAGES, metadata={"description": "a language the agent speaks (english, arabic, hindi, russian, french ...)"})
    nationality = CountryCodeField(metadata={"description": "2-letter country code of the agent's nationality (GB, IN, RU ...)"})
    super_agent = Flag(metadata={"description": "true: SuperAgents only"})
    sort = ChoiceField(refs.AGENT_SORTS, metadata={
        "description": "featured (default), listings-most, listings-least, sale-listings or rent-listings"})
    page = PageField(max_page=MAX_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=20, max_size=MAX_AGENTS_PAGE_SIZE, metadata={
        "description": "results per page (default 20, max 100)"})
    country = _country()


class AgentSchema(BaseSchema):
    agent = AgentRefField(metadata={"description": "agent id (264476) or a propertyfinder agent link"})
    country = _country()


class AgentListingsSchema(BaseSchema):
    agent = AgentRefField(metadata={"description": "agent id or a propertyfinder agent link"})
    category = ChoiceField(refs.LISTING_CATEGORIES, metadata={"description": EVERY_CATEGORY})
    sort = ChoiceField(refs.SEARCH_SORTS, load_default=0, metadata={
        "description": "featured (default), newest, price-low, price-high, beds-least, beds-most"})
    page = PageField(max_page=MAX_SEARCH_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=25, max_size=MAX_SEARCH_PAGE_SIZE, metadata={
        "description": "results per page (default 25, max 60)"})
    country = _country()


# ---- companies (brokerages) -------------------------------------------------------------------

class CompaniesSearchSchema(BaseSchema):
    query = _optional_text("company name to search for", 100)
    location = LocationField(required=False, load_default=None, metadata={
        "description": "location id, name or link the company lists in (one place: with several ids the first counts)"})
    sort = ChoiceField(refs.COMPANY_SORTS, metadata={"description": "featured (default), name or listings-most"})
    page = PageField(max_page=MAX_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=20, max_size=MAX_AGENTS_PAGE_SIZE, metadata={
        "description": "results per page (default 20, max 100)"})
    country = _country()


class CompanySchema(BaseSchema):
    company = CompanyRefField(metadata={"description": "company id (4338) or a propertyfinder broker link"})
    country = _country()


class CompanyAgentsSchema(BaseSchema):
    company = CompanyRefField(metadata={"description": "company id or a propertyfinder broker link"})
    sort = ChoiceField(refs.AGENT_SORTS, metadata={
        "description": "featured (default), listings-most, listings-least, sale-listings or rent-listings"})
    page = PageField(max_page=MAX_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=20, max_size=MAX_AGENTS_PAGE_SIZE, metadata={
        "description": "results per page (default 20, max 100)"})
    country = _country()


class CompanyListingsSchema(BaseSchema):
    company = CompanyRefField(metadata={"description": "company id or a propertyfinder broker link"})
    category = ChoiceField(refs.LISTING_CATEGORIES, metadata={"description": EVERY_CATEGORY})
    sort = ChoiceField(refs.SEARCH_SORTS, load_default=0, metadata={
        "description": "featured (default), newest, price-low, price-high, beds-least, beds-most"})
    page = PageField(max_page=MAX_SEARCH_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=25, max_size=MAX_SEARCH_PAGE_SIZE, metadata={
        "description": "results per page (default 25, max 60)"})
    country = _country()


# ---- new projects / developers ----------------------------------------------------------------

class ProjectsSearchSchema(BaseSchema):
    location = LocationField(required=False, load_default=None, metadata={"description": LOCATION_DESCRIPTION})
    developer = DeveloperRefField(required=False, load_default=None, metadata={
        "description": "developer uuid, slug (emaar-properties) or developer link"})
    property_type = ChoiceField(list(refs.PROJECT_PROPERTY_TYPES), metadata={
        "description": "apartment, villa, townhouse, penthouse, duplex or land"})
    completion_status = ChoiceField({"completed": "completed", "under-construction": "under_construction",
                                     "not-started": "not_started"}, metadata={
        "description": "completed, under-construction or not-started"})
    min_price = Price(metadata={"description": "minimum starting price"})
    max_price = Price(metadata={"description": "maximum starting price"})
    delivery_from = DateField(metadata={"description": "only projects delivered on/after this date (YYYY-MM-DD)"})
    has_dld_id = Flag(metadata={"description": "true: only projects registered with the Dubai Land Department"})
    has_post_handover_payment_plan = Flag(metadata={"description": "true: only projects with a post-handover payment plan"})
    keywords = _optional_text("free-text keywords (project or developer name)")
    page = PageField(max_page=MAX_PROJECTS_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=10, max_size=MAX_PROJECTS_PAGE_SIZE, metadata={
        "description": "results per page (default 10, max 50)"})
    country = _country()


class ProjectSchema(BaseSchema):
    project = ProjectRefField(metadata={
        "description": "project uuid, '<developer-slug>/<project-slug>' (emaar-properties/valia-tower) or a project link"})
    country = _country()


class DevelopersSearchSchema(BaseSchema):
    query = _optional_text("developer name to search for (matched in the directory)", 100)
    page = PageField(max_page=MAX_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=20, max_size=MAX_AGENTS_PAGE_SIZE, metadata={
        "description": "results per page (default 20, max 100)"})
    country = _country()


class DeveloperSchema(BaseSchema):
    developer = DeveloperRefField(metadata={"description": "developer uuid, slug (emaar-properties) or a developer link"})
    country = _country()


# ---- transactions --------------------------------------------------------------------------------

class TransactionsSearchSchema(BaseSchema):
    location = LocationField(metadata={
        "description": "location id, name or link (Dubai = 1, Dubai Marina = 50); Dubai Land Department data, Dubai only"})
    type = ChoiceField(refs.TRANSACTION_TYPES, load_default=1, metadata={"description": "sold (default) or rented"})
    period = ChoiceField(list(refs.TRANSACTION_PERIODS), metadata={
        "description": "1w, 1m, 3m, 6m, ytd, 1y, 3y, 5y or 10y (alternative to date_from/date_to)"})
    date_from = DateField(bound="past", metadata={"description": "transactions on/after this date (YYYY-MM-DD), with date_to"})
    date_to = DateField(bound="past", metadata={"description": "transactions on/before this date (YYYY-MM-DD), with date_from"})
    property_type = ChoiceField(refs.PROPERTY_TYPES, metadata={"description": "apartment, villa, townhouse, penthouse ..."})
    bedrooms = CommaListField(value_map=refs.BEDROOMS, max_items=9, metadata={"description": "comma-separated: studio, 1 ... 7, 7+"})
    min_price = Price(metadata={"description": "minimum transaction price (AED)"})
    max_price = Price(metadata={"description": "maximum transaction price (AED)"})
    min_area = NonNegativeNumber(metadata={"description": "minimum size in sqft"})
    max_area = NonNegativeNumber(metadata={"description": "maximum size in sqft"})
    completion_status = ChoiceField({"completed": "completed", "off-plan": "off_plan"}, metadata={
        "description": "sold: completed (ready) or off-plan"})
    contract_status = ChoiceField(list(refs.CONTRACT_STATUS), metadata={"description": "rented: new or renewed contracts"})
    sold_by = ChoiceField(list(refs.SOLD_BY), metadata={"description": "sold: developer or individual"})
    unit_number = _optional_text("a unit / property number to look up", 30)
    sort = ChoiceField(refs.TRANSACTION_SORTS, load_default="td", metadata={
        "description": "date-desc (default), date-asc, price-asc or price-desc"})
    page = PageField(max_page=MAX_TRANSACTIONS_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=25, max_size=MAX_TRANSACTIONS_PAGE_SIZE, metadata={
        "description": "results per page (default 25, max 50)"})
    country = _country()

    @validates_schema
    def _dates(self, data, **kwargs):
        if bool(data.get("date_from")) != bool(data.get("date_to")):
            raise ValidationError("date_from and date_to go together.", "date_from")
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise ValidationError("date_from must not be after date_to.", "date_from")
        if data.get("period") and data.get("date_from"):
            raise ValidationError("Use either period or date_from/date_to, not both.", "period")


# ---- areas ----------------------------------------------------------------------------------------

class AreaSchema(BaseSchema):
    area = LocationField(metadata={"description": "location id (50), a place name or an area-insights / search link"})
    country = _country()


class AreaReviewsSchema(BaseSchema):
    area = LocationField(metadata={"description": "location id (50), a place name or an area-insights / search link"})
    sort = ChoiceField(list(refs.REVIEW_SORTS), load_default="newest", metadata={
        "description": "newest (default), oldest, rating_lowest or rating_highest"})
    include_sublocations = Flag(load_default=False, metadata={
        "description": "true: the reviews of the buildings / sub-communities inside this area instead of the area's own"})
    page = PageField(max_page=MAX_PAGE, metadata={"description": PAGE})
    per_page = PageSizeField(default=20, max_size=MAX_REVIEWS_PAGE_SIZE, metadata={
        "description": "results per page (default 20, max 50)"})
    country = _country()
