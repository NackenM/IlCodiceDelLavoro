"""Window with the timeline of the applications selected in the list."""

from __future__ import annotations

import tkinter as tk

from .. import charts
from ..model import Application
from .chart_panel import ChartPanel

# The window grows with the number of applications, up to this height.
MAX_HEIGHT = 860
HEIGHT_PER_APPLICATION = 62


class TimelineDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, applications: list[Application]):
        super().__init__(parent)
        self.title("Timeline")
        height = 160 + HEIGHT_PER_APPLICATION * len(applications)
        self.geometry(f"1000x{min(height, MAX_HEIGHT)}")
        self.minsize(640, 260)
        self.transient(parent)

        chart_panel = ChartPanel(self)
        chart_panel.pack(fill="both", expand=True, padx=10, pady=10)
        chart_panel.show(charts.build_timeline_figure(applications))
