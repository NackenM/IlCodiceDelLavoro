"""Reply times: how many days each application waited for its first reply,
one row per kind of reply, with the average marked; and the applications
still waiting, against those averages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date

from matplotlib.figure import Figure

from ..model import Application
from ..outcomes import GHOSTED_AFTER_DAYS
from ..reply_times import (
    FirstReply,
    ReplyKind,
    ReplyTimeSummary,
    Waiting,
    first_replies,
    waiting_for_reply,
)
from .style import (
    BASELINE,
    INK_PRIMARY,
    INK_SECONDARY,
    SURFACE,
    TEXT_BODY,
    TEXT_SMALL,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    new_figure,
    plural,
    show_empty_message,
    style_bar_axes,
)

ALL_REPLIES = "All replies"
PENDING = "Pending"
# The same colors as the matching markers in the timeline.
REPLY_COLORS = {
    ALL_REPLIES: INK_SECONDARY,
    ReplyKind.ASSESSMENT: "#eda100",
    ReplyKind.INTERVIEW: "#2a78d6",
    ReplyKind.REJECTION: "#d03b3b",
}
# Replies on the same day in one row are stacked this far apart.
STACK_STEP = 0.09
STACK_MAX_OFFSET = 0.32
MEAN_HALF_HEIGHT = 0.36
# The time axis ends a little past the longest reply or the ghosted limit,
# whichever is later; applications waiting longer sit at its end.
AXIS_END_MARGIN = 1.15


def _stack_offsets(replies: Sequence[FirstReply | Waiting]) -> list[float]:
    """Vertical offsets that spread replies on the same day around the
    row: 0, +1, -1, +2, -2, ... steps, capped to stay in the row."""
    seen: Counter[int] = Counter()
    offsets = []
    for reply in replies:
        index = seen[reply.days]
        seen[reply.days] += 1
        step = (index + 1) // 2 * (1 if index % 2 else -1)
        offsets.append(
            max(-STACK_MAX_OFFSET, min(STACK_MAX_OFFSET, step * STACK_STEP))
        )
    return offsets


def row_label(label: str, summary: ReplyTimeSummary | None) -> str:
    """The row's name over its count and median, e.g. "Interview" over
    "12 replies · median 7 d"."""
    if summary is None:
        return label
    return (
        f"{label}\n{plural(summary.count, 'reply', 'replies')}"
        f"  ·  median {summary.median_days:g} d"
    )


def waiting_tooltip(waiting: Waiting, averages: dict[ReplyKind, float]) -> str:
    """Who, how long, and which average reply times it is past."""
    passed = [
        kind.lower() for kind, avg in averages.items() if waiting.days > avg
    ]
    if not averages:
        verdict = ""
    elif len(passed) == len(averages):
        verdict = "\nlonger than every average reply time"
    elif passed:
        verdict = f"\npast the average {' and '.join(passed)} reply time"
    else:
        verdict = "\nwithin every average reply time"
    return (
        f"{waiting.application.display_name}\n"
        f"waiting {plural(waiting.days, 'day')}{verdict}"
    )


def _draw_averages_for_comparison(
    axes, y: float, averages: dict[ReplyKind, float]
) -> list[HoverTarget]:
    """Each kind's average reply time across the pending row, dashed in
    the color of its row above; the value is in the tooltip."""
    hover_targets = []
    for kind, average in averages.items():
        axes.plot(
            [average] * 2,
            [y - MEAN_HALF_HEIGHT, y + MEAN_HALF_HEIGHT],
            color=REPLY_COLORS[kind],
            linewidth=1.6,
            linestyle=(0, (3, 2)),
            zorder=2,
        )
        # An invisible, wider line makes the dashes easy to hover.
        (hit_area,) = axes.plot(
            [average] * 2,
            [y - MEAN_HALF_HEIGHT, y + MEAN_HALF_HEIGHT],
            color="none",
            linewidth=8,
        )
        hover_targets.append(
            HoverTarget(
                hit_area, f"Ø {kind.lower()} reply: {average:.1f} days"
            )
        )
    return hover_targets


def _draw_ghosted_limit(axes, y: float) -> None:
    """Where waiting turns into being ghosted, across the pending row."""
    axes.plot(
        [GHOSTED_AFTER_DAYS] * 2,
        [y - MEAN_HALF_HEIGHT, y + MEAN_HALF_HEIGHT],
        color=BASELINE,
        linewidth=1.6,
        zorder=2,
    )
    axes.annotate(
        f"ghosted after {GHOSTED_AFTER_DAYS} d",
        (GHOSTED_AFTER_DAYS, y - MEAN_HALF_HEIGHT),
        xytext=(0, 2),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=TEXT_SMALL,
        color=INK_SECONDARY,
    )


def build_reply_times_figure(
    applications: Sequence[Application], today: date | None = None
) -> Figure:
    figure, axes = new_figure(6.4, 4.6)
    replies = first_replies(applications)
    waiting = waiting_for_reply(applications, today)
    if not replies and not waiting:
        show_empty_message(axes, "No applications in this time range")
        return figure

    rows: dict[str, list[FirstReply]] = {ALL_REPLIES: replies}
    for kind in ReplyKind:
        rows[kind] = [reply for reply in replies if reply.kind is kind]

    hover_targets = []
    row_labels = []
    for y, (label, row_replies) in enumerate(rows.items()):
        summary = ReplyTimeSummary.of(row_replies)
        row_labels.append(row_label(label, summary))
        color = REPLY_COLORS[label]
        if summary is None:
            axes.text(
                0,
                y,
                "  none yet",
                va="center",
                fontsize=TEXT_SMALL,
                color=INK_SECONDARY,
            )
            continue
        row_replies = sorted(row_replies, key=lambda reply: reply.days)
        for reply, offset in zip(
            row_replies, _stack_offsets(row_replies), strict=True
        ):
            (dot,) = axes.plot(
                [reply.days],
                [y + offset],
                marker="o",
                markersize=7,
                color=color,
                alpha=0.8,
                markeredgecolor=SURFACE,
                markeredgewidth=1,
                linestyle="none",
                zorder=3,
            )
            hover_targets.append(
                HoverTarget(
                    dot,
                    f"{reply.application.display_name}\n"
                    f"{plural(reply.days, 'day')} → {reply.stage}",
                )
            )
        axes.plot(
            [summary.mean_days] * 2,
            [y - MEAN_HALF_HEIGHT, y + MEAN_HALF_HEIGHT],
            color=INK_PRIMARY,
            linewidth=2,
            zorder=4,
        )
        axes.annotate(
            f"Ø {summary.mean_days:.1f} d",
            (summary.mean_days, y - MEAN_HALF_HEIGHT),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=TEXT_SMALL,
            color=INK_PRIMARY,
            zorder=5,
        )

    # Last, the applications still waiting: hollow, as nothing came yet.
    y = len(rows)
    waiting = sorted(waiting, key=lambda w: w.days)
    longest_reply = max((reply.days for reply in replies), default=0)
    axis_end = max(longest_reply, GHOSTED_AFTER_DAYS) * AXIS_END_MARGIN
    averages = {
        kind: summary.mean_days
        for kind in ReplyKind
        if (summary := ReplyTimeSummary.of(rows[kind]))
    }
    hover_targets += _draw_averages_for_comparison(axes, y, averages)
    if waiting:
        _draw_ghosted_limit(axes, y)
    shown_waiting = [  # past the axis end: at the end, pointing on
        Waiting(item.application, min(item.days, round(axis_end)))
        for item in waiting
    ]
    for item, shown, offset in zip(
        waiting, shown_waiting, _stack_offsets(shown_waiting), strict=True
    ):
        beyond = item.days > shown.days
        (dot,) = axes.plot(
            [shown.days],
            [y + offset],
            marker=">" if beyond else "o",
            markersize=7,
            markerfacecolor=SURFACE,
            markeredgecolor=INK_SECONDARY,
            markeredgewidth=1.5,
            linestyle="none",
            zorder=3,
            clip_on=False,
        )
        hover_targets.append(HoverTarget(dot, waiting_tooltip(item, averages)))
    if beyond_count := sum(
        item.days > shown.days
        for item, shown in zip(waiting, shown_waiting, strict=True)
    ):
        axes.annotate(
            f"{beyond_count} longer",
            (round(axis_end), y + MEAN_HALF_HEIGHT),
            xytext=(0, -2),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=TEXT_SMALL,
            color=INK_SECONDARY,
        )
    pending_summary = ReplyTimeSummary.of(waiting)
    row_labels.append(
        f"{PENDING}\n{pending_summary.count} waiting  ·  "
        f"median {pending_summary.median_days:g} d"
        if pending_summary
        else PENDING
    )

    axes.set_yticks(range(len(row_labels)))
    axes.set_yticklabels(row_labels, fontsize=TEXT_BODY, color=INK_SECONDARY)
    axes.set_ylim(len(row_labels) - 0.5, -0.75)  # all replies on top
    axes.set_xlim(-max(axis_end * 0.03, 0.5), axis_end + 1)
    axes.xaxis.get_major_locator().set_params(integer=True)
    axes.set_xlabel(
        "Days from applying to the first reply (pending: until today)",
        fontsize=TEXT_BODY,
        color=INK_SECONDARY,
    )
    style_bar_axes(axes, value_axis="x")
    axes.set_title(
        "Time to first reply",
        pad=24,
        **TITLE_STYLE,
    )
    axes.text(
        0,
        1.02,
        f"{len(replies)} of {plural(len(applications), 'application')} "
        f"answered, {len(waiting)} waiting  ·  Ø = average,"
        "  dashed = average per kind",
        transform=axes.transAxes,
        fontsize=TEXT_SMALL,
        color=INK_SECONDARY,
        va="bottom",
    )
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure
