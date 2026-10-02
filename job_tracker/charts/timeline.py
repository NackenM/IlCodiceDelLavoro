"""Timeline: one row per application, a marker per stage reached, the days
between consecutive stages, and a dashed tail up to today while open; a
red line marks today."""

from __future__ import annotations

import textwrap
from collections.abc import Sequence
from datetime import date, timedelta
from itertools import pairwise

from matplotlib.axes import Axes
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure

from ..model import Application, StageEvent
from ..outcomes import OPEN_OUTCOMES, Outcome, classify
from ..stages import Stage
from .style import (
    BASELINE,
    GRIDLINE,
    INK_MUTED,
    INK_SECONDARY,
    OUTCOME_COLORS,
    SURFACE,
    TEXT_BODY,
    TEXT_SMALL,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    new_figure,
    plural,
    show_empty_message,
)

MARKER_LABELS = {
    Stage.APPLIED: "Applied",
    Stage.ONLINE_ASSESSMENT: "OA",
    Stage.ROUND_1: "1st",
    Stage.ROUND_2: "2nd",
    Stage.ROUND_3: "3rd",
    Stage.CODING_CHALLENGE: "CC",
    Stage.REJECTED: "Rejected",
    Stage.GHOSTED: "Ghosted",
    Stage.OFFER: "Offer",
}
INTERVIEW_COLOR = "#2a78d6"
MARKER_COLORS = {
    Stage.APPLIED: INK_SECONDARY,
    Stage.ONLINE_ASSESSMENT: "#eda100",
    Stage.ROUND_1: INTERVIEW_COLOR,
    Stage.ROUND_2: INTERVIEW_COLOR,
    Stage.ROUND_3: INTERVIEW_COLOR,
    Stage.CODING_CHALLENGE: "#4a3aa7",
    Stage.REJECTED: OUTCOME_COLORS[Outcome.REJECTED_AFTER_STAGE],
    Stage.GHOSTED: OUTCOME_COLORS[Outcome.GHOSTED],
    Stage.OFFER: OUTCOME_COLORS[Outcome.OFFER],
}
# Day counts on segments narrower than this share of the time axis are left
# to the tooltip instead of colliding with the markers.
MIN_DAY_LABEL_SHARE = 0.035
# Rough width of one label character as a share of the time axis, used to
# stagger marker labels that would overlap.
CHARACTER_WIDTH_SHARE = 0.013
# Marker labels go on the first of these lines below the marker where they
# fit next to the labels already there.
LABEL_LINES = 3
LABEL_LINE_HEIGHT = 0.17
# Room left of the earliest marker, as a share of the time axis, so its
# centered label stays clear of the row labels; and the gap in points
# between those row labels and the plot.
LEFT_MARGIN_SHARE = 0.07
ROW_LABEL_PAD = 14
DASHED = (0, (3, 2))
TODAY_COLOR = OUTCOME_COLORS[Outcome.REJECTED_AFTER_STAGE]
# Row labels wrap at this many characters: the company on its own line,
# the job title on up to two more.
ROW_LABEL_WIDTH = 28


def row_label(application: Application) -> str:
    """Company and job title on separate lines, long ones wrapped."""
    if not (application.company.strip() or application.job_title.strip()):
        return application.id
    lines = textwrap.wrap(
        application.company, ROW_LABEL_WIDTH, max_lines=1, placeholder="…"
    )
    lines += textwrap.wrap(
        application.job_title, ROW_LABEL_WIDTH, max_lines=2, placeholder="…"
    )
    return "\n".join(lines)


def marker_label(event: StageEvent) -> str:
    return "+".join(MARKER_LABELS[stage] for stage in event.stages)


def _draw_gaps(
    axes: Axes, y: int, events: list[StageEvent], span_days: int
) -> list[HoverTarget]:
    """Day counts between consecutive events, and their tooltips."""
    hover_targets = []
    for earlier, later in pairwise(events):
        gap_days = (later.day - earlier.day).days
        if gap_days and gap_days / span_days >= MIN_DAY_LABEL_SHARE:
            axes.text(
                earlier.day + (later.day - earlier.day) / 2,
                y - 0.14,
                f"{gap_days}d",
                ha="center",
                va="bottom",
                fontsize=TEXT_SMALL,
                color=INK_SECONDARY,
                zorder=5,
            )
        # An invisible, wide line makes the whole gap hoverable.
        (hit_area,) = axes.plot(
            [earlier.day, later.day], [y, y], color="none", linewidth=8
        )
        hover_targets.append(
            HoverTarget(
                hit_area,
                f"{MARKER_LABELS[earlier.stages[-1]]} → "
                f"{MARKER_LABELS[later.stages[0]]}: {gap_days} days\n"
                f"{earlier.day:%d.%m.%Y} → {later.day:%d.%m.%Y}",
            )
        )
    return hover_targets


def _draw_markers(
    axes: Axes,
    y: int,
    application: Application,
    events: list[StageEvent],
    span_days: int,
) -> list[HoverTarget]:
    """A dot per event with its stage label; labels that would run into the
    labels before them are stepped down a line."""
    hover_targets = []
    # Per line, where its last label ends, as a share of the time axis.
    line_ends = [float("-inf")] * LABEL_LINES
    for event in events:
        color = MARKER_COLORS[event.stages[-1]]
        (marker,) = axes.plot(
            [event.day],
            [y],
            marker="o",
            markersize=8,
            color=color,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            zorder=4,
        )
        label = marker_label(event)
        center = (event.day - events[0].day).days / span_days
        half_width = (len(label) / 2 + 1) * CHARACTER_WIDTH_SHARE
        left, right = center - half_width, center + half_width
        line = next(
            (i for i, end in enumerate(line_ends) if end <= left),
            # No line has room: overlap where the most is left.
            line_ends.index(min(line_ends)),
        )
        line_ends[line] = right
        axes.text(
            event.day,
            y + 0.2 + line * LABEL_LINE_HEIGHT,
            label,
            ha="center",
            va="top",
            fontsize=TEXT_SMALL,
            color=color,
            zorder=5,
        )
        details = "\n".join(
            application.stage_description(stage) for stage in event.stages
        )
        hover_targets.append(
            HoverTarget(marker, f"{event.day:%d.%m.%Y}\n{details}")
        )
    return hover_targets


def _draw_summary(
    axes: Axes,
    y: int,
    application: Application,
    events: list[StageEvent],
    today: date,
) -> None:
    """Total duration; open applications get a dashed tail up to today."""
    first_day, last_day = events[0].day, events[-1].day
    outcome = classify(application, today)
    if outcome in OPEN_OUTCOMES and today > last_day:
        axes.plot(
            [last_day, today],
            [y, y],
            color=BASELINE,
            linewidth=1.6,
            linestyle=DASHED,
            zorder=2,
        )
        summary = f"{(today - first_day).days}d so far\n{outcome.lower()}"
        summary_day = today
    else:
        summary = f"{(last_day - first_day).days}d in total"
        summary_day = last_day
    axes.annotate(
        summary,
        (summary_day, y),
        xytext=(9, 0),
        textcoords="offset points",
        va="center",
        fontsize=TEXT_SMALL,
        color=INK_SECONDARY,
    )


def _draw_today(axes: Axes, today: date) -> None:
    axes.axvline(today, color=TODAY_COLOR, linewidth=1.2, zorder=1)
    axes.annotate(
        "Today",
        (today, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(0, 3),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=TEXT_SMALL,
        color=TODAY_COLOR,
    )


def build_timeline_figure(
    applications: Sequence[Application], today: date | None = None
) -> Figure:
    today = today or date.today()
    figure, axes = new_figure(9, 1.4 + 0.62 * max(len(applications), 1))
    events_per_application = [a.stage_events() for a in applications]
    all_days = [e.day for events in events_per_application for e in events]
    if not all_days:
        show_empty_message(
            axes, "The selected applications have no stage dates yet"
        )
        return figure

    start = min(all_days)
    end = max([*all_days, today])
    span_days = max((end - start).days, 1)

    marker_targets, gap_targets = [], []
    for y, (application, events) in enumerate(
        zip(applications, events_per_application, strict=True)
    ):
        if not events:
            axes.text(
                start,
                y,
                "  no stage dates",
                va="center",
                fontsize=TEXT_SMALL,
                color=INK_MUTED,
            )
            continue
        axes.plot(
            [e.day for e in events],
            [y] * len(events),
            color=BASELINE,
            linewidth=2.2,
            zorder=2,
        )
        gap_targets += _draw_gaps(axes, y, events, span_days)
        _draw_summary(axes, y, application, events, today)
        marker_targets += _draw_markers(
            axes, y, application, events, span_days
        )

    _draw_today(axes, today)
    axes.set_yticks(range(len(applications)))
    axes.set_yticklabels(
        [row_label(a) for a in applications],
        fontsize=TEXT_BODY,
        color=INK_SECONDARY,
    )
    axes.set_ylim(len(applications) - 0.35, -0.6)  # first one on top
    # Room on the right for the "Nd so far" summaries.
    axes.set_xlim(
        start - timedelta(days=span_days * LEFT_MARGIN_SHARE),
        end + timedelta(days=span_days * 0.16),
    )
    axes.xaxis.set_major_formatter(DateFormatter("%d.%m."))
    axes.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    for name, spine in axes.spines.items():
        spine.set_visible(name == "bottom")
        spine.set_color(BASELINE)
    axes.tick_params(colors=INK_SECONDARY, length=0, labelsize=TEXT_BODY)
    axes.tick_params(axis="y", pad=ROW_LABEL_PAD)
    axes.set_title(
        f"Timeline  ·  {plural(len(applications), 'application')}",
        pad=12,
        **TITLE_STYLE,
    )
    # Markers win over the gap they sit on.
    attach_hover(figure, axes, marker_targets + gap_targets)

    figure.tight_layout()
    return figure
