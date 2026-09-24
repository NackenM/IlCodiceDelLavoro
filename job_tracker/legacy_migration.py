"""One-time upgrade of CSV rows from before the 1st/2nd/3rd-round layout.

Back then interviews were recorded as Initial / Virtual / 2nd / 3rd /
On-site stages. They become rounds 1-3 in date order, keeping the format
the old stage name implied.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .csv_columns import ROUND_TAG_COLUMNS, STAGE_DATE_COLUMNS
from .stages import INTERVIEW_ROUNDS, RoundFormat, Stage


@dataclass(frozen=True)
class LegacyInterviewStage:
    status: str
    date_column: str
    implied_format: RoundFormat | None


# Oldest first; the order breaks ties between same-day interviews.
LEGACY_INTERVIEW_STAGES = (
    LegacyInterviewStage(
        "Interview - Initial", "date_interview_initial", None
    ),
    LegacyInterviewStage(
        "Interview - Virtual", "date_interview_virtual", RoundFormat.VIRTUAL
    ),
    LegacyInterviewStage("Interview - 2nd Round", "date_interview_2nd", None),
    LegacyInterviewStage("Interview - 3rd Round", "date_interview_3rd", None),
    LegacyInterviewStage(
        "Interview - On-site", "date_interview_onsite", RoundFormat.ON_SITE
    ),
)
LEGACY_COLUMNS = frozenset(
    stage.date_column for stage in LEGACY_INTERVIEW_STAGES
)
_LEGACY_BY_STATUS = {stage.status: stage for stage in LEGACY_INTERVIEW_STAGES}


def has_legacy_columns(column_names: Iterable[str]) -> bool:
    return not LEGACY_COLUMNS.isdisjoint(column_names)


def migrate_row(row: dict[str, str]) -> dict[str, str]:
    """The row with its legacy interview dates moved into rounds 1-3.

    Dates beyond a 3rd round are kept in the notes rather than dropped; the
    status follows its interview into the round it became.
    """
    migrated = dict(row)
    held = sorted(
        (row[stage.date_column], order, stage)
        for order, stage in enumerate(LEGACY_INTERVIEW_STAGES)
        if row.get(stage.date_column, "").strip()
    )
    round_of_legacy_status: dict[str, Stage] = {}
    for (day, _, legacy), interview_round in zip(
        held, INTERVIEW_ROUNDS, strict=False
    ):
        migrated[STAGE_DATE_COLUMNS[interview_round]] = day
        migrated[ROUND_TAG_COLUMNS[interview_round].format] = (
            legacy.implied_format or ""
        )
        round_of_legacy_status[legacy.status] = interview_round

    overflow = held[len(INTERVIEW_ROUNDS) :]
    if overflow:
        further = ", ".join(
            f"{legacy.status} {day}" for day, _, legacy in overflow
        )
        migrated["notes"] = " | ".join(
            part
            for part in (
                row.get("notes", ""),
                f"Further interviews: {further}",
            )
            if part
        )

    if row.get("status") in _LEGACY_BY_STATUS:
        # A legacy stage without a date maps to the furthest round reached.
        furthest_round = INTERVIEW_ROUNDS[
            max(min(len(held), len(INTERVIEW_ROUNDS)) - 1, 0)
        ]
        migrated["status"] = round_of_legacy_status.get(
            row["status"], furthest_round
        ).value

    for column in LEGACY_COLUMNS:
        migrated.pop(column, None)
    return migrated
