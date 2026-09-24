"""The stages an application moves through, and the tags of interview
rounds."""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    """Every stage an application can reach, in dropdown / sort order.

    The coding challenge is listed after the 1st round, where it usually
    happens, but it is optional and can follow any round.
    """

    APPLIED = "Applied"
    ONLINE_ASSESSMENT = "Online Assessment"
    ROUND_1 = "Interview - 1st Round"
    CODING_CHALLENGE = "Coding Challenge"
    ROUND_2 = "Interview - 2nd Round"
    ROUND_3 = "Interview - 3rd Round"
    REJECTED = "Rejected"
    OFFER = "Offer"

    @property
    def short_name(self) -> str:
        """The name without the "Interview - " prefix, e.g. "1st Round"."""
        return self.value.removeprefix("Interview - ")


# The forward pipeline. The coding challenge (optional, between rounds) and
# rejection (an exit reachable from any stage) are side stages outside it,
# so skipping them never looks like a stalled pipeline.
PIPELINE = (
    Stage.APPLIED,
    Stage.ONLINE_ASSESSMENT,
    Stage.ROUND_1,
    Stage.ROUND_2,
    Stage.ROUND_3,
    Stage.OFFER,
)
INTERVIEW_ROUNDS = (Stage.ROUND_1, Stage.ROUND_2, Stage.ROUND_3)


class RoundFormat(StrEnum):
    ON_SITE = "On-site"
    VIRTUAL = "Virtual"
    PHONE = "Phone"

    @property
    def letter(self) -> str:
        return {"On-site": "O", "Virtual": "V", "Phone": "P"}[self.value]


class RoundFocus(StrEnum):
    TECHNICAL = "Technical"
    HR = "HR"
    HIRING_MANAGER = "Hiring manager"

    @property
    def letter(self) -> str:
        return {"Technical": "T", "HR": "H", "Hiring manager": "M"}[self.value]


# A round without a format set counts as virtual.
DEFAULT_ROUND_FORMAT = RoundFormat.VIRTUAL
