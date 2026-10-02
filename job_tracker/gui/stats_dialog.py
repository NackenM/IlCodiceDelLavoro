"""Statistics window: success rate, company and reply-time charts with
target and time-range filters, and a month-by-month activity calendar."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import date
from tkinter import ttk

from matplotlib.figure import Figure

from .. import charts
from ..activity import ActivityKind, activity_by_day, latest_active_month
from ..charts.style import LogoLookup
from ..dates import month_title, shift_month
from ..model import Application
from ..outcomes import (
    APPLIED_WITHIN_CHOICES,
    GHOSTED_AFTER_DAYS,
    SUCCESS_TARGETS,
    applied_within,
)
from .chart_panel import ChartPanel
from .form_widgets import HINT_COLOR
from .logo_store import LogoStore

SUCCESS_RATE_VIEW = "Success rate"
BY_COMPANY_VIEW = "By company"
CALENDAR_VIEW = "Calendar"
# Views the target filter does not apply to; given the applications and
# the company logos (None without).
UNTARGETED_VIEWS: dict[
    str, Callable[[Sequence[Application], LogoLookup | None], Figure]
] = {
    BY_COMPANY_VIEW: lambda applications, logos: (
        charts.build_company_outcomes_figure(applications, logos=logos)
    ),
    "Company share": lambda applications, _: charts.build_company_share_figure(
        applications
    ),
    "Reply times": lambda applications, _: charts.build_reply_times_figure(
        applications
    ),
}


class StatisticsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        applications: list[Application],
        logos: LogoStore | None = None,
    ):
        super().__init__(parent)
        self.title("Statistics")
        self.geometry("860x600")
        self.minsize(560, 440)
        self.transient(parent)
        self.applications = applications
        self.logos = logos

        self.filters = filters = ttk.Frame(self)
        filters.pack(fill="x", padx=10, pady=8)
        self.view, _ = self._add_choice(
            filters,
            "View",
            [SUCCESS_RATE_VIEW, *UNTARGETED_VIEWS, CALENDAR_VIEW],
            width=14,
        )
        self.target, self.target_choice = self._add_choice(
            filters, "Target", list(SUCCESS_TARGETS), width=28
        )
        self.applied_within, self.applied_choice = self._add_choice(
            filters, "Applied", list(APPLIED_WITHIN_CHOICES), width=16
        )
        self._build_month_bar()

        self.ghosted_hint = ttk.Label(
            self,
            text=f"Ghosted = no reply {GHOSTED_AFTER_DAYS}+ days after "
            "applying; younger ones count as awaiting reply.",
            foreground=HINT_COLOR,
        )
        self.ghosted_hint.pack(anchor="w", padx=10)

        self.chart_panel = ChartPanel(self)
        self.chart_panel.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self._redraw()
        if logos is not None:
            logos.subscribe_while(self, self._redraw_logos)

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

    def _build_month_bar(self) -> None:
        """Month switcher and count choice, shown with the calendar only.
        It opens on the month of the latest activity."""
        self.month_bar = ttk.Frame(self)
        days = activity_by_day(self.applications, ActivityKind.ALL_STAGES)
        self.year, self.month = latest_active_month(days, date.today())
        ttk.Button(
            self.month_bar, text="◀", width=3, command=lambda: self._shift(-1)
        ).pack(side="left")
        self.month_label = ttk.Label(self.month_bar, width=16, anchor="center")
        self.month_label.pack(side="left", padx=4)
        ttk.Button(
            self.month_bar, text="▶", width=3, command=lambda: self._shift(1)
        ).pack(side="left")
        ttk.Button(
            self.month_bar, text="This month", command=self._this_month
        ).pack(side="left", padx=(8, 16))
        self.activity_kind, _ = self._add_choice(
            self.month_bar, "Count", list(ActivityKind), width=16
        )
        # Left / right arrows switch months too, unless a dropdown has the
        # keyboard.
        for key, months in (("<Left>", -1), ("<Right>", 1)):
            self.bind(
                key, lambda event, m=months: self._shift_by_key(event, m)
            )

    def _shift(self, months: int) -> None:
        self.year, self.month = shift_month(self.year, self.month, months)
        self._redraw()

    def _shift_by_key(self, event: tk.Event, months: int) -> None:
        if self.view.get() == CALENDAR_VIEW and not isinstance(
            event.widget, ttk.Combobox
        ):
            self._shift(months)

    def _this_month(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self._redraw()

    def _redraw(self) -> None:
        calendar_shown = self.view.get() == CALENDAR_VIEW
        if calendar_shown:
            self.ghosted_hint.pack_forget()
            self.month_bar.pack(
                fill="x", padx=10, pady=(0, 6), after=self.filters
            )
        else:
            self.month_bar.pack_forget()
            self.ghosted_hint.pack(anchor="w", padx=10, after=self.filters)
        self.applied_choice.configure(
            state="disabled" if calendar_shown else "readonly"
        )
        if calendar_shown:
            self.target_choice.configure(state="disabled")
            self.month_label.configure(text=month_title(self.year, self.month))
            self.chart_panel.show(
                charts.build_activity_calendar_figure(
                    self.applications,
                    self.year,
                    self.month,
                    ActivityKind(self.activity_kind.get()),
                )
            )
            return
        shown = applied_within(
            self.applications,
            APPLIED_WITHIN_CHOICES[self.applied_within.get()],
        )
        build_untargeted_figure = UNTARGETED_VIEWS.get(self.view.get())
        if build_untargeted_figure:
            self.target_choice.configure(state="disabled")
            figure = build_untargeted_figure(
                shown, self.logos.image if self.logos else None
            )
        else:
            self.target_choice.configure(state="readonly")
            figure = charts.build_success_rate_figure(shown, self.target.get())
        self.chart_panel.show(figure)

    def _redraw_logos(self) -> None:
        if self.view.get() == BY_COMPANY_VIEW:
            self._redraw()
