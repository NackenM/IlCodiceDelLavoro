"""Rules that follow from an application's dates and tags."""

from datetime import date

import pytest

from job_tracker.model import NO_COMPANY, Application, RoundTags, StageEvent
from job_tracker.stages import PIPELINE, RoundFocus, RoundFormat, Stage

from .factories import make_application


class TestRoundTags:
    def test_unset_format_counts_as_virtual(self):
        tags = RoundTags()
        assert tags.effective_format is RoundFormat.VIRTUAL
        assert tags.letters() == "V"
        assert tags.descriptions() == ["Virtual"]

    def test_format_and_focus(self):
        tags = RoundTags(RoundFormat.ON_SITE, RoundFocus.HIRING_MANAGER)
        assert tags.letters() == "O M"
        assert tags.descriptions() == ["On-site", "Hiring manager"]


class TestStatusLabel:
    def test_round_shows_its_tag_letters(self):
        application = make_application(
            dates={Stage.ROUND_1: "2026-09-01"},
            tags={Stage.ROUND_1: RoundTags(RoundFormat.PHONE, RoundFocus.HR)},
        )
        assert application.status_label() == "Interview - 1st Round · P H"

    def test_untagged_round_shows_virtual(self):
        application = make_application(dates={Stage.ROUND_2: "2026-09-01"})
        assert application.status_label() == "Interview - 2nd Round · V"

    def test_coding_challenge_shows_where_it_happened(self):
        application = make_application(
            dates={
                Stage.ROUND_1: "2026-09-01",
                Stage.CODING_CHALLENGE: "2026-09-03",
            }
        )
        assert (
            application.status_label() == "Coding Challenge (after 1st Round)"
        )

    def test_other_stages_are_shown_as_is(self):
        assert make_application(status=Stage.OFFER).status_label() == "Offer"


@pytest.mark.parametrize(
    ("round_dates", "challenge", "position"),
    [
        ({}, "2026-09-05", "before 1st Round"),
        ({Stage.ROUND_1: "2026-09-01"}, "2026-09-05", "after 1st Round"),
        # same day counts as after the round
        ({Stage.ROUND_1: "2026-09-05"}, "2026-09-05", "after 1st Round"),
        (
            {Stage.ROUND_1: "2026-09-01", Stage.ROUND_2: "2026-09-04"},
            "2026-09-05",
            "after 2nd Round",
        ),
        (
            {Stage.ROUND_1: "2026-09-01", Stage.ROUND_2: "2026-09-10"},
            "2026-09-05",
            "after 1st Round",
        ),
    ],
)
def test_coding_challenge_position(round_dates, challenge, position):
    application = make_application(
        dates={**round_dates, Stage.CODING_CHALLENGE: challenge}
    )
    assert application.coding_challenge_position() == position


def test_no_coding_challenge_has_no_position():
    assert make_application().coding_challenge_position() == ""


class TestFurthestPipelineIndex:
    def test_nothing_reached(self):
        application = Application(status=Stage.REJECTED)
        assert application.furthest_pipeline_index() == -1

    def test_uses_dates(self):
        application = make_application(
            status=Stage.REJECTED,
            dates={Stage.APPLIED: "2026-09-01", Stage.ROUND_2: "2026-09-10"},
        )
        assert application.furthest_pipeline_index() == PIPELINE.index(
            Stage.ROUND_2
        )

    def test_uses_status_without_a_date(self):
        application = make_application(
            status=Stage.ROUND_3, dates={Stage.APPLIED: "2026-09-01"}
        )
        assert application.furthest_pipeline_index() == PIPELINE.index(
            Stage.ROUND_3
        )

    def test_side_stages_do_not_count(self):
        application = make_application(
            dates={
                Stage.APPLIED: "2026-09-01",
                Stage.CODING_CHALLENGE: "2026-09-10",
            }
        )
        assert application.furthest_pipeline_index() == 0


def test_stage_events_group_same_day_stages_in_order():
    application = make_application(
        dates={
            Stage.APPLIED: "2026-09-01",
            Stage.CODING_CHALLENGE: "2026-09-08",
            Stage.ROUND_1: "2026-09-08",
            Stage.REJECTED: "2026-09-12",
        }
    )
    assert application.stage_events() == [
        StageEvent(date(2026, 9, 1), (Stage.APPLIED,)),
        StageEvent(date(2026, 9, 8), (Stage.ROUND_1, Stage.CODING_CHALLENGE)),
        StageEvent(date(2026, 9, 12), (Stage.REJECTED,)),
    ]


def test_stage_description_of_a_round():
    application = make_application(
        tags={Stage.ROUND_3: RoundTags(focus=RoundFocus.TECHNICAL)}
    )
    assert (
        application.stage_description(Stage.ROUND_3)
        == "Interview - 3rd Round (Virtual · Technical)"
    )


class TestDisplayNames:
    def test_company_and_title(self):
        application = make_application(company=" Acme ", job_title="Dev")
        assert application.display_name == "Acme · Dev"

    def test_falls_back_to_id(self):
        application = Application(id="abc123")
        assert application.display_name == "abc123"

    def test_company_whitespace_is_collapsed(self):
        assert (
            make_application(company="  Acme   Robotics ").company_display_name
            == "Acme Robotics"
        )
        assert make_application(company="").company_display_name == NO_COMPANY


def test_salary_amount_comes_from_the_text():
    assert make_application(salary="65-75k €").salary_amount == 65_000


def test_new_applications_get_distinct_ids():
    assert Application().id != Application().id
