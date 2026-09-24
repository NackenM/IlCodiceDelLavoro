"""Statistics window: success rate and company charts, with target and
time-range filters."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from matplotlib.figure import Figure

from .. import charts
from ..model import Application
from ..outcomes import (
    APPLIED_WITHIN_CHOICES,
    GHOSTED_AFTER_DAYS,
    SUCCESS_TARGETS,
    applied_within,
)
from .chart_panel import ChartPanel
from .form_widgets import HINT_COLOR

SUCCESS_RATE_VIEW = "Success rate"
# Views that show every outcome, so the target filter does not apply.
COMPANY_VIEWS: dict[str, Callable[[Sequence[Application]], Figure]] = {
    "By company": charts.build_company_outcomes_figure,
    "Company share": charts.build_company_share_figure,
}


class StatisticsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, applications: list[Application]):
        super().__init__(parent)
        self.title("Statistics")
        self.geometry("860x600")
        self.minsize(560, 440)
        self.transient(parent)
        self.applications = applications

        filters = ttk.Frame(self)
        filters.pack(fill="x", padx=10, pady=8)
        self.view, _ = self._add_choice(
            filters, "View", [SUCCESS_RATE_VIEW, *COMPANY_VIEWS], width=14
        )
        self.target, self.target_choice = self._add_choice(
            filters, "Target", list(SUCCESS_TARGETS), width=28
        )
        self.applied_within, _ = self._add_choice(
            filters, "Applied", list(APPLIED_WITHIN_CHOICES), width=16
        )

        ttk.Label(
            self,
            text=f"Ghosted = no reply {GHOSTED_AFTER_DAYS}+ days after "
            "applying; younger ones count as awaiting reply.",
            foreground=HINT_COLOR,
        ).pack(anchor="w", padx=10)

        self.chart_panel = ChartPanel(self)
        self.chart_panel.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self._redraw()

    def _add_choice(
        self, parent: ttk.Frame, label: str, choices: list[str], width: int
    ) -> tuple[tk.StringVar, ttk.Combobox]:
        ttk.Label(parent, text=label).pack(side="left")
        variable = tk.StringVar(value=choices[0])
        choice = ttk.Combobox(
            parent,
            textvariable=variable,
            values=choices,
            state="readonly",
            width=width,
        )
        choice.pack(side="left", padx=(6, 16))
        choice.bind("<<ComboboxSelected>>", lambda _event: self._redraw())
        return variable, choice

    def _redraw(self) -> None:
        shown = applied_within(
            self.applications,
            APPLIED_WITHIN_CHOICES[self.applied_within.get()],
        )
        build_company_figure = COMPANY_VIEWS.get(self.view.get())
        if build_company_figure:
            self.target_choice.configure(state="disabled")
            figure = build_company_figure(shown)
        else:
            self.target_choice.configure(state="readonly")
            figure = charts.build_success_rate_figure(shown, self.target.get())
        self.chart_panel.show(figure)
