"""Activity per day, and how it is shaded in the calendar."""

from datetime import date

import pytest

from job_tracker.activity import (
    HEAT_LEVELS,
    ActivityKind,
    activity_by_day,
    heat_level,
    latest_active_month,
)
from job_tracker.dates import month_title
from job_tracker.stages import Stage

from .factories import make_application

APPLICATIONS = [
    make_application(
        company="Acme",
        dates={Stage.APPLIED: "2026-09-01", Stage.ROUND_1: "2026-09-08"},
    ),
    make_application(
        company="Globex",
        dates={Stage.APPLIED: "2026-09-08", Stage.REJECTED: "2026-09-20"},
    ),
    make_application(company="Initech"),  # no dates: no activity
]


def test_applications_sent_count_the_applied_dates_only():
    days = activity_by_day(APPLICATIONS, ActivityKind.APPLIED)
    assert {day: len(events) for day, events in days.items()} == {
        date(2026, 9, 1): 1,
        date(2026, 9, 8): 1,
    }


def test_all_stage_dates_count_every_stage_reached():
    days = activity_by_day(APPLICATIONS, ActivityKind.ALL_STAGES)
    on_the_8th = days[date(2026, 9, 8)]
    assert [(e.application.company, e.stage) for e in on_the_8th] == [
        ("Acme", Stage.ROUND_1),
        ("Globex", Stage.APPLIED),
    ]
    assert sum(len(events) for events in days.values()) == 4


@pytest.mark.parametrize(
    ("count", "busiest", "level"),
    [
        (0, 5, 0),
        (1, 1, HEAT_LEVELS),
        (1, 8, 1),
        (4, 8, 2),
        (8, 8, HEAT_LEVELS),
        (3, 0, 0),
    ],
)
def test_heat_level_is_relative_to_the_busiest_day(count, busiest, level):
    assert heat_level(count, busiest) == level


def test_calendar_opens_on_the_latest_month_with_activity():
    days = [date(2026, 7, 3), date(2026, 9, 20), date(2026, 12, 1)]
    # Future dates (a planned interview) don't count.
    assert latest_active_month(days, date(2026, 10, 2)) == (2026, 9)
    assert latest_active_month([], date(2026, 10, 2)) == (2026, 10)


def test_month_title():
    assert month_title(2026, 9) == "September 2026"
