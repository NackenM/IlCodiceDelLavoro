"""Typing `#dd` into a text field replaces it with today's date."""

from __future__ import annotations

import tkinter as tk
from datetime import date

from ..dates import format_display_date

TODAY_TOKEN = "#dd"


def today_display() -> str:
    return format_display_date(date.today())


def enable_today_shortcut(widget: tk.Entry | tk.Text) -> None:
    """Replace `#dd` with today's date as soon as it is typed."""
    if isinstance(widget, tk.Text):
        widget.bind("<KeyRelease>", _expand_in_text, add="+")
    else:
        widget.bind("<KeyRelease>", _expand_in_entry, add="+")


def _expand_in_entry(event: tk.Event) -> None:
    entry = event.widget
    cursor = entry.index("insert")
    token_start = cursor - len(TODAY_TOKEN)
    if token_start >= 0 and entry.get()[token_start:cursor] == TODAY_TOKEN:
        entry.delete(token_start, cursor)
        entry.insert(token_start, today_display())


def _expand_in_text(event: tk.Event) -> None:
    text = event.widget
    token_start = f"insert-{len(TODAY_TOKEN)}c"
    if text.get(token_start, "insert") == TODAY_TOKEN:
        text.delete(token_start, "insert")
        text.insert("insert", today_display())
