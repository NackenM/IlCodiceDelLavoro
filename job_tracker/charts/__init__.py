"""Matplotlib figures of the application data; each builder takes a sequence
of applications and returns a Figure ready to embed."""

from .activity_calendar import build_activity_calendar_figure
from .progress import build_progress_figure
from .reply_times import build_reply_times_figure
from .statistics import (
    build_company_outcomes_figure,
    build_company_share_figure,
    build_success_rate_figure,
)
from .timeline import TimelineFigures, build_timeline_figures
from .waterfall import build_outcome_waterfall_figure

__all__ = [
    "build_activity_calendar_figure",
    "TimelineFigures",
    "build_company_outcomes_figure",
    "build_company_share_figure",
    "build_outcome_waterfall_figure",
    "build_progress_figure",
    "build_reply_times_figure",
    "build_success_rate_figure",
    "build_timeline_figures",
]
