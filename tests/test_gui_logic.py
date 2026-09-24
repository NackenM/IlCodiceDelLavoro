"""The GUI's pure helpers: list sorting and company completion."""

import pytest

from job_tracker.gui.application_list import COLUMNS_BY_KEY, sort_applications
from job_tracker.gui.company_field import companies_containing, completion_for
from job_tracker.stages import Stage

from .factories import make_application


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
        make_application(status=status)
        for status in [Stage.OFFER, Stage.APPLIED, Stage.ROUND_2]
    ]
    assert [
        a.status
        for a in sort_applications(applications, COLUMNS_BY_KEY["status"])
    ] == [Stage.APPLIED, Stage.ROUND_2, Stage.OFFER]


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
