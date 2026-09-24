"""Dialog for entering a new application, optionally pre-filled from the
job posting URL."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from ..dates import DISPLAY_HINT, parse_display_date
from ..emails import InvalidEmailError, normalize_email_list
from ..model import Application
from ..repository import ApplicationRepository
from ..scraper import ParsedPosting, fetch_posting
from ..stages import Stage
from .company_field import CompanyCombobox
from .form_widgets import HINT_COLOR, LabeledForm, ScrolledText
from .today_shortcut import TODAY_TOKEN, enable_today_shortcut, today_display

POLL_INTERVAL_MS = 100


class AddApplicationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        repository: ApplicationRepository,
        known_companies: list[str],
        on_saved: Callable[[], None],
    ):
        super().__init__(parent)
        self.title("Add Application")
        self.geometry("640x660")
        self.minsize(560, 520)
        self.transient(parent)
        self.grab_set()
        self.repository = repository
        self.on_saved = on_saved

        # Only the main thread may touch Tk widgets. The background fetch
        # hands its result over through this queue instead of calling widget
        # methods itself -- doing that from a worker thread races with the
        # Tk event loop and can hang instead of raising.
        self._fetch_results: queue.Queue[ParsedPosting | Exception] = (
            queue.Queue()
        )

        self._build_url_row()
        self._build_form(known_companies)
        self._build_buttons()

    def _build_url_row(self) -> None:
        url_frame = ttk.Frame(self)
        url_frame.pack(fill="x", padx=10, pady=4)
        ttk.Label(url_frame, text="Job posting URL").pack(anchor="w")
        url_row = ttk.Frame(url_frame)
        url_row.pack(fill="x")
        self.url = tk.StringVar()
        ttk.Entry(url_row, textvariable=self.url).pack(
            side="left", fill="x", expand=True
        )
        self.fetch_button = ttk.Button(
            url_row, text="Parse from URL", command=self._fetch_posting
        )
        self.fetch_button.pack(side="left", padx=(6, 0))
        self.fetch_status = ttk.Label(self, text="", foreground=HINT_COLOR)
        self.fetch_status.pack(fill="x", padx=10)

    def _build_form(self, known_companies: list[str]) -> None:
        form = LabeledForm(self)
        form.pack(fill="x", padx=10, pady=(6, 0))
        self.job_title = tk.StringVar()
        form.add_entry("Job title", self.job_title)
        self.company = tk.StringVar()
        form.add_row(
            "Company", CompanyCombobox(form, self.company, known_companies)
        )
        self.contact_email = tk.StringVar()
        form.add_entry("Contact email(s)", self.contact_email)

        date_field = ttk.Frame(form)
        self.date_applied = tk.StringVar(value=today_display())
        date_entry = ttk.Entry(
            date_field, textvariable=self.date_applied, width=14
        )
        date_entry.pack(side="left")
        enable_today_shortcut(date_entry)
        ttk.Label(
            date_field,
            text=f"{DISPLAY_HINT}  (type {TODAY_TOKEN} for today)",
            foreground=HINT_COLOR,
        ).pack(side="left", padx=(6, 0))
        form.add_row("Date applied", date_field)

        self.salary = tk.StringVar()
        form.add_salary(self.salary)

        ttk.Label(
            self,
            text="Job description  (parsed content is a preview -- "
            "edit freely before saving)",
        ).pack(anchor="w", padx=10, pady=(10, 2))
        self.job_description = ScrolledText(self, height=14)
        self.job_description.pack(fill="both", expand=True, padx=10)

    def _build_buttons(self) -> None:
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=10)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right"
        )
        ttk.Button(buttons, text="Save Application", command=self._save).pack(
            side="right", padx=(0, 6)
        )

    # -- fetching the posting ----------------------------------------------

    def _fetch_posting(self) -> None:
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning(
                "No URL", "Enter a job posting URL first.", parent=self
            )
            return
        self.fetch_button.state(["disabled"])
        self.fetch_status.configure(text="Fetching & parsing page…")

        def fetch_in_background() -> None:
            try:
                self._fetch_results.put(fetch_posting(url))
            except Exception as error:  # shown to the user, never swallowed
                self._fetch_results.put(error)

        threading.Thread(target=fetch_in_background, daemon=True).start()
        self.after(POLL_INTERVAL_MS, self._check_fetch_result)

    def _check_fetch_result(self) -> None:
        try:
            result = self._fetch_results.get_nowait()
        except queue.Empty:
            self.after(POLL_INTERVAL_MS, self._check_fetch_result)
            return
        self.fetch_button.state(["!disabled"])
        if isinstance(result, Exception):
            self.fetch_status.configure(text="")
            messagebox.showerror(
                "Parse failed",
                f"Could not parse that URL:\n{result}",
                parent=self,
            )
            return
        self.fetch_status.configure(
            text="Parsed -- review the title & description below before "
            "saving (best-effort guess)."
        )
        if result.title and not self.job_title.get().strip():
            self.job_title.set(result.title)
        self.job_description.set(result.description)

    # -- saving --------------------------------------------------------------

    def _save(self) -> None:
        job_title = self.job_title.get().strip()
        if not job_title:
            messagebox.showwarning(
                "Missing title", "Job title is required.", parent=self
            )
            return
        try:
            date_applied = parse_display_date(self.date_applied.get())
        except ValueError:
            messagebox.showwarning(
                "Invalid date",
                f"Date applied must be in {DISPLAY_HINT} format.",
                parent=self,
            )
            return
        try:
            contact_email = normalize_email_list(self.contact_email.get())
        except InvalidEmailError as error:
            messagebox.showwarning("Invalid email", str(error), parent=self)
            return

        self.repository.add(
            Application(
                job_title=job_title,
                company=self.company.get().strip(),
                status=Stage.APPLIED,
                stage_dates=(
                    {Stage.APPLIED: date_applied} if date_applied else {}
                ),
                contact_email=contact_email,
                url=self.url.get().strip(),
                job_description=self.job_description.get(),
                salary=self.salary.get().strip(),
            )
        )
        self.on_saved()
        self.destroy()
