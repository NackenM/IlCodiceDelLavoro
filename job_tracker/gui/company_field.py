"""Company entry that suggests companies already in the tracker, so repeat
applications keep one spelling."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import outcomes, storage

# Keys that move the cursor or delete text -- completing after these would
# re-insert what the user just removed.
_NO_COMPLETE_KEYS = {"BackSpace", "Delete", "Left", "Right", "Up", "Down", "Home", "End",
                     "Tab", "Return", "Escape", "Shift_L", "Shift_R"}


class CompanyCombobox(ttk.Combobox):
    """Editable combobox: the dropdown lists known companies containing the
    typed text, and the first one starting with it is completed inline in
    its stored spelling (the completed part is selected, so typing on simply
    replaces it)."""

    def __init__(self, master, textvariable: tk.StringVar, **kwargs):
        self.companies = outcomes.known_companies(storage.load_applications())
        super().__init__(master, textvariable=textvariable, values=self.companies, **kwargs)
        self.bind("<KeyRelease>", self._on_key)

    def _on_key(self, event):
        typed = self.get()[: self.index("insert")]
        needle = typed.casefold()
        self.configure(values=[c for c in self.companies if needle in c.casefold()])
        if event.keysym in _NO_COMPLETE_KEYS or not typed:
            return
        match = next((c for c in self.companies if c.casefold().startswith(needle)), None)
        if match and len(match) > len(typed):
            self.delete(0, "end")
            self.insert(0, match)
            self.icursor(len(typed))
            self.selection_range(len(typed), "end")
