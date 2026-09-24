"""Company entry that suggests the companies already in the tracker, so
repeat applications keep one spelling."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Keys that move the cursor or delete text -- completing after these would
# re-insert what the user just removed.
_KEYS_WITHOUT_COMPLETION = {
    "BackSpace",
    "Delete",
    "Left",
    "Right",
    "Up",
    "Down",
    "Home",
    "End",
    "Tab",
    "Return",
    "Escape",
    "Shift_L",
    "Shift_R",
}


def companies_containing(companies: list[str], typed: str) -> list[str]:
    needle = typed.casefold()
    return [company for company in companies if needle in company.casefold()]


def completion_for(companies: list[str], typed: str) -> str | None:
    """The first known company starting with `typed` (ignoring case) that
    is longer than it."""
    needle = typed.casefold()
    return next(
        (
            company
            for company in companies
            if company.casefold().startswith(needle)
            and len(company) > len(typed)
        ),
        None,
    )


class CompanyCombobox(ttk.Combobox):
    """Editable combobox: the dropdown lists the known companies containing
    the typed text, and the first one starting with it is completed inline
    in its stored spelling (the completed part is selected, so typing on
    replaces it)."""

    def __init__(
        self,
        master,
        textvariable: tk.StringVar,
        known_companies: list[str],
        **kwargs,
    ):
        super().__init__(
            master, textvariable=textvariable, values=known_companies, **kwargs
        )
        self.known_companies = known_companies
        self.bind("<KeyRelease>", self._on_key_release)

    def _on_key_release(self, event: tk.Event) -> None:
        typed = self.get()[: self.index("insert")]
        self.configure(
            values=companies_containing(self.known_companies, typed)
        )
        if event.keysym in _KEYS_WITHOUT_COMPLETION or not typed:
            return
        completion = completion_for(self.known_companies, typed)
        if completion:
            self.delete(0, "end")
            self.insert(0, completion)
            self.icursor(len(typed))
            self.selection_range(len(typed), "end")
