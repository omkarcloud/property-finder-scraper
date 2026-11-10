"""Configuration for the Property Finder Scraper. Everything can be set with
an environment variable; the defaults work out of the box.

    PORT                    port the API listens on (default 8000)
    PROPERTY_FINDER_PROXY   proxy URL for every request, e.g.
                            http://user:pass@host:port (default: none, direct).
                            Property Finder answers a home or office
                            connection fine at normal volume, so you only
                            need a proxy for heavy, sustained traffic.

Everything else below is a plain constant with a working default. Edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

# After a block, how long (seconds) new sessions ride the fallback proxy.
# The kit has no second proxy tier (see property_finder_fallback_proxy), so
# this only matters if you wire one in.
PROPERTY_FINDER_BLOCK_HOLD_S = 600

# Property Finder serves at most 500 transactions per query; paging stops there.
PROPERTY_FINDER_TRANSACTIONS_ROW_CAP = 500

PROPERTY_FINDER_PROXY = os.environ.get("PROPERTY_FINDER_PROXY") or None


def property_finder_proxy():
    """The proxy for one HTTP session (None = direct)."""
    return os.environ.get("PROPERTY_FINDER_PROXY") or None


def property_finder_fallback_proxy():
    """Where new sessions go for PROPERTY_FINDER_BLOCK_HOLD_S after a block on
    a direct connection. None keeps them direct; return a proxy URL here to
    switch to it automatically."""
    return None
