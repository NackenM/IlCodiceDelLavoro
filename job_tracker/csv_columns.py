"""Column layout of the applications CSV."""

from __future__ import annotations

from dataclasses import dataclass

from .stages import Stage

STAGE_DATE_COLUMNS: dict[Stage, str] = {
    Stage.APPLIED: "date_applied",
    Stage.ONLINE_ASSESSMENT: "date_online_assessment",
    Stage.ROUND_1: "date_round_1",
    Stage.ROUND_2: "date_round_2",
    Stage.ROUND_3: "date_round_3",
    Stage.CODING_CHALLENGE: "date_coding_challenge",
    Stage.REJECTED: "date_rejected",
    Stage.OFFER: "date_offer",
}


@dataclass(frozen=True)
class RoundTagColumns:
    format: str
    focus: str


ROUND_TAG_COLUMNS: dict[Stage, RoundTagColumns] = {
    Stage.ROUND_1: RoundTagColumns("round_1_format", "round_1_focus"),
    Stage.ROUND_2: RoundTagColumns("round_2_format", "round_2_focus"),
    Stage.ROUND_3: RoundTagColumns("round_3_format", "round_3_focus"),
}

ALL_COLUMNS: list[str] = [
    "id",
    "job_title",
    "company",
    "contact_email",
    "url",
    "job_description",
    "salary",
    "status",
    "notes",
    "last_update",
    *STAGE_DATE_COLUMNS.values(),
    *(
        column
        for tag_columns in ROUND_TAG_COLUMNS.values()
        for column in (tag_columns.format, tag_columns.focus)
    ),
]
