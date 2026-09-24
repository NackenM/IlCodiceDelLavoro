"""Building example applications for the tests."""

from __future__ import annotations

from datetime import date

from job_tracker.model import Application, RoundTags
from job_tracker.stages import Stage

TODAY = date(2026, 9, 24)


def make_application(
    status: Stage | None = None,
    dates: dict[Stage, str] | None = None,
    tags: dict[Stage, RoundTags] | None = None,
    **fields,
) -> Application:
    """An application with ISO `dates` per stage; the status defaults to
    the latest stage reached."""
    stage_dates = {
        stage: date.fromisoformat(day) for stage, day in (dates or {}).items()
    }
    if status is None:
        reached = [stage for stage in Stage if stage in stage_dates]
        status = max(
            reached, key=lambda s: stage_dates[s], default=Stage.APPLIED
        )
    fields.setdefault("job_title", "Engineer")
    fields.setdefault("company", "Acme")
    return Application(
        status=status, stage_dates=stage_dates, round_tags=tags or {}, **fields
    )
