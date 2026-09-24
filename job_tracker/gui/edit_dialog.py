"""Pop-up window for updating an existing job application."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .. import storage
from . import dates
from .add_dialog import SALARY_HINT
from .company_field import CompanyCombobox


class EditApplicationDialog(tk.Toplevel):
    def __init__(self, parent, app_row: dict, on_saved, on_deleted):
        super().__init__(parent)
        self.app_id = app_row["id"]
        self.on_saved = on_saved
        self.on_deleted = on_deleted
        self.title(f"Edit Application -- {app_row.get('job_title', '')}")
        self.geometry("640x780")
        self.minsize(560, 560)
        self.transient(parent)
        self.grab_set()

        self._build_form(app_row)

    def _build_form(self, row: dict):
        form = ttk.Frame(self)
        form.pack(fill="x", padx=10, pady=(10, 0))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Job title").grid(row=0, column=0, sticky="w", pady=4)
        self.title_var = tk.StringVar(value=row.get("job_title", ""))
        ttk.Entry(form, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Company").grid(row=1, column=0, sticky="w", pady=4)
        self.company_var = tk.StringVar(value=row.get("company", ""))
        CompanyCombobox(form, textvariable=self.company_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Contact email(s)").grid(row=2, column=0, sticky="w", pady=4)
        self.contact_var = tk.StringVar(value=row.get("contact_email", ""))
        ttk.Entry(form, textvariable=self.contact_var).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="URL").grid(row=3, column=0, sticky="w", pady=4)
        self.url_var = tk.StringVar(value=row.get("url", ""))
        ttk.Entry(form, textvariable=self.url_var).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Salary").grid(row=4, column=0, sticky="w", pady=4)
        salary_row = ttk.Frame(form)
        salary_row.grid(row=4, column=1, sticky="ew", pady=4)
        self.salary_var = tk.StringVar(value=row.get("salary", ""))
        ttk.Entry(salary_row, textvariable=self.salary_var, width=24).pack(side="left")
        ttk.Label(salary_row, text=SALARY_HINT).pack(side="left", padx=(6, 0))

        ttk.Label(form, text="Current status").grid(row=5, column=0, sticky="w", pady=4)
        self.status_var = tk.StringVar(value=row.get("status", storage.STATUS_APPLIED))
        status_combo = ttk.Combobox(
            form, textvariable=self.status_var, values=storage.STATUS_CHOICES, state="readonly"
        )
        status_combo.grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Last update").grid(row=6, column=0, sticky="w", pady=4)
        last_update = dates.to_display(row.get("last_update", "")) or "--"
        ttk.Label(form, text=f"{last_update}  (set automatically on save)").grid(
            row=6, column=1, sticky="w", pady=4
        )

        ttk.Separator(self).pack(fill="x", padx=10, pady=8)

        ttk.Label(
            self,
            text=f"Stage dates  ({dates.DISPLAY_HINT}, type {dates.TODAY_TOKEN} for today, "
            "leave blank if not reached)",
        ).pack(anchor="w", padx=10)
        dates_frame = ttk.Frame(self)
        dates_frame.pack(fill="x", padx=10, pady=(4, 0))
        dates_frame.columnconfigure(0, weight=1)
        dates_frame.columnconfigure(1, weight=1)

        self.date_vars: dict[str, tk.StringVar] = {}
        for i, status in enumerate(storage.STATUS_CHOICES):
            col_field = storage.STATUS_DATE_COLUMNS[status]
            var = tk.StringVar(value=dates.to_display(row.get(col_field, "")))
            self.date_vars[status] = var
            r, c = divmod(i, 2)
            cell = ttk.Frame(dates_frame)
            cell.grid(row=r, column=c, sticky="ew", padx=(0, 12), pady=3)
            ttk.Label(cell, text=status, width=20).pack(side="left")
            entry = ttk.Entry(cell, textvariable=var, width=12)
            entry.pack(side="left")
            dates.enable_today_shortcut(entry)
            ttk.Button(
                cell, text="Today", width=6,
                command=lambda v=var: v.set(dates.today_display()),
            ).pack(side="left", padx=(4, 0))

        ttk.Separator(self).pack(fill="x", padx=10, pady=8)

        ttk.Label(self, text="Job description").pack(anchor="w", padx=10)
        desc_frame = ttk.Frame(self)
        desc_frame.pack(fill="both", expand=True, padx=10)
        self.desc_text = tk.Text(desc_frame, wrap="word", height=8)
        scrollbar = ttk.Scrollbar(desc_frame, command=self.desc_text.yview)
        self.desc_text.configure(yscrollcommand=scrollbar.set)
        self.desc_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.desc_text.insert("1.0", row.get("job_description", ""))
        dates.enable_today_shortcut(self.desc_text)

        ttk.Label(self, text="Notes").pack(anchor="w", padx=10, pady=(8, 2))
        self.notes_var = tk.StringVar(value=row.get("notes", ""))
        notes_entry = ttk.Entry(self, textvariable=self.notes_var)
        notes_entry.pack(fill="x", padx=10)
        dates.enable_today_shortcut(notes_entry)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_row, text="Delete", command=self._delete).pack(side="left")
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btn_row, text="Save Changes", command=self._save).pack(side="right", padx=(0, 6))

    def _save(self):
        for status, var in self.date_vars.items():
            value = var.get().strip()
            if not dates.is_valid_display_date(value):
                messagebox.showwarning(
                    "Invalid date", f"'{status}' date must be in {dates.DISPLAY_HINT} format.", parent=self
                )
                return
        try:
            contact_email = storage.normalize_emails(self.contact_var.get())
        except ValueError as exc:
            messagebox.showwarning("Invalid email", f"'{exc}' is not a valid email address.", parent=self)
            return

        updates = {
            "job_title": self.title_var.get().strip(),
            "company": self.company_var.get().strip(),
            "contact_email": contact_email,
            "url": self.url_var.get().strip(),
            "salary": self.salary_var.get().strip(),
            "status": self.status_var.get(),
            "notes": self.notes_var.get().strip(),
            "job_description": self.desc_text.get("1.0", "end").strip(),
        }
        for status, var in self.date_vars.items():
            updates[storage.STATUS_DATE_COLUMNS[status]] = dates.to_iso(var.get().strip())

        storage.update_application(self.app_id, updates)
        self.on_saved()
        self.destroy()

    def _delete(self):
        if messagebox.askyesno("Delete application", "Remove this application permanently?", parent=self):
            storage.delete_application(self.app_id)
            self.on_deleted()
            self.destroy()
