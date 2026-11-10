"""The one network helper the property_finder module asks for: the
Accept-Language its sessions announce. Property Finder picks the page
language from the URL (every request asks for the English pages), not from
this header, so the kit sends the list a desktop Chrome in the US sends, on
your own connection or on PROPERTY_FINDER_PROXY alike."""

ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def accept_language(proxy=None, country=None):
    return ACCEPT_LANGUAGE


def site_accept_language(site=None):
    return ACCEPT_LANGUAGE
