"""The sortable table of applications in the main window."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from tkinter import ttk
from typing import Any

from ..dates import format_display_date
from ..model import Application
from ..stages import Stage

_STAGE_ORDER = {stage: index for index, stage in enumerate(Stage)}


@dataclass(frozen=True)
class ListColumn:
    key: str
    heading: str
    width: int
    cell_text: Callable[[Application], str]
    # None puts the application after all others, in either direction.
    sort_value: Callable[[Application], Any | None]


def _text_sort_value(text: str) -> str | None:
    return text.casefold() or None


LIST_COLUMNS = [
    ListColumn(
        "job_title",
        "Job Title",
        200,
        lambda a: a.job_title,
        lambda a: _text_sort_value(a.job_title),
    ),
    ListColumn(
        "company",
        "Company",
        140,
        lambda a: a.company,
        lambda a: _text_sort_value(a.company),
    ),
    ListColumn(
        "status",
        "Status",
        220,
        Application.status_label,
        lambda a: _STAGE_ORDER[a.status],  # pipeline order
    ),
    # By amount; salaries without a number ("negotiable") go last.
    ListColumn(
        "salary", "Salary", 110, lambda a: a.salary, lambda a: a.salary_amount
    ),
    ListColumn(
        "contact_email",
        "Contact",
        190,
        lambda a: a.contact_email,
        lambda a: _text_sort_value(a.contact_email),
    ),
    ListColumn(
        "date_applied",
        "Date Applied",
        95,
        lambda a: format_display_date(a.date_applied),
        lambda a: a.date_applied,
    ),
    ListColumn(
        "last_update",
        "Last Update",
        95,
        lambda a: format_display_date(a.last_update),
        lambda a: a.last_update,
    ),
]
COLUMNS_BY_KEY = {column.key: column for column in LIST_COLUMNS}


def sort_applications(
    applications: Sequence[Application],
    column: ListColumn,
    descending: bool = False,
) -> list[Application]:
    """Sorted by the column's value; applications without one go last in
    either direction -- those with some text (e.g. a "negotiable" salary)
    before blank ones."""
    with_value = [a for a in applications if column.sort_value(a) is not None]
    without_value = [a for a in applications if column.sort_value(a) is None]
    with_value.sort(key=column.sort_value, reverse=descending)
    without_value.sort(key=lambda a: not column.cell_text(a))
    return with_value + without_value


class ApplicationList(ttk.Frame):
    """Treeview of the applications; click a heading to sort by it, again
    to reverse."""

    def __init__(self, master, on_open: Callable[[Application], None]):
        super().__init__(master)
        self._applications: list[Application] = []
        self._sort_column: ListColumn | None = None
        self._sort_descending = False
        self._on_open = on_open

        self.tree = ttk.Treeview(
            self,
            columns=[column.key for column in LIST_COLUMNS],
            show="headings",
            selectmode="extended",
        )
        for column in LIST_COLUMNS:
            self.tree.heading(
                column.key,
                text=column.heading,
                command=lambda c=column: self._sort_by(c),
            )
            self.tree.column(column.key, width=column.width, anchor="w")
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_double_click)

    def show(self, applications: list[Application]) -> None:
        self._applications = applications
        self._redraw()

    def selected(self) -> list[Application]:
        """The selected applications, in the list's current order."""
        by_id = {a.id: a for a in self._applications}
        return [by_id[item] for item in self.tree.selection() if item in by_id]

    def _sort_by(self, column: ListColumn) -> None:
        if self._sort_column is column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column, self._sort_descending = column, False
        self._redraw()

    def _redraw(self) -> None:
        for column in LIST_COLUMNS:
            arrow = ""
            if column is self._sort_column:
                arrow = " ▼" if self._sort_descending else " ▲"
            self.tree.heading(column.key, text=column.heading + arrow)

        shown = self._applications
        if self._sort_column is not None:
            shown = sort_applications(
                shown, self._sort_column, self._sort_descending
            )
        self.tree.delete(*self.tree.get_children())
        for application in shown:
            self.tree.insert(
                "",
                "end",
                iid=application.id,
                values=[
                    column.cell_text(application) for column in LIST_COLUMNS
                ],
            )

    def _on_double_click(self, event: tk.Event) -> None:
        # The row under the cursor: with several rows selected, the
        # selection alone doesn't say which one was double-clicked.
        clicked_id = self.tree.identify_row(event.y)
        clicked = next(
            (a for a in self._applications if a.id == clicked_id), None
        )
        if clicked is not None:
            self._on_open(clicked)
