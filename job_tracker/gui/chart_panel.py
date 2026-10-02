"""Frames that show one matplotlib figure at a time."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Pixels scrolled per notch of a mouse wheel (which reports 120 a notch).
WHEEL_NOTCH_PIXELS = 40


class ChartPanel(ttk.Frame):
    """The figure stretched to fill the panel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._canvas: FigureCanvasTkAgg | None = None

    def show(self, figure: Figure) -> None:
        """Replace the current chart with `figure`."""
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
        self._canvas = FigureCanvasTkAgg(figure, master=self)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)


class ScrollableChartPanel(ttk.Frame):
    """The figure as wide as the panel but at its own height, scrolling
    vertically (scrollbar, mouse wheel or trackpad) when that is taller
    than the panel; shorter figures stretch to fill it. An optional header
    figure stays fixed above it."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._viewport = tk.Canvas(
            self, highlightthickness=0, borderwidth=0, yscrollincrement=1
        )
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self._viewport.yview
        )
        self._viewport.configure(yscrollcommand=scrollbar.set)
        # The header shares the viewport's column, so both are equally
        # wide and the header's plot can line up with the figure's.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._viewport.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self._viewport.bind("<Configure>", lambda _event: self._fit())
        self._canvas: FigureCanvasTkAgg | None = None
        self._header_canvas: FigureCanvasTkAgg | None = None
        self._window: int | None = None
        self._figure_height = 0
        self._header_height = 0

    @property
    def natural_height(self) -> int:
        """The header's and the figure's own heights, in pixels."""
        return self._header_height + self._figure_height

    def show(self, figure: Figure, header: Figure | None = None) -> None:
        """Replace the current chart with `figure`, under `header`."""
        if self._canvas is not None:
            self._viewport.delete(self._window)
            self._canvas.get_tk_widget().destroy()
        if self._header_canvas is not None:
            self._header_canvas.get_tk_widget().destroy()
            self._header_canvas = None
        self._header_height = 0
        if header is not None:
            # Created first, so it is ready when the figure's first draw
            # lines it up.
            self._header_height = round(header.bbox.height)
            self._header_canvas = FigureCanvasTkAgg(header, master=self)
            header_widget = self._header_canvas.get_tk_widget()
            # Width 1: the grid stretches it, without the figure's own
            # width holding the window open.
            header_widget.configure(width=1, height=self._header_height)
            header_widget.grid(row=0, column=0, sticky="ew")
            self._bind_scrolling(header_widget)

        self._figure_height = round(figure.bbox.height)
        self._canvas = FigureCanvasTkAgg(figure, master=self._viewport)
        widget = self._canvas.get_tk_widget()
        self._window = self._viewport.create_window(
            0, 0, window=widget, anchor="nw"
        )
        self._bind_scrolling(widget)
        self._fit()
        self._viewport.yview_moveto(0)

    def _bind_scrolling(self, widget: tk.Widget) -> None:
        for sequence in ("<MouseWheel>", "<TouchpadScroll>"):
            widget.bind(sequence, self._on_scroll, add="+")

    def _fit(self) -> None:
        """Size the figure to the viewport's width and the larger of its
        own and the viewport's height."""
        if self._window is None:
            return
        width = self._viewport.winfo_width()
        height = max(self._figure_height, self._viewport.winfo_height())
        self._viewport.itemconfigure(self._window, width=width, height=height)
        self._viewport.configure(scrollregion=(0, 0, width, height))

    def _on_scroll(self, event: tk.Event) -> None:
        if event.type == tk.EventType.MouseWheel:
            pixels = -event.delta * WHEEL_NOTCH_PIXELS // 120
        else:  # a trackpad reports the exact distance moved
            _, delta_y = self.tk.splitlist(
                self.tk.call("tk::PreciseScrollDeltas", event.delta)
            )
            pixels = -int(delta_y)
        self._viewport.yview_scroll(pixels, "units")
