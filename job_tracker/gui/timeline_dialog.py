"""Window with the timeline of the applications selected in the list."""

from __future__ import annotations

import tkinter as tk

from .. import charts
from ..model import Application
from .chart_panel import ScrollableChartPanel
from .form_widgets import SCREEN_MARGIN
from .logo_store import LogoStore

WIDTH = 1000
# Taller timelines scroll inside a window of at most this height.
MAX_HEIGHT = 860
PADDING = 10


class TimelineDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        applications: list[Application],
        logos: LogoStore | None = None,
    ):
        super().__init__(parent)
        self.title("Timeline")
        self.minsize(640, 260)
        self.transient(parent)
        self.applications = applications
        self.logos = logos

        self.chart_panel = ScrollableChartPanel(self)
        self.chart_panel.pack(
            fill="both", expand=True, padx=PADDING, pady=PADDING
        )
        self._draw()
        if logos is not None:
            # Logos still on their way are drawn in where the rows are.
            logos.subscribe_while(self, lambda: self._draw(keep_scroll=True))
        height = min(
            self.chart_panel.natural_height + 2 * PADDING,
            MAX_HEIGHT,
            self.winfo_screenheight() - SCREEN_MARGIN,
        )
        self.geometry(f"{WIDTH}x{height}")

    def _draw(self, keep_scroll: bool = False) -> None:
        timeline = charts.build_timeline_figures(
            self.applications,
            logos=self.logos.image if self.logos else None,
        )
        self.chart_panel.show(
            timeline.body, header=timeline.header, keep_scroll=keep_scroll
        )
