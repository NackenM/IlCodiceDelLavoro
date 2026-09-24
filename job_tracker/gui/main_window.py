"""Main application window: application list + pipeline chart."""
from __future__ import annotations

import signal
import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .. import chart, storage
from . import dates
from .add_dialog import AddApplicationDialog
from .edit_dialog import EditApplicationDialog
from .stats_dialog import StatisticsDialog

LIST_COLUMNS = [
    ("job_title", "Job Title", 200),
    ("company", "Company", 140),
    ("status", "Status", 150),
    ("contact_email", "Contact", 190),
    ("date_applied", "Date Applied", 95),
    ("last_update", "Last Update", 95),
]
DATE_LIST_COLUMNS = {"date_applied", "last_update"}
STATUS_ORDER = {status: i for i, status in enumerate(storage.STATUS_CHOICES)}
SIGNAL_CHECK_MS = 200
CHART_VIEWS = {
    "Outcome waterfall": chart.build_outcome_waterfall_figure,
    "Progress by application": chart.build_progress_figure,
}


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Application Tracker")
        self.geometry("1180x760")
        self.minsize(900, 620)

        self.df = None
        self.canvas = None
        self.sort_key = None
        self.sort_descending = False

        self._build_toolbar()
        self._build_body()
        self.refresh()

    def _build_toolbar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="+ Add Application", command=self._open_add_dialog).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Statistics", command=self._open_stats_dialog).pack(side="left", padx=(6, 0))
        ttk.Label(bar, text="Chart").pack(side="left", padx=(18, 6))
        self.chart_view_var = tk.StringVar(value=next(iter(CHART_VIEWS)))
        view_combo = ttk.Combobox(
            bar, textvariable=self.chart_view_var, values=list(CHART_VIEWS), state="readonly", width=22
        )
        view_combo.pack(side="left")
        view_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_chart())
        ttk.Label(bar, text="Click a column header to sort  ·  Double-click a row to edit").pack(side="right")

    def _build_body(self):
        paned = ttk.Panedwindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        list_frame = ttk.Frame(paned)
        columns = [c[0] for c in LIST_COLUMNS]
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        for key, heading, width in LIST_COLUMNS:
            self.tree.heading(key, text=heading, command=lambda k=key: self._sort_by(k))
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

    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_key, self.sort_descending = key, False
        self._refresh_tree()

    def _sorted_rows(self):
        rows = [row for _, row in self.df.iterrows()]
        if self.sort_key is None:
            return rows
        key = self.sort_key
        # Blank cells always go last, whichever direction is chosen.
        filled = [r for r in rows if r[key]]
        blank = [r for r in rows if not r[key]]
        if key == "status":
            sort_value = lambda r: STATUS_ORDER.get(r[key], len(STATUS_ORDER))  # pipeline order
        else:
            # Dates are stored as ISO, so plain string order is chronological.
            sort_value = lambda r: r[key].casefold()
        filled.sort(key=sort_value, reverse=self.sort_descending)
        return filled + blank

    def _refresh_tree(self):
        for key, heading, _ in LIST_COLUMNS:
            arrow = ""
            if key == self.sort_key:
                arrow = " \u25bc" if self.sort_descending else " \u25b2"
            self.tree.heading(key, text=heading + arrow)

        self.tree.delete(*self.tree.get_children())
        for row in self._sorted_rows():
            values = [
                dates.to_display(row[key]) if key in DATE_LIST_COLUMNS else row[key]
                for key, _, _ in LIST_COLUMNS
            ]
            self.tree.insert("", "end", iid=row["id"], values=values)

    def _refresh_chart(self):
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        figure = CHART_VIEWS[self.chart_view_var.get()](self.df)
        self.canvas = FigureCanvasTkAgg(figure, master=self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _open_stats_dialog(self):
        StatisticsDialog(self, self.df)

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


def _close_on_signals(app: tk.Tk) -> None:
    """Close the window cleanly on Ctrl+C / kill (e.g. PyCharm's Stop or Rerun).

    On macOS, Tk 9 installs a C signal handler that tears Tcl down from inside
    the handler; the resulting <Destroy> callbacks re-enter Python without the
    GIL and abort the interpreter. Re-registering Python handlers after Tk is
    created replaces it, so the shutdown runs on the main thread instead.
    """
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: app.destroy())

    # mainloop only checks for pending Python signals between Tk events, so
    # keep a steady trickle of events coming while the app sits idle.
    def heartbeat():
        app.after(SIGNAL_CHECK_MS, heartbeat)

    heartbeat()


def main():
    storage.ensure_csv()
    app = MainWindow()
    _close_on_signals(app)
    app.mainloop()
