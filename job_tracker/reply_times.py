"""How long companies took to send a first reply to an application."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from statistics import mean, median

from .model import Application
from .stages import Stage


class ReplyKind(StrEnum):
    """What the first reply was, in display order."""

    ASSESSMENT = "Assessment"
    INTERVIEW = "Interview"
    REJECTION = "Rejection"


# The kind of reply each stage stands for; stages missing here (applying,
# being ghosted) are no reply. An offer without a round before it counts
# as an interview invitation.
REPLY_KINDS = {
    Stage.ONLINE_ASSESSMENT: ReplyKind.ASSESSMENT,
    Stage.CODING_CHALLENGE: ReplyKind.ASSESSMENT,
    Stage.ROUND_1: ReplyKind.INTERVIEW,
    Stage.ROUND_2: ReplyKind.INTERVIEW,
    Stage.ROUND_3: ReplyKind.INTERVIEW,
    Stage.OFFER: ReplyKind.INTERVIEW,
    Stage.REJECTED: ReplyKind.REJECTION,
}
_STAGE_ORDER = {stage: index for index, stage in enumerate(Stage)}


@dataclass(frozen=True)
class FirstReply:
    application: Application
    stage: Stage
    days: int

    @property
    def kind(self) -> ReplyKind:
        return REPLY_KINDS[self.stage]


def first_reply(application: Application) -> FirstReply | None:
    """The earliest reply after applying; on the same day an invitation
    comes before a rejection (it was the reply, the rejection followed).
    None without an applied date or any reply."""
    applied = application.date_applied
    if applied is None:
        return None
    replies = [
        (day, stage)
        for stage, day in application.stage_dates.items()
        if stage in REPLY_KINDS and day >= applied
    ]
    if not replies:
        return None
    day, stage = min(replies, key=lambda r: (r[0], _STAGE_ORDER[r[1]]))
    return FirstReply(application, stage, (day - applied).days)


def first_replies(applications: Iterable[Application]) -> list[FirstReply]:
    return [
        reply
        for application in applications
        if (reply := first_reply(application)) is not None
    ]


@dataclass(frozen=True)
class Waiting:
    """An application with no reply yet, `days` after it was sent."""

    application: Application
    days: int


def waiting_for_reply(
    applications: Iterable[Application], today: date | None = None
) -> list[Waiting]:
    """The applications still waiting for a first reply. Those marked as
    ghosted are closed and left out; ones only silently overdue stay in,
    to show how far past the usual reply times they are."""
    today = today or date.today()
    return [
        Waiting(application, (today - application.date_applied).days)
        for application in applications
        if application.date_applied is not None
        and application.date_applied <= today
        and not application.has_reached(Stage.GHOSTED)
        and first_reply(application) is None
    ]


@dataclass(frozen=True)
class ReplyTimeSummary:
    count: int
    mean_days: float
    median_days: float

    @classmethod
    def of(
        cls, replies: Sequence[FirstReply | Waiting]
    ) -> ReplyTimeSummary | None:
        if not replies:
            return None
        days = [reply.days for reply in replies]
        return cls(len(days), mean(days), median(days))
