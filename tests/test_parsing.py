"""Salary amounts, email lists and display dates."""

from datetime import date

import pytest

from job_tracker.dates import (
    format_display_date,
    is_valid_display_date,
    parse_display_date,
)
from job_tracker.emails import InvalidEmailError, normalize_email_list
from job_tracker.salary import parse_salary_amount


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("65-75k €", 65_000),
        ("€70.000 / year", 70_000),
        ("70,000 USD", 70_000),
        ("65 000 EUR", 65_000),
        ("72.5k", 72_500),
        ("80k-90k", 80_000),
        ("58k", 58_000),
        ("4.500 €/Monat", 4_500),  # the period is not interpreted
        ("negotiable", None),
        ("", None),
    ],
)
def test_parse_salary_amount(text, amount):
    assert parse_salary_amount(text) == amount


def test_normalize_email_list_accepts_any_separator():
    assert (
        normalize_email_list(" a@x.example; b@y.example ,c@z.example ")
        == "a@x.example, b@y.example, c@z.example"
    )


def test_normalize_email_list_allows_blank():
    assert normalize_email_list("  ") == ""


def test_normalize_email_list_names_the_invalid_address():
    with pytest.raises(InvalidEmailError) as error:
        normalize_email_list("a@x.example, not-an-email")
    assert error.value.address == "not-an-email"


def test_display_date_round_trip():
    assert format_display_date(date(2026, 9, 4)) == "04.09.2026"
    assert parse_display_date("04.09.2026") == date(2026, 9, 4)


def test_blank_display_date_means_not_set():
    assert format_display_date(None) == ""
    assert parse_display_date("  ") is None
    assert is_valid_display_date("")


@pytest.mark.parametrize("text", ["31.02.2026", "2026-09-04", "4/9/2026"])
def test_invalid_display_dates(text):
    assert not is_valid_display_date(text)
    with pytest.raises(ValueError):
        parse_display_date(text)
