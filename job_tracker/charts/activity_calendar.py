"""Activity calendar: one month as a grid of days, each shaded by how much
happened on it, like a contribution graph."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from matplotlib.colors import to_hex, to_rgb
from matplotlib.figure import Figure
from matplotlib.offsetbox import (
    AnchoredOffsetbox,
    DrawingArea,
    HPacker,
    TextArea,
)
from matplotlib.patches import FancyBboxPatch, Rectangle

from ..activity import (
    HEAT_LEVELS,
    ActivityKind,
    DayEvent,
    activity_by_day,
    heat_level,
)
from ..dates import WEEKDAY_HEADINGS, month_grid, month_title
from ..model import Application
from .style import (
    INK_PRIMARY,
    INK_SECONDARY,
    SURFACE,
    TEXT_BODY,
    TEXT_SMALL,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    bullet_list,
    draw_subtitle,
    new_figure,
    plural,
)

HEAT_HUE = "#2a78d6"
EMPTY_DAY_COLOR = "#ebeae4"
# Cells are 1 x 1 in data units, with this much space around each.
CELL_GAP = 0.06
CELL_ROUNDING = 0.12
# From this heat level on, a cell is dark enough for white text.
WHITE_TEXT_FROM_LEVEL = 3
LEGEND_SWATCH_POINTS = 10
HEADING_ROW_HEIGHT = 0.45


def _mix(color: str, share: float) -> str:
    """`color` mixed into the background by `share` (0..1)."""
    base, tint = to_rgb(SURFACE), to_rgb(color)
    mixed = (b + (t - b) * share for b, t in zip(base, tint, strict=True))
    return to_hex(tuple(mixed))


# The color of each heat level, 0 (an empty day) to HEAT_LEVELS.
HEAT_COLORS = [EMPTY_DAY_COLOR] + [
    _mix(HEAT_HUE, 0.3 + 0.7 * level / HEAT_LEVELS)
    for level in range(1, HEAT_LEVELS + 1)
]


def _day_tooltip(day: date, events: list[DayEvent], kind: ActivityKind) -> str:
    heading = f"{WEEKDAY_HEADINGS[day.weekday()]} {day:%d.%m.%Y}"
    if not events:
        return f"{heading}\nnothing"
    if kind is ActivityKind.APPLIED:
        count = plural(len(events), "application") + " sent"
        entries = [event.application.display_name for event in events]
    else:
        count = plural(len(events), "stage date")
        entries = [
            f"{event.application.display_name}: {event.stage}"
            for event in events
        ]
    return f"{heading}  ·  {count}\n{bullet_list(entries)}"


def _summary(days: dict[date, list[DayEvent]], kind: ActivityKind) -> str:
    total = sum(len(events) for events in days.values())
    what = (
        plural(total, "application") + " sent"
        if kind is ActivityKind.APPLIED
        else plural(total, "stage date")
    )
    if not total:
        return f"{what} this month"
    busiest = max(days, key=lambda day: (len(days[day]), -day.toordinal()))
    return (
        f"{what}  ·  {plural(len(days), 'active day')}  ·  busiest "
        f"{busiest:%d.%m.} ({len(days[busiest])})"
    )


def _draw_legend(axes) -> None:
    """ "Less ▢▢▢▢▢ More" under the grid, at its right edge."""
    step = LEGEND_SWATCH_POINTS + 3
    swatches = DrawingArea(step * len(HEAT_COLORS), LEGEND_SWATCH_POINTS)
    for index, color in enumerate(HEAT_COLORS):
        swatches.add_artist(
            Rectangle(
                (index * step, 0),
                LEGEND_SWATCH_POINTS,
                LEGEND_SWATCH_POINTS,
                facecolor=color,
                edgecolor="none",
            )
        )
    text_style = {"fontsize": TEXT_SMALL, "color": INK_SECONDARY}
    legend = HPacker(
        children=[
            TextArea("Less", textprops=text_style),
            swatches,
            TextArea("More", textprops=text_style),
        ],
        sep=5,
        align="center",
    )
    axes.add_artist(
        AnchoredOffsetbox(
            loc="upper right",
            child=legend,
            bbox_to_anchor=(1, 0),
            bbox_transform=axes.transAxes,
            frameon=False,
            pad=0,
            borderpad=0.4,
        )
    )


def build_activity_calendar_figure(
    applications: Sequence[Application],
    year: int,
    month: int,
    kind: ActivityKind = ActivityKind.APPLIED,
    today: date | None = None,
) -> Figure:
    """The month `year`-`month`, Monday first, one cell per day shaded by
    its activity; shades compare across months, as they are relative to
    the busiest day overall."""
    today = today or date.today()
    figure, axes = new_figure(6.4, 4.6)
    all_days = activity_by_day(applications, kind)
    busiest = max((len(events) for events in all_days.values()), default=0)
    weeks = month_grid(year, month)
    this_month = {
        day: events
        for day, events in all_days.items()
        if (day.year, day.month) == (year, month)
    }

    hover_targets = []
    for row, week in enumerate(weeks):
        for column, day in enumerate(week):
            if day.month != month:
                continue  # the neighbouring months' days stay blank
            events = this_month.get(day, [])
            level = heat_level(len(events), busiest)
            cell = FancyBboxPatch(
                (column + CELL_GAP, row + CELL_GAP),
                1 - 2 * CELL_GAP,
                1 - 2 * CELL_GAP,
                boxstyle=f"round,pad=0,rounding_size={CELL_ROUNDING}",
                facecolor=HEAT_COLORS[level],
                edgecolor=INK_PRIMARY if day == today else "none",
                linewidth=1.5,
                zorder=2,
            )
            axes.add_patch(cell)
            text_color = (
                "white" if level >= WHITE_TEXT_FROM_LEVEL else INK_SECONDARY
            )
            axes.text(
                column + 0.14,
                row + 0.14,
                str(day.day),
                ha="left",
                va="top",
                fontsize=TEXT_SMALL,
                color=text_color,
                zorder=3,
            )
            if events:
                axes.text(
                    column + 0.5,
                    row + 0.56,
                    str(len(events)),
                    ha="center",
                    va="center",
                    fontsize=TEXT_BODY,
                    fontweight="bold",
                    color="white" if text_color == "white" else INK_PRIMARY,
                    zorder=3,
                )
            hover_targets.append(
                HoverTarget(cell, _day_tooltip(day, events, kind))
            )

    for column, heading in enumerate(WEEKDAY_HEADINGS):
        axes.text(
            column + 0.5,
            -HEADING_ROW_HEIGHT / 2,
            heading,
            ha="center",
            va="center",
            fontsize=TEXT_SMALL,
            color=INK_SECONDARY,
        )
    axes.set_xlim(0, 7)
    # First week on top, under a row of weekday headings.
    axes.set_ylim(len(weeks), -HEADING_ROW_HEIGHT)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_title(month_title(year, month), pad=22, **TITLE_STYLE)
    draw_subtitle(axes, _summary(this_month, kind))
    _draw_legend(axes)
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure
