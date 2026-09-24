"""Outcome classification, time filtering and company grouping."""

import pytest

from job_tracker.companies import (
    company_key,
    group_by_company,
    known_companies,
)
from job_tracker.model import NO_COMPANY
from job_tracker.outcomes import (
    GHOSTED_AFTER_DAYS,
    Outcome,
    applied_within,
    classify,
    count_outcomes,
    group_by_outcome,
    rejection_stage,
)
from job_tracker.stages import Stage

from .factories import TODAY, make_application


@pytest.mark.parametrize(
    ("dates", "status", "outcome"),
    [
        (
            {Stage.APPLIED: "2026-07-01", Stage.OFFER: "2026-08-01"},
            None,
            Outcome.OFFER,
        ),
        (
            {Stage.APPLIED: "2026-07-01", Stage.REJECTED: "2026-07-03"},
            None,
            Outcome.REJECTED_RIGHT_AWAY,
        ),
        (
            {
                Stage.APPLIED: "2026-07-01",
                Stage.ONLINE_ASSESSMENT: "2026-07-03",
                Stage.REJECTED: "2026-07-05",
            },
            None,
            Outcome.REJECTED_AFTER_STAGE,
        ),
        (
            {Stage.APPLIED: "2026-08-01", Stage.ROUND_1: "2026-08-10"},
            None,
            Outcome.IN_PROGRESS,
        ),
        ({Stage.APPLIED: "2026-08-01"}, None, Outcome.GHOSTED),
        ({Stage.APPLIED: "2026-09-10"}, None, Outcome.AWAITING_REPLY),
        # Rejected status without a rejection date still counts.
        (
            {Stage.APPLIED: "2026-09-10"},
            Stage.REJECTED,
            Outcome.REJECTED_RIGHT_AWAY,
        ),
        # No applied date: can't tell whether it's ghosted.
        ({}, Stage.APPLIED, Outcome.AWAITING_REPLY),
    ],
)
def test_classify(dates, status, outcome):
    application = make_application(status=status, dates=dates)
    assert classify(application, TODAY) is outcome


def test_ghosted_threshold():
    def applied_days_ago(days):
        day = TODAY.toordinal() - days
        return make_application(
            dates={Stage.APPLIED: TODAY.fromordinal(day).isoformat()}
        )

    at_threshold = applied_days_ago(GHOSTED_AFTER_DAYS)
    just_before = applied_days_ago(GHOSTED_AFTER_DAYS - 1)
    assert classify(at_threshold, TODAY) is Outcome.GHOSTED
    assert classify(just_before, TODAY) is Outcome.AWAITING_REPLY


def test_rejection_stage_is_the_last_pipeline_stage_reached():
    application = make_application(
        dates={
            Stage.APPLIED: "2026-07-01",
            Stage.ROUND_1: "2026-07-05",
            Stage.CODING_CHALLENGE: "2026-07-07",
            Stage.ROUND_2: "2026-07-10",
            Stage.REJECTED: "2026-07-15",
        }
    )
    assert rejection_stage(application) is Stage.ROUND_2


def test_counting_and_grouping_cover_every_outcome():
    applications = [
        make_application(dates={Stage.APPLIED: "2026-09-20"}),
        make_application(dates={Stage.APPLIED: "2026-09-21"}),
        make_application(dates={Stage.APPLIED: "2026-01-01"}),
    ]
    counts = count_outcomes(applications, TODAY)
    assert counts == {Outcome.AWAITING_REPLY: 2, Outcome.GHOSTED: 1}

    groups = group_by_outcome(applications, TODAY)
    assert list(groups) == list(Outcome)
    assert groups[Outcome.OFFER] == []
    assert len(groups[Outcome.AWAITING_REPLY]) == 2


def test_applied_within():
    recent = make_application(dates={Stage.APPLIED: "2026-09-01"})
    old = make_application(dates={Stage.APPLIED: "2026-05-01"})
    undated = make_application()
    applications = [recent, old, undated]
    assert applied_within(applications, 30, TODAY) == [recent]
    assert applied_within(applications, 365, TODAY) == [recent, old]
    assert applied_within(applications, None, TODAY) == applications


class TestCompanies:
    def test_company_key_ignores_case_and_spacing(self):
        assert company_key(" ACME   GmbH ") == company_key("acme gmbh")

    def test_group_by_company(self):
        applications = [
            make_application(company="Globex"),
            make_application(company="ACME GmbH"),
            make_application(company=" acme  gmbh"),
            make_application(company=""),
            make_application(company="Initech"),
        ]
        groups = group_by_company(applications)
        assert [(g.name, g.size) for g in groups] == [
            ("ACME GmbH", 2),  # most applications first, first spelling
            ("Globex", 1),  # then alphabetical
            ("Initech", 1),
            (NO_COMPANY, 1),  # always last
        ]
        assert not groups[-1].has_company

    def test_group_splits_by_outcome(self):
        offer = make_application(
            dates={Stage.APPLIED: "2026-07-01", Stage.OFFER: "2026-08-01"}
        )
        waiting = make_application(dates={Stage.APPLIED: "2026-09-20"})
        (group,) = group_by_company([offer, waiting])
        by_outcome = group.by_outcome(TODAY)
        assert by_outcome[Outcome.OFFER] == [offer]
        assert by_outcome[Outcome.AWAITING_REPLY] == [waiting]

    def test_known_companies(self):
        applications = [
            make_application(company="globex"),
            make_application(company="Acme"),
            make_application(company="ACME"),
            make_application(company=""),
        ]
        assert known_companies(applications) == ["Acme", "globex"]
