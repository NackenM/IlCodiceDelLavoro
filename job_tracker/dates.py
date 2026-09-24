"""Dates as the user sees and types them (DD.MM.YYYY).

The CSV stores ISO dates (YYYY-MM-DD) so they sort and parse
unambiguously; the conversion to and from that lives in the repository.
"""

from __future__ import annotations

from datetime import date, datetime

DISPLAY_FORMAT = "%d.%m.%Y"
DISPLAY_HINT = "DD.MM.YYYY"


def format_display_date(value: date | None) -> str:
    return value.strftime(DISPLAY_FORMAT) if value else ""


def parse_display_date(text: str) -> date | None:
    """DD.MM.YYYY -> date; blank -> None. Raises ValueError if invalid."""
    text = text.strip()
    if not text:
        return None
    return datetime.strptime(text, DISPLAY_FORMAT).date()


def is_valid_display_date(text: str) -> bool:
    """True for a DD.MM.YYYY date and for blank (= not set)."""
    try:
        parse_display_date(text)
    except ValueError:
        return False
    return True
