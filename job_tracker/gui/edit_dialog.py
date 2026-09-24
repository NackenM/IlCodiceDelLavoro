"""Dialog for updating or deleting an existing application."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from tkinter import messagebox, ttk

from ..dates import (
    DISPLAY_HINT,
    format_display_date,
    is_valid_display_date,
    parse_display_date,
)
from ..emails import InvalidEmailError, normalize_email_list
from ..model import Application, RoundTags
from ..repository import ApplicationRepository
from ..stages import (
    DEFAULT_ROUND_FORMAT,
    INTERVIEW_ROUNDS,
    RoundFocus,
    RoundFormat,
    Stage,
)
from .company_field import CompanyCombobox
from .form_widgets import HINT_COLOR, LabeledForm, ScrolledText
from .today_shortcut import TODAY_TOKEN, enable_today_shortcut, today_display


@dataclass
class RoundTagFields:
    """The Format / Focus dropdowns of one interview round."""

    format: tk.StringVar
    focus: tk.StringVar

    def tags(self) -> RoundTags:
        return RoundTags(
            format=RoundFormat(self.format.get()),
            focus=RoundFocus(self.focus.get()) if self.focus.get() else None,
        )


class EditApplicationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        repository: ApplicationRepository,
        application: Application,
        known_companies: list[str],
        on_changed: Callable[[], None],
    ):
        super().__init__(parent)
        self.title(f"Edit Application -- {application.job_title}")
        self.geometry("760x860")
        self.minsize(560, 560)
        self.transient(parent)
        self.grab_set()
        self.repository = repository
        self.application = application
        self.on_changed = on_changed

        self._build_details(known_companies)
        ttk.Separator(self).pack(fill="x", padx=10, pady=8)
        self._build_stage_dates()
        ttk.Separator(self).pack(fill="x", padx=10, pady=8)
        self._build_description_and_notes()
        self._build_buttons()

    def _build_details(self, known_companies: list[str]) -> None:
        application = self.application
        form = LabeledForm(self)
        form.pack(fill="x", padx=10, pady=(10, 0))
        self.job_title = tk.StringVar(value=application.job_title)
        form.add_entry("Job title", self.job_title)
        self.company = tk.StringVar(value=application.company)
        form.add_row(
            "Company", CompanyCombobox(form, self.company, known_companies)
        )
        self.contact_email = tk.StringVar(value=application.contact_email)
        form.add_entry("Contact email(s)", self.contact_email)
        self.url = tk.StringVar(value=application.url)
        form.add_entry("URL", self.url)
        self.salary = tk.StringVar(value=application.salary)
        form.add_salary(self.salary)

        self.status = tk.StringVar(value=application.status)
        form.add_row(
            "Current status",
            ttk.Combobox(
                form,
                textvariable=self.status,
                values=[stage.value for stage in Stage],
                state="readonly",
            ),
        )
        last_update = format_display_date(application.last_update) or "--"
        form.add_row(
            "Last update",
            ttk.Label(
                form, text=f"{last_update}  (set automatically on save)"
            ),
            stretch=False,
        )

    def _build_stage_dates(self) -> None:
        ttk.Label(
            self,
            text=f"Stage dates  ({DISPLAY_HINT}, type {TODAY_TOKEN} for "
            "today, leave blank if not reached)",
        ).pack(anchor="w", padx=10)
        grid = ttk.Frame(self)
        grid.pack(fill="x", padx=10, pady=(4, 0))

        self.stage_dates: dict[Stage, tk.StringVar] = {}
        self.round_tag_fields: dict[Stage, RoundTagFields] = {}
        for row, stage in enumerate(Stage):
            date_text = tk.StringVar(
                value=format_display_date(
                    self.application.stage_dates.get(stage)
                )
            )
            self.stage_dates[stage] = date_text
            label = (
                f"{stage} (optional)"
                if stage is Stage.CODING_CHALLENGE
                else stage.value
            )
            ttk.Label(grid, text=label).grid(
                row=row, column=0, sticky="w", pady=3
            )
            entry = ttk.Entry(grid, textvariable=date_text, width=12)
            entry.grid(row=row, column=1, padx=(8, 0), pady=3)
            enable_today_shortcut(entry)
            ttk.Button(
                grid,
                text="Today",
                width=6,
                command=lambda var=date_text: var.set(today_display()),
            ).grid(row=row, column=2, padx=(4, 0), pady=3)

            if stage in INTERVIEW_ROUNDS:
                self.round_tag_fields[stage] = self._build_round_tag_fields(
                    grid, row, self.application.tags_of(stage)
                )
            elif stage is Stage.CODING_CHALLENGE:
                self.coding_challenge_position = ttk.Label(
                    grid, foreground=HINT_COLOR
                )
                self.coding_challenge_position.grid(
                    row=row, column=3, sticky="w", padx=(12, 0)
                )

        # Keep "-> after 1st Round" in step with the dates as they are typed.
        for stage in (*INTERVIEW_ROUNDS, Stage.CODING_CHALLENGE):
            self.stage_dates[stage].trace_add(
                "write", lambda *_: self._show_coding_challenge_position()
            )
        self._show_coding_challenge_position()

    @staticmethod
    def _build_round_tag_fields(
        grid: ttk.Frame, row: int, tags: RoundTags
    ) -> RoundTagFields:
        """Format always has a value (virtual unless set); focus may stay
        blank."""
        frame = ttk.Frame(grid)
        frame.grid(row=row, column=3, sticky="w", padx=(12, 0))
        fields = RoundTagFields(
            format=tk.StringVar(value=tags.format or DEFAULT_ROUND_FORMAT),
            focus=tk.StringVar(value=tags.focus or ""),
        )
        for caption, variable, choices in (
            ("Format", fields.format, [f.value for f in RoundFormat]),
            ("Focus", fields.focus, ["", *(f.value for f in RoundFocus)]),
        ):
            ttk.Label(frame, text=caption).pack(side="left", padx=(0, 4))
            ttk.Combobox(
                frame,
                textvariable=variable,
                values=choices,
                state="readonly",
                width=13,
            ).pack(side="left", padx=(0, 10))
        return fields

    def _build_description_and_notes(self) -> None:
        ttk.Label(self, text="Job description").pack(anchor="w", padx=10)
        self.job_description = ScrolledText(
            self, height=8, initial_text=self.application.job_description
        )
        self.job_description.pack(fill="both", expand=True, padx=10)

        ttk.Label(self, text="Notes").pack(anchor="w", padx=10, pady=(8, 2))
        self.notes = tk.StringVar(value=self.application.notes)
        notes_entry = ttk.Entry(self, textvariable=self.notes)
        notes_entry.pack(fill="x", padx=10)
        enable_today_shortcut(notes_entry)

    def _build_buttons(self) -> None:
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=10)
        ttk.Button(buttons, text="Delete", command=self._delete).pack(
            side="left"
        )
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right"
        )
        ttk.Button(buttons, text="Save Changes", command=self._save).pack(
            side="right", padx=(0, 6)
        )

    # -- behaviour -----------------------------------------------------------

    def _entered_stage_dates(self) -> dict[Stage, date]:
        """The complete, valid dates entered; blank or half-typed ones are
        left out."""
        entered = {}
        for stage, date_text in self.stage_dates.items():
            if is_valid_display_date(date_text.get()):
                day = parse_display_date(date_text.get())
                if day:
                    entered[stage] = day
        return entered

    def _show_coding_challenge_position(self) -> None:
        preview = Application(stage_dates=self._entered_stage_dates())
        position = preview.coding_challenge_position()
        self.coding_challenge_position.configure(
            text=f"→ {position}" if position else ""
        )

    def _save(self) -> None:
        for stage, date_text in self.stage_dates.items():
            if not is_valid_display_date(date_text.get()):
                messagebox.showwarning(
                    "Invalid date",
                    f"'{stage}' date must be in {DISPLAY_HINT} format.",
                    parent=self,
                )
                return
        try:
            contact_email = normalize_email_list(self.contact_email.get())
        except InvalidEmailError as error:
            messagebox.showwarning("Invalid email", str(error), parent=self)
            return

        self.repository.update(
            replace(
                self.application,
                job_title=self.job_title.get().strip(),
                company=self.company.get().strip(),
                contact_email=contact_email,
                url=self.url.get().strip(),
                salary=self.salary.get().strip(),
                status=Stage(self.status.get()),
                stage_dates=self._entered_stage_dates(),
                round_tags={
                    interview_round: tag_fields.tags()
                    for interview_round, tag_fields in (
                        self.round_tag_fields.items()
                    )
                },
                job_description=self.job_description.get(),
                notes=self.notes.get().strip(),
            )
        )
        self.on_changed()
        self.destroy()

    def _delete(self) -> None:
        if messagebox.askyesno(
            "Delete application",
            "Remove this application permanently?",
            parent=self,
        ):
            self.repository.delete(self.application.id)
            self.on_changed()
            self.destroy()
