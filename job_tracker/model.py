"""The job application record and the rules that follow from its dates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from .salary import parse_salary_amount
from .stages import (
    DEFAULT_ROUND_FORMAT,
    INTERVIEW_ROUNDS,
    PIPELINE,
    RoundFocus,
    RoundFormat,
    Stage,
)

NO_COMPANY = "(no company)"


def new_application_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass(frozen=True)
class RoundTags:
    """How an interview round was held and what it was about."""

    format: RoundFormat | None = None
    focus: RoundFocus | None = None

    @property
    def effective_format(self) -> RoundFormat:
        return self.format or DEFAULT_ROUND_FORMAT

    def descriptions(self) -> list[str]:
        """["Virtual", "Technical"]; the focus only when set."""
        return [self.effective_format, *([self.focus] if self.focus else [])]

    def letters(self) -> str:
        """Abbreviation for the list, e.g. "V T"."""
        focus_letter = self.focus.letter if self.focus else ""
        return " ".join(
            letter
            for letter in (self.effective_format.letter, focus_letter)
            if letter
        )


@dataclass(frozen=True)
class StageEvent:
    """One day on an application's timeline; stages reached on the same day
    share an event, in pipeline order."""

    day: date
    stages: tuple[Stage, ...]


@dataclass
class Application:
    job_title: str = ""
    company: str = ""
    status: Stage = Stage.APPLIED
    # The date each stage was reached, kept even after moving past it.
    stage_dates: dict[Stage, date] = field(default_factory=dict)
    round_tags: dict[Stage, RoundTags] = field(default_factory=dict)
    contact_email: str = ""
    url: str = ""
    job_description: str = ""
    salary: str = ""
    notes: str = ""
    last_update: date | None = None
    id: str = field(default_factory=new_application_id)

    # -- stages ------------------------------------------------------------

    @property
    def date_applied(self) -> date | None:
        return self.stage_dates.get(Stage.APPLIED)

    def has_reached(self, stage: Stage) -> bool:
        return stage in self.stage_dates

    def tags_of(self, interview_round: Stage) -> RoundTags:
        return self.round_tags.get(interview_round, RoundTags())

    def furthest_pipeline_index(self) -> int:
        """Index into PIPELINE of the furthest stage reached, -1 if none.

        Uses both the stage dates and the current status, since the status
        can be changed without filling in the matching date.
        """
        reached = [
            index
            for index, stage in enumerate(PIPELINE)
            if self.has_reached(stage)
        ]
        if self.status in PIPELINE:
            reached.append(PIPELINE.index(self.status))
        return max(reached, default=-1)

    def is_rejected(self) -> bool:
        return (
            self.has_reached(Stage.REJECTED) or self.status is Stage.REJECTED
        )

    def coding_challenge_position(self) -> str:
        """Where the optional coding challenge fell, from the dates:
        "after 1st Round", "before 1st Round", or "" without one."""
        challenge_day = self.stage_dates.get(Stage.CODING_CHALLENGE)
        if challenge_day is None:
            return ""
        # A round on the same day counts as before the challenge.
        rounds_before = [
            interview_round
            for interview_round in INTERVIEW_ROUNDS
            if self.has_reached(interview_round)
            and self.stage_dates[interview_round] <= challenge_day
        ]
        if not rounds_before:
            return "before 1st Round"
        return f"after {rounds_before[-1].short_name}"

    def stage_description(self, stage: Stage) -> str:
        """The stage with its details, e.g. "Interview - 2nd Round
        (Virtual · Technical)" or "Coding Challenge (after 1st Round)"."""
        if stage in INTERVIEW_ROUNDS:
            return (
                f"{stage} ({' · '.join(self.tags_of(stage).descriptions())})"
            )
        if stage is Stage.CODING_CHALLENGE and (
            position := self.coding_challenge_position()
        ):
            return f"{stage} ({position})"
        return stage.value

    def status_label(self) -> str:
        """The status as shown in the list: rounds with their tag letters,
        the coding challenge with where it happened."""
        if self.status in INTERVIEW_ROUNDS:
            return f"{self.status} · {self.tags_of(self.status).letters()}"
        return self.stage_description(self.status)

    def stage_events(self) -> list[StageEvent]:
        """The stages reached, grouped by day, oldest first."""
        stages_by_day: dict[date, list[Stage]] = {}
        for stage in Stage:  # enum order keeps same-day stages in order
            if stage in self.stage_dates:
                stages_by_day.setdefault(self.stage_dates[stage], []).append(
                    stage
                )
        return [
            StageEvent(day, tuple(stages))
            for day, stages in sorted(stages_by_day.items())
        ]

    # -- display -----------------------------------------------------------

    @property
    def company_display_name(self) -> str:
        return " ".join(self.company.split()) or NO_COMPANY

    @property
    def display_name(self) -> str:
        """ "Company · Job title", falling back to the id."""
        parts = (self.company.strip(), self.job_title.strip())
        return " · ".join(part for part in parts if part) or self.id

    @property
    def salary_amount(self) -> float | None:
        return parse_salary_amount(self.salary)
