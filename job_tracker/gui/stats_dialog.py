"""Pop-up window with the statistics charts (success-rate donut, applications
by company) and their target / time-range filters."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .. import chart, outcomes


VIEW_SUCCESS = "Success rate"
VIEW_COMPANY = "By company"


class StatisticsDialog(tk.Toplevel):
    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self.title("Statistics")
        self.geometry("860x600")
        self.minsize(560, 440)
        self.transient(parent)
        self.df = df
        self.canvas = None

        filters = ttk.Frame(self)
        filters.pack(fill="x", padx=10, pady=8)

        ttk.Label(filters, text="View").pack(side="left")
        self.view_var = tk.StringVar(value=VIEW_SUCCESS)
        view_combo = ttk.Combobox(
            filters, textvariable=self.view_var, values=[VIEW_SUCCESS, VIEW_COMPANY],
            state="readonly", width=14,
        )
        view_combo.pack(side="left", padx=(6, 16))
        view_combo.bind("<<ComboboxSelected>>", lambda _e: self._redraw())

        ttk.Label(filters, text="Target").pack(side="left")
        self.target_var = tk.StringVar(value=next(iter(outcomes.TARGETS)))
        self.target_combo = target_combo = ttk.Combobox(
            filters, textvariable=self.target_var, values=list(outcomes.TARGETS),
            state="readonly", width=28,
        )
        target_combo.pack(side="left", padx=(6, 16))
        target_combo.bind("<<ComboboxSelected>>", lambda _e: self._redraw())

        ttk.Label(filters, text="Applied").pack(side="left")
        self.range_var = tk.StringVar(value=next(iter(outcomes.TIME_RANGES)))
        range_combo = ttk.Combobox(
            filters, textvariable=self.range_var, values=list(outcomes.TIME_RANGES),
            state="readonly", width=16,
        )
        range_combo.pack(side="left", padx=(6, 0))
        range_combo.bind("<<ComboboxSelected>>", lambda _e: self._redraw())

        ttk.Label(
            self,
            text=f"Ghosted = no reply {outcomes.GHOSTED_AFTER_DAYS}+ days after applying; "
            "younger ones count as awaiting reply.",
            foreground=chart.INK_SECONDARY,
        ).pack(anchor="w", padx=10)

        self.chart_container = ttk.Frame(self)
        self.chart_container.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self._redraw()

    def _redraw(self):
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        df = outcomes.filter_by_time_range(self.df, outcomes.TIME_RANGES[self.range_var.get()])
        if self.view_var.get() == VIEW_COMPANY:
            self.target_combo.configure(state="disabled")  # the company view shows every outcome
            figure = chart.build_company_figure(df)
        else:
            self.target_combo.configure(state="readonly")
            figure = chart.build_success_donut_figure(df, self.target_var.get())
        self.canvas = FigureCanvasTkAgg(figure, master=self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
