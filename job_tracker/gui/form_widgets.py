"""Form pieces shared by the Add and Edit dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .today_shortcut import enable_today_shortcut

SALARY_HINT = "e.g. 65-75k € / year"
HINT_COLOR = "#52514e"


class LabeledForm(ttk.Frame):
    """Two-column grid: a label on the left, a stretching field on the
    right, one row per `add_row` call."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.columnconfigure(1, weight=1)
        self._next_row = 0

    def add_row(self, label: str, field: tk.Widget, stretch=True) -> None:
        ttk.Label(self, text=label).grid(
            row=self._next_row, column=0, sticky="w", pady=4
        )
        field.grid(
            row=self._next_row,
            column=1,
            sticky="ew" if stretch else "w",
            pady=4,
            padx=(8, 0),
        )
        self._next_row += 1

    def add_entry(self, label: str, variable: tk.StringVar) -> ttk.Entry:
        entry = ttk.Entry(self, textvariable=variable)
        self.add_row(label, entry)
        return entry

    def add_salary(self, variable: tk.StringVar) -> None:
        field = ttk.Frame(self)
        ttk.Entry(field, textvariable=variable, width=24).pack(side="left")
        ttk.Label(field, text=SALARY_HINT, foreground=HINT_COLOR).pack(
            side="left", padx=(6, 0)
        )
        self.add_row("Salary", field)


class ScrolledText(ttk.Frame):
    """A multi-line text box with a scrollbar and the `#dd` shortcut."""

    def __init__(self, master, height: int, initial_text: str = ""):
        super().__init__(master)
        self.text = tk.Text(self, wrap="word", height=height)
        scrollbar = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.set(initial_text)
        enable_today_shortcut(self.text)

    def get(self) -> str:
        return self.text.get("1.0", "end").strip()

    def set(self, value: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
