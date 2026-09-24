"""Pop-up window for entering a new job application."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .. import scraper, storage


class AddApplicationDialog(tk.Toplevel):
    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self.title("Add Application")
        self.geometry("640x620")
        self.minsize(560, 520)
        self.on_saved = on_saved
        self.transient(parent)
        self.grab_set()

        # Only the main thread may touch Tk widgets. The background fetch
        # thread hands its result off through this queue instead of calling
        # widget methods (e.g. `self.after`) directly -- doing that from a
        # worker thread races with the Tk event loop and can hang instead
        # of raising.
        self._parse_queue: "queue.Queue" = queue.Queue()

        self._build_form()

    def _build_form(self):
        pad = {"padx": 10, "pady": 4}

        url_frame = ttk.Frame(self)
        url_frame.pack(fill="x", **pad)
        ttk.Label(url_frame, text="Job posting URL").pack(anchor="w")
        url_row = ttk.Frame(url_frame)
        url_row.pack(fill="x")
        self.url_var = tk.StringVar()
        ttk.Entry(url_row, textvariable=self.url_var).pack(side="left", fill="x", expand=True)
        self.parse_btn = ttk.Button(url_row, text="Parse from URL", command=self._parse_url)
        self.parse_btn.pack(side="left", padx=(6, 0))

        self.status_label = ttk.Label(self, text="", foreground="#52514e")
        self.status_label.pack(fill="x", padx=10)

        form = ttk.Frame(self)
        form.pack(fill="x", padx=10, pady=(6, 0))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Job title").grid(row=0, column=0, sticky="w", pady=4)
        self.title_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Company").grid(row=1, column=0, sticky="w", pady=4)
        self.company_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.company_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Date applied").grid(row=2, column=0, sticky="w", pady=4)
        date_row = ttk.Frame(form)
        date_row.grid(row=2, column=1, sticky="ew", pady=4)
        self.date_applied_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(date_row, textvariable=self.date_applied_var, width=14).pack(side="left")
        ttk.Label(date_row, text="YYYY-MM-DD").pack(side="left", padx=(6, 0))

        ttk.Label(
            self, text="Job description  (parsed content is a preview -- edit freely before saving)"
        ).pack(anchor="w", padx=10, pady=(10, 2))
        desc_frame = ttk.Frame(self)
        desc_frame.pack(fill="both", expand=True, padx=10)
        self.desc_text = tk.Text(desc_frame, wrap="word", height=14)
        scrollbar = ttk.Scrollbar(desc_frame, command=self.desc_text.yview)
        self.desc_text.configure(yscrollcommand=scrollbar.set)
        self.desc_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btn_row, text="Save Application", command=self._save).pack(side="right", padx=(0, 6))

    def _parse_url(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Enter a job posting URL first.", parent=self)
            return
        self.parse_btn.state(["disabled"])
        self.status_label.configure(text="Fetching & parsing page…")

        def worker():
            try:
                result = scraper.fetch_and_parse(url)
                self._parse_queue.put(("ok", result))
            except Exception as exc:  # surfaced to the user via the dialog, never swallowed
                self._parse_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_parse_queue)

    def _poll_parse_queue(self):
        try:
            kind, payload = self._parse_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_parse_queue)
            return
        if kind == "ok":
            self._apply_parse_result(payload)
        else:
            self._parse_failed(payload)

    def _apply_parse_result(self, result: dict):
        self.parse_btn.state(["!disabled"])
        self.status_label.configure(
            text="Parsed -- review the title & description below before saving (best-effort guess)."
        )
        if result["title"] and not self.title_var.get().strip():
            self.title_var.set(result["title"])
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", result["description"])

    def _parse_failed(self, exc: Exception):
        self.parse_btn.state(["!disabled"])
        self.status_label.configure(text="")
        messagebox.showerror("Parse failed", f"Could not parse that URL:\n{exc}", parent=self)

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Missing title", "Job title is required.", parent=self)
            return
        date_applied = self.date_applied_var.get().strip()
        if date_applied and not _is_valid_date(date_applied):
            messagebox.showwarning("Invalid date", "Date applied must be in YYYY-MM-DD format.", parent=self)
            return

        record = {
            "job_title": title,
            "company": self.company_var.get().strip(),
            "url": self.url_var.get().strip(),
            "job_description": self.desc_text.get("1.0", "end").strip(),
            "status": storage.STATUS_APPLIED,
            "notes": "",
            "date_applied": date_applied,
        }
        storage.add_application(record)
        self.on_saved()
        self.destroy()


def _is_valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False
