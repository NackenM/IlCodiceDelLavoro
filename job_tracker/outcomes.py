"""Sort each application into exactly one outcome, for the charts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta
from enum import StrEnum

from .model import Application
from .stages import PIPELINE, Stage

# An application without any reply counts as ghosted once it is this old;
# younger ones are still awaiting a reply.
GHOSTED_AFTER_DAYS = 30


class Outcome(StrEnum):
    """Mutually exclusive outcomes, in display order."""

    OFFER = "Offer"
    IN_PROGRESS = "In progress"
    REJECTED_AFTER_STAGE = "Rejected after a stage"
    REJECTED_RIGHT_AWAY = "Rejected right away"
    GHOSTED = "Ghosted"
    AWAITING_REPLY = "Awaiting reply"


# Still open: nobody has said no (yet).
OPEN_OUTCOMES = frozenset(
    {Outcome.IN_PROGRESS, Outcome.AWAITING_REPLY, Outcome.GHOSTED}
)

# Each success-rate target is a set of outcomes, measured against all
# applications in the selected time range.
SUCCESS_TARGETS: dict[str, frozenset[Outcome]] = {
    "Offer": frozenset({Outcome.OFFER}),
    "Assessment or interview": frozenset(
        {Outcome.OFFER, Outcome.IN_PROGRESS, Outcome.REJECTED_AFTER_STAGE}
    ),
    "Any reply (not ghosted)": frozenset(
        {
            Outcome.OFFER,
            Outcome.IN_PROGRESS,
            Outcome.REJECTED_AFTER_STAGE,
            Outcome.REJECTED_RIGHT_AWAY,
        }
    ),
    "Rejection": frozenset(
        {Outcome.REJECTED_AFTER_STAGE, Outcome.REJECTED_RIGHT_AWAY}
    ),
    "Ghosted": frozenset({Outcome.GHOSTED}),
}

# Time-range filter choices: label -> days back (None = everything).
APPLIED_WITHIN_CHOICES: dict[str, int | None] = {
    "All time": None,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "Last 12 months": 365,
}


def classify(application: Application, today: date | None = None) -> Outcome:
    today = today or date.today()
    furthest = application.furthest_pipeline_index()
    if furthest == PIPELINE.index(Stage.OFFER):
        return Outcome.OFFER
    got_past_application = furthest > 0
    if application.is_rejected():
        return (
            Outcome.REJECTED_AFTER_STAGE
            if got_past_application
            else Outcome.REJECTED_RIGHT_AWAY
        )
    if got_past_application:
        return Outcome.IN_PROGRESS
    applied = application.date_applied
    if applied is None:  # can't tell how long it has been
        return Outcome.AWAITING_REPLY
    if (today - applied).days >= GHOSTED_AFTER_DAYS:
        return Outcome.GHOSTED
    return Outcome.AWAITING_REPLY


def rejection_stage(application: Application) -> Stage:
    """The last pipeline stage reached before the rejection."""
    return PIPELINE[max(application.furthest_pipeline_index(), 0)]


def count_outcomes(
    applications: Iterable[Application], today: date | None = None
) -> Counter[Outcome]:
    return Counter(
        classify(application, today) for application in applications
    )


def group_by_outcome(
    applications: Iterable[Application], today: date | None = None
) -> dict[Outcome, list[Application]]:
    """Every outcome as a key (in display order), even when empty."""
    groups: dict[Outcome, list[Application]] = {o: [] for o in Outcome}
    for application in applications:
        groups[classify(application, today)].append(application)
    return groups


def applied_within(
    applications: Iterable[Application],
    days: int | None,
    today: date | None = None,
) -> list[Application]:
    """Applications sent within the last `days` days (all for None);
    applications without an applied date only count for None."""
    if days is None:
        return list(applications)
    cutoff = (today or date.today()) - timedelta(days=days)
    return [
        application
        for application in applications
        if application.date_applied and application.date_applied >= cutoff
    ]
