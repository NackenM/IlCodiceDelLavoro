"""Dates as the user sees and types them (DD.MM.YYYY).

The CSV stores ISO dates (YYYY-MM-DD) so they sort and parse
unambiguously; the conversion to and from that lives in the repository.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime

DISPLAY_FORMAT = "%d.%m.%Y"
DISPLAY_HINT = "DD.MM.YYYY"
WEEKDAY_HEADINGS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def format_display_date(value: date | None) -> str:
    return value.strftime(DISPLAY_FORMAT) if value else ""


def parse_display_date(text: str) -> date | None:
    """DD.MM.YYYY -> date; blank -> None. Raises ValueError if invalid."""
    text = text.strip()
    if not text:
        return None
    return datetime.strptime(text, DISPLAY_FORMAT).date()


def month_grid(year: int, month: int) -> list[list[date]]:
    """The weeks (Monday first) covering the month, padded with days of
    the neighbouring months so every week is complete."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)


def month_title(year: int, month: int) -> str:
    """ "September 2026"."""
    return f"{calendar.month_name[month]} {year}"


def shift_month(year: int, month: int, months: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + months
    return index // 12, index % 12 + 1


def is_valid_display_date(text: str) -> bool:
    """True for a DD.MM.YYYY date and for blank (= not set)."""
    try:
        parse_display_date(text)
    except ValueError:
        return False
    return True
