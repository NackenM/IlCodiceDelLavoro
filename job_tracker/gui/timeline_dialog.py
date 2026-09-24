"""Pop-up window with the timeline of the applications selected in the list."""
from __future__ import annotations

import tkinter as tk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .. import chart

# Window height grows with the number of applications, up to this cap.
MAX_HEIGHT = 860


class TimelineDialog(tk.Toplevel):
    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self.title("Timeline")
        self.geometry(f"1000x{min(160 + 62 * len(df), MAX_HEIGHT)}")
        self.minsize(640, 260)
        self.transient(parent)

        canvas = FigureCanvasTkAgg(chart.build_timeline_figure(df), master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
