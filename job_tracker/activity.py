"""What happened on which day: applications sent, or every stage reached,
for the calendar heatmap."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .model import Application
from .stages import Stage


class ActivityKind(StrEnum):
    """What a day's activity counts."""

    APPLIED = "Applications sent"
    ALL_STAGES = "All stage dates"


# Heat levels above "nothing that day"; the busiest day gets the top one.
HEAT_LEVELS = 4


@dataclass(frozen=True)
class DayEvent:
    application: Application
    stage: Stage


def activity_by_day(
    applications: Iterable[Application], kind: ActivityKind
) -> dict[date, list[DayEvent]]:
    """Each day with something on it, and what: the applications sent that
    day, or every stage any application reached that day."""
    stages = (Stage.APPLIED,) if kind is ActivityKind.APPLIED else tuple(Stage)
    days: dict[date, list[DayEvent]] = {}
    for application in applications:
        for stage in stages:
            if (day := application.stage_dates.get(stage)) is not None:
                days.setdefault(day, []).append(DayEvent(application, stage))
    return days


def heat_level(count: int, busiest: int) -> int:
    """0 for an empty day, else 1..HEAT_LEVELS relative to the busiest
    day, so a month's colors compare with every other month's."""
    if count <= 0 or busiest <= 0:
        return 0
    return min(HEAT_LEVELS, math.ceil(HEAT_LEVELS * count / busiest))


def latest_active_month(days: Iterable[date], today: date) -> tuple[int, int]:
    """The month of the latest activity up to today, or today's month
    without any: where the calendar opens."""
    past = [day for day in days if day <= today]
    latest = max(past, default=today)
    return latest.year, latest.month
