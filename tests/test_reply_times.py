"""The first reply to an application, and how long it took."""

import pytest

from job_tracker.reply_times import (
    ReplyKind,
    ReplyTimeSummary,
    first_replies,
    first_reply,
)
from job_tracker.stages import Stage

from .factories import make_application


@pytest.mark.parametrize(
    ("reply_stage", "kind"),
    [
        (Stage.ONLINE_ASSESSMENT, ReplyKind.ASSESSMENT),
        (Stage.CODING_CHALLENGE, ReplyKind.ASSESSMENT),
        (Stage.ROUND_1, ReplyKind.INTERVIEW),
        (Stage.OFFER, ReplyKind.INTERVIEW),
        (Stage.REJECTED, ReplyKind.REJECTION),
    ],
)
def test_kind_of_the_first_reply(reply_stage, kind):
    application = make_application(
        dates={Stage.APPLIED: "2026-09-01", reply_stage: "2026-09-08"}
    )
    reply = first_reply(application)
    assert (reply.stage, reply.kind, reply.days) == (reply_stage, kind, 7)


def test_only_the_earliest_reply_counts():
    application = make_application(
        dates={
            Stage.APPLIED: "2026-09-01",
            Stage.ROUND_1: "2026-09-10",
            Stage.ONLINE_ASSESSMENT: "2026-09-04",
            Stage.REJECTED: "2026-09-20",
        }
    )
    assert first_reply(application).stage is Stage.ONLINE_ASSESSMENT


def test_an_invitation_wins_over_a_rejection_on_the_same_day():
    application = make_application(
        dates={
            Stage.APPLIED: "2026-09-01",
            Stage.REJECTED: "2026-09-05",
            Stage.ROUND_1: "2026-09-05",
        }
    )
    assert first_reply(application).kind is ReplyKind.INTERVIEW


@pytest.mark.parametrize(
    "dates",
    [
        {Stage.APPLIED: "2026-09-01"},
        {Stage.APPLIED: "2026-09-01", Stage.GHOSTED: "2026-10-01"},
        {Stage.ROUND_1: "2026-09-08"},  # no applied date to count from
        # A reply dated before applying is a typo, not a reply.
        {Stage.APPLIED: "2026-09-10", Stage.REJECTED: "2026-09-01"},
    ],
)
def test_no_reply(dates):
    assert first_reply(make_application(dates=dates)) is None


def test_summary_of_reply_times():
    replies = first_replies(
        [
            make_application(
                dates={Stage.APPLIED: "2026-09-01", Stage.REJECTED: day}
            )
            for day in ("2026-09-03", "2026-09-05", "2026-09-13")
        ]
        + [make_application(dates={Stage.APPLIED: "2026-09-01"})]
    )
    assert ReplyTimeSummary.of(replies) == ReplyTimeSummary(3, 6, 4)
    assert ReplyTimeSummary.of([]) is None
