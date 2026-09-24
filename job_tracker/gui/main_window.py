"""Main window: the application list above a pipeline chart."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import charts
from ..companies import known_companies
from ..model import Application
from ..repository import DEFAULT_CSV_PATH, ApplicationRepository
from .add_dialog import AddApplicationDialog
from .application_list import ApplicationList
from .chart_panel import ChartPanel
from .edit_dialog import EditApplicationDialog
from .stats_dialog import StatisticsDialog
from .stop_signals import close_on_stop_signals, stop_signals_held_back
from .timeline_dialog import TimelineDialog

CHART_VIEWS = {
    "Outcome waterfall": charts.build_outcome_waterfall_figure,
    "Progress by application": charts.build_progress_figure,
}
USAGE_HINT = (
    "Click a column header to sort  ·  Double-click a row to edit  ·  "
    "⌘-click rows for Timeline"
)


class MainWindow(tk.Tk):
    def __init__(self, repository: ApplicationRepository):
        super().__init__()
        self.title("Job Application Tracker")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.repository = repository
        self.applications: list[Application] = []

        self._build_toolbar()
        self._build_body()
        self.refresh()

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=6)
        buttons = [
            ("+ Add Application", self._open_add_dialog),
            ("Refresh", self.refresh),
            ("Statistics", self._open_statistics),
            ("Timeline", self._open_timeline),
        ]
        for index, (text, command) in enumerate(buttons):
            ttk.Button(toolbar, text=text, command=command).pack(
                side="left", padx=(6 if index else 0, 0)
            )

        ttk.Label(toolbar, text="Chart").pack(side="left", padx=(18, 6))
        self.chart_view = tk.StringVar(value=next(iter(CHART_VIEWS)))
        chart_choice = ttk.Combobox(
            toolbar,
            textvariable=self.chart_view,
            values=list(CHART_VIEWS),
            state="readonly",
            width=22,
        )
        chart_choice.pack(side="left")
        chart_choice.bind(
            "<<ComboboxSelected>>", lambda _event: self._show_chart()
        )
        ttk.Label(toolbar, text=USAGE_HINT).pack(side="right")

    def _build_body(self) -> None:
        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.application_list = ApplicationList(
            panes, on_open=self._open_edit_dialog
        )
        panes.add(self.application_list, weight=2)
        self.chart_panel = ChartPanel(panes)
        panes.add(self.chart_panel, weight=3)

    def refresh(self) -> None:
        self.applications = self.repository.load_all()
        self.application_list.show(self.applications)
        self._show_chart()

    def _show_chart(self) -> None:
        build_figure = CHART_VIEWS[self.chart_view.get()]
        self.chart_panel.show(build_figure(self.applications))

    def _open_add_dialog(self) -> None:
        AddApplicationDialog(
            self,
            self.repository,
            known_companies(self.applications),
            on_saved=self.refresh,
        )

    def _open_edit_dialog(self, application: Application) -> None:
        EditApplicationDialog(
            self,
            self.repository,
            application,
            known_companies(self.applications),
            on_changed=self.refresh,
        )

    def _open_statistics(self) -> None:
        StatisticsDialog(self, self.applications)

    def _open_timeline(self) -> None:
        selected = self.application_list.selected()
        if not selected:
            messagebox.showinfo(
                "Timeline",
                "Select one or more applications in the list first "
                "(⌘- or Shift-click to select several).",
                parent=self,
            )
            return
        TimelineDialog(self, selected)


def main(csv_path: Path = DEFAULT_CSV_PATH) -> None:
    with stop_signals_held_back():
        window = MainWindow(ApplicationRepository(csv_path))
        close_on_stop_signals(window)
    window.mainloop()
