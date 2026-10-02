"""The GUI's pure helpers: list sorting and company completion."""

from datetime import date

import pytest

from job_tracker.dates import month_grid, shift_month
from job_tracker.gui.application_list import (
    COLUMNS_BY_KEY,
    sort_applications,
    status_sort_value,
    status_text,
)
from job_tracker.gui.company_field import companies_containing, completion_for
from job_tracker.gui.date_picker import initial_date
from job_tracker.stages import Stage

from .factories import TODAY, make_application


def sorted_values(applications, key, descending=False):
    column = COLUMNS_BY_KEY[key]
    return [
        column.cell_text(a)
        for a in sort_applications(applications, column, descending)
    ]


@pytest.mark.parametrize("descending", [False, True])
def test_salary_sorts_by_amount_and_keeps_unknown_last(descending):
    applications = [
        make_application(salary=text)
        for text in ["", "negotiable", "80-90k €", "€65.000", "70k"]
    ]
    values = sorted_values(applications, "salary", descending)
    amounts = ["€65.000", "70k", "80-90k €"]
    assert values == [
        *(reversed(amounts) if descending else amounts),
        "negotiable",
        "",
    ]


def test_status_sorts_in_pipeline_order():
    applications = [
        make_application(dates={status: "2026-09-20"})
        for status in [Stage.OFFER, Stage.APPLIED, Stage.ROUND_2]
    ]
    assert [
        a.status
        for a in sort_applications(applications, COLUMNS_BY_KEY["status"])
    ] == [Stage.APPLIED, Stage.ROUND_2, Stage.OFFER]


def test_long_unanswered_application_shows_as_ghosted():
    application = make_application(dates={Stage.APPLIED: "2026-08-01"})
    assert status_text(application, TODAY) == (
        "Ghosted (no reply for 54 days)"
    )
    assert status_sort_value(application, TODAY) == status_sort_value(
        make_application(dates={Stage.GHOSTED: "2026-09-01"}), TODAY
    )


def test_recent_application_shows_as_applied():
    application = make_application(dates={Stage.APPLIED: "2026-09-10"})
    assert status_text(application, TODAY) == "Applied"


def test_dates_sort_chronologically_with_blank_last():
    applications = [
        make_application(dates={Stage.APPLIED: "2026-09-10"}),
        make_application(),
        make_application(dates={Stage.APPLIED: "2026-08-01"}),
    ]
    assert sorted_values(applications, "date_applied", descending=True) == [
        "10.09.2026",
        "01.08.2026",
        "",
    ]


def test_text_sorts_ignoring_case():
    applications = [
        make_application(company=name)
        for name in ["beta", "Alpha", "", "Gamma"]
    ]
    assert sorted_values(applications, "company") == [
        "Alpha",
        "beta",
        "Gamma",
        "",
    ]


COMPANIES = ["Acme Robotics", "ACME GmbH", "Globex"]


def test_companies_containing_matches_anywhere_ignoring_case():
    assert companies_containing(COMPANIES, "gmbh") == ["ACME GmbH"]
    assert companies_containing(COMPANIES, "") == COMPANIES


def test_completion_uses_the_stored_spelling():
    assert completion_for(COMPANIES, "acme") == "Acme Robotics"
    assert completion_for(COMPANIES, "acme g") == "ACME GmbH"


def test_no_completion_when_nothing_longer_matches():
    assert completion_for(COMPANIES, "Globex") is None
    assert completion_for(COMPANIES, "Initech") is None


def test_month_grid_starts_on_monday_and_covers_the_month():
    weeks = month_grid(2026, 10)
    assert weeks[0][0] == date(2026, 9, 28)
    assert all(len(week) == 7 for week in weeks)
    days = [day for week in weeks for day in week]
    assert date(2026, 10, 1) in days and date(2026, 10, 31) in days


@pytest.mark.parametrize(
    "start, months, expected",
    [
        ((2026, 12), 1, (2027, 1)),
        ((2026, 1), -1, (2025, 12)),
        ((2026, 5), 0, (2026, 5)),
    ],
)
def test_shift_month_wraps_around_the_year(start, months, expected):
    assert shift_month(*start, months) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("15.03.2026", date(2026, 3, 15)),
        ("", date(2026, 10, 2)),
        ("15.03.", date(2026, 10, 2)),
    ],
)
def test_calendar_opens_on_entered_date_or_today(text, expected):
    assert initial_date(text, today=date(2026, 10, 2)) == expected
