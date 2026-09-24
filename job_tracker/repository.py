"""Loading and saving applications as a CSV file."""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date
from pathlib import Path

from . import legacy_migration
from .csv_columns import ALL_COLUMNS, ROUND_TAG_COLUMNS, STAGE_DATE_COLUMNS
from .model import Application, RoundTags
from .stages import PIPELINE, RoundFocus, RoundFormat, Stage

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "applications.csv"
)
# The original file is kept under this suffix when the legacy migration
# rewrites it.
LEGACY_BACKUP_SUFFIX = ".before-rounds.csv"


class ApplicationNotFoundError(KeyError):
    pass


class ApplicationRepository:
    """All applications, stored as one CSV row each (dates as ISO)."""

    def __init__(
        self,
        csv_path: Path = DEFAULT_CSV_PATH,
        today: Callable[[], date] = date.today,
    ):
        self.csv_path = csv_path
        self._today = today

    def load_all(self) -> list[Application]:
        rows = self._read_rows()
        return [application_from_row(row) for row in rows]

    def add(self, application: Application) -> Application:
        saved = replace(application, last_update=self._today())
        self._write_all([*self.load_all(), saved])
        return saved

    def update(self, application: Application) -> Application:
        applications = self.load_all()
        index = self._index_of(applications, application.id)
        applications[index] = replace(application, last_update=self._today())
        self._write_all(applications)
        return applications[index]

    def delete(self, application_id: str) -> None:
        applications = self.load_all()
        del applications[self._index_of(applications, application_id)]
        self._write_all(applications)

    # -- file access -------------------------------------------------------

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.csv_path.exists():
            return []
        with self.csv_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            columns = reader.fieldnames or []
        if legacy_migration.has_legacy_columns(columns):
            rows = self._migrate_legacy_file(rows)
        return rows

    def _migrate_legacy_file(
        self, rows: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        backup = self.csv_path.with_name(
            self.csv_path.stem + LEGACY_BACKUP_SUFFIX
        )
        if not backup.exists():
            backup.write_bytes(self.csv_path.read_bytes())
        migrated = [legacy_migration.migrate_row(row) for row in rows]
        self._write_rows(migrated)
        return migrated

    def _write_all(self, applications: Iterable[Application]) -> None:
        self._write_rows(application_to_row(app) for app in applications)

    def _write_rows(self, rows: Iterable[dict[str, str]]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=ALL_COLUMNS,
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _index_of(applications: list[Application], application_id: str) -> int:
        for index, application in enumerate(applications):
            if application.id == application_id:
                return index
        raise ApplicationNotFoundError(application_id)


# -- row <-> Application ---------------------------------------------------


def _parse_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip()) if text.strip() else None
    except ValueError:
        return None


def _parse_enum[E: (RoundFormat, RoundFocus)](
    enum_type: type[E], text: str
) -> E | None:
    try:
        return enum_type(text) if text else None
    except ValueError:
        return None


def _parse_status(text: str, stage_dates: dict[Stage, date]) -> Stage:
    """The stored status; an unknown one falls back to the furthest stage
    reached."""
    try:
        return Stage(text)
    except ValueError:
        reached = [stage for stage in PIPELINE if stage in stage_dates]
        return reached[-1] if reached else Stage.APPLIED


def application_from_row(row: dict[str, str]) -> Application:
    def text(column: str) -> str:
        return (row.get(column) or "").strip()

    stage_dates = {
        stage: day
        for stage, column in STAGE_DATE_COLUMNS.items()
        if (day := _parse_iso_date(text(column))) is not None
    }
    round_tags = {
        interview_round: tags
        for interview_round, columns in ROUND_TAG_COLUMNS.items()
        if (
            tags := RoundTags(
                format=_parse_enum(RoundFormat, text(columns.format)),
                focus=_parse_enum(RoundFocus, text(columns.focus)),
            )
        )
        != RoundTags()
    }
    return Application(
        id=text("id"),
        job_title=text("job_title"),
        company=text("company"),
        status=_parse_status(text("status"), stage_dates),
        stage_dates=stage_dates,
        round_tags=round_tags,
        contact_email=text("contact_email"),
        url=text("url"),
        job_description=row.get("job_description") or "",
        salary=text("salary"),
        notes=text("notes"),
        last_update=_parse_iso_date(text("last_update")),
    )


def application_to_row(application: Application) -> dict[str, str]:
    row = {
        "id": application.id,
        "job_title": application.job_title,
        "company": application.company,
        "contact_email": application.contact_email,
        "url": application.url,
        "job_description": application.job_description,
        "salary": application.salary,
        "status": application.status.value,
        "notes": application.notes,
        "last_update": (
            application.last_update.isoformat()
            if application.last_update
            else ""
        ),
    }
    for stage, column in STAGE_DATE_COLUMNS.items():
        day = application.stage_dates.get(stage)
        row[column] = day.isoformat() if day else ""
    for interview_round, columns in ROUND_TAG_COLUMNS.items():
        tags = application.tags_of(interview_round)
        row[columns.format] = tags.format.value if tags.format else ""
        row[columns.focus] = tags.focus.value if tags.focus else ""
    return row
