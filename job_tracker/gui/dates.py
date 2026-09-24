"""Date display/parsing helpers and the `#dd` today-shortcut for input widgets.

Dates are stored as ISO (YYYY-MM-DD) in the CSV so they sort and parse
unambiguously; the GUI shows and accepts them as DD.MM.YYYY.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime

DISPLAY_FORMAT = "%d.%m.%Y"
DISPLAY_HINT = "DD.MM.YYYY"
TODAY_TOKEN = "#dd"


def today_display() -> str:
    return date.today().strftime(DISPLAY_FORMAT)


def to_display(iso_value: str) -> str:
    """ISO -> DD.MM.YYYY. Blank or unparseable values are returned unchanged."""
    if not iso_value:
        return ""
    try:
        return date.fromisoformat(iso_value).strftime(DISPLAY_FORMAT)
    except ValueError:
        return iso_value


def to_iso(display_value: str) -> str:
    """DD.MM.YYYY -> ISO. Blank stays blank; raises ValueError if invalid."""
    if not display_value:
        return ""
    return datetime.strptime(display_value, DISPLAY_FORMAT).date().isoformat()


def is_valid_display_date(value: str) -> bool:
    try:
        to_iso(value)
        return True
    except ValueError:
        return False


def enable_today_shortcut(widget: tk.Entry | tk.Text) -> None:
    """Replace `#dd` with today's date as soon as it is typed into `widget`."""
    if isinstance(widget, tk.Text):
        widget.bind("<KeyRelease>", _expand_in_text, add="+")
    else:
        widget.bind("<KeyRelease>", _expand_in_entry, add="+")


def _expand_in_entry(event) -> None:
    w = event.widget
    pos = w.index("insert")
    start = pos - len(TODAY_TOKEN)
    if start >= 0 and w.get()[start:pos] == TODAY_TOKEN:
        w.delete(start, pos)
        w.insert(start, today_display())


def _expand_in_text(event) -> None:
    w = event.widget
    start = f"insert-{len(TODAY_TOKEN)}c"
    if w.get(start, "insert") == TODAY_TOKEN:
        w.delete(start, "insert")
        w.insert("insert", today_display())
