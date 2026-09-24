"""Main application window: application list + pipeline waterfall chart."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .. import chart, storage
from .add_dialog import AddApplicationDialog
from .edit_dialog import EditApplicationDialog

LIST_COLUMNS = [
    ("job_title", "Job Title", 220),
    ("company", "Company", 150),
    ("status", "Status", 160),
    ("date_applied", "Date Applied", 100),
]


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Application Tracker")
        self.geometry("1180x760")
        self.minsize(900, 620)

        self.df = None
        self.canvas = None

        self._build_toolbar()
        self._build_body()
        self.refresh()

    def _build_toolbar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="+ Add Application", command=self._open_add_dialog).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))
        ttk.Label(bar, text="Double-click a row to edit").pack(side="right")

    def _build_body(self):
        paned = ttk.Panedwindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        list_frame = ttk.Frame(paned)
        columns = [c[0] for c in LIST_COLUMNS]
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        for key, heading, width in LIST_COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_row_double_click)
        paned.add(list_frame, weight=2)

        chart_frame = ttk.Frame(paned)
        self.chart_container = chart_frame
        paned.add(chart_frame, weight=3)

    def refresh(self):
        self.df = storage.load_applications()
        self._refresh_tree()
        self._refresh_chart()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for _, row in self.df.iterrows():
            values = [row.get(key, "") for key, _, _ in LIST_COLUMNS]
            self.tree.insert("", "end", iid=row["id"], values=values)

    def _refresh_chart(self):
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        figure = chart.build_waterfall_figure(self.df)
        self.canvas = FigureCanvasTkAgg(figure, master=self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _open_add_dialog(self):
        AddApplicationDialog(self, on_saved=self.refresh)

    def _on_row_double_click(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        app_id = selection[0]
        row = self.df[self.df["id"] == app_id]
        if row.empty:
            return
        EditApplicationDialog(self, row.iloc[0].to_dict(), on_saved=self.refresh, on_deleted=self.refresh)


def main():
    storage.ensure_csv()
    app = MainWindow()
    app.mainloop()
