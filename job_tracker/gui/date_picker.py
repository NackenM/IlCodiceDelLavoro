"""A small month calendar for picking a date instead of typing it."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from ..dates import format_display_date, parse_display_date

WEEKDAY_HEADINGS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
OTHER_MONTH_COLOR = "#9a9893"


def month_grid(year: int, month: int) -> list[list[date]]:
    """The weeks (Monday first) covering the month, padded with days of
    the neighbouring months so every week is complete."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)


def shift_month(year: int, month: int, months: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + months
    return index // 12, index % 12 + 1


def initial_date(text: str, today: date) -> date:
    """The date already in the field, or today if it is blank/invalid."""
    try:
        return parse_display_date(text) or today
    except ValueError:
        return today


class DatePickerButton(ttk.Button):
    """Opens a calendar below itself; the picked day is written into
    `variable` as DD.MM.YYYY."""

    def __init__(self, master, variable: tk.StringVar, **kwargs):
        super().__init__(
            master, text="📅", width=3, command=self._open, **kwargs
        )
        self.variable = variable

    def _open(self) -> None:
        CalendarPopup(self, self.variable)


class CalendarPopup(tk.Toplevel):
    def __init__(self, anchor: tk.Widget, variable: tk.StringVar):
        dialog = anchor.winfo_toplevel()
        super().__init__(dialog)
        self.title("Pick a date")
        self.resizable(False, False)
        self.transient(dialog)
        self._dialog = dialog
        self._variable = variable
        self._today = date.today()
        self._selected = initial_date(variable.get(), self._today)
        self._year, self._month = self._selected.year, self._selected.month

        header = ttk.Frame(self, padding=(6, 6, 6, 0))
        header.pack(fill="x")
        ttk.Button(
            header, text="‹", width=2, command=lambda: self._move(-1)
        ).pack(side="left")
        self._heading = ttk.Label(header, anchor="center")
        self._heading.pack(side="left", fill="x", expand=True)
        ttk.Button(
            header, text="›", width=2, command=lambda: self._move(1)
        ).pack(side="right")

        self._days = ttk.Frame(self, padding=6)
        self._days.pack()
        ttk.Button(self, text="Today", command=self._pick_today).pack(
            pady=(0, 6)
        )

        self.bind("<Escape>", lambda _event: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._draw()
        self.geometry(
            f"+{anchor.winfo_rootx()}"
            f"+{anchor.winfo_rooty() + anchor.winfo_height()}"
        )
        # The Add/Edit dialogs hold the grab; take it over while open.
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

    def _move(self, months: int) -> None:
        self._year, self._month = shift_month(self._year, self._month, months)
        self._draw()

    def _draw(self) -> None:
        self._heading.configure(
            text=f"{calendar.month_name[self._month]} {self._year}"
        )
        for child in self._days.winfo_children():
            child.destroy()
        for column, heading in enumerate(WEEKDAY_HEADINGS):
            ttk.Label(self._days, text=heading, anchor="center").grid(
                row=0, column=column, sticky="ew"
            )
        for row, week in enumerate(month_grid(self._year, self._month), 1):
            for column, day in enumerate(week):
                button = tk.Button(
                    self._days,
                    text=str(day.day),
                    width=2,
                    relief="flat",
                    command=lambda day=day: self._pick(day),
                )
                if day.month != self._month:
                    button.configure(foreground=OTHER_MONTH_COLOR)
                if day == self._selected:
                    button.configure(font=("TkDefaultFont", 0, "bold"))
                elif day == self._today:
                    button.configure(font=("TkDefaultFont", 0, "underline"))
                button.grid(row=row, column=column, padx=1, pady=1)

    def _pick_today(self) -> None:
        self._pick(self._today)

    def _pick(self, day: date) -> None:
        self._variable.set(format_display_date(day))
        self._close()

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
        self._dialog.grab_set()
