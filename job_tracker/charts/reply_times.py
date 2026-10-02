"""Reply times: how many days each application waited for its first reply,
one row per kind of reply, with the average marked."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from matplotlib.figure import Figure

from ..model import Application
from ..reply_times import (
    FirstReply,
    ReplyKind,
    ReplyTimeSummary,
    first_replies,
)
from .style import (
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


def _stack_offsets(replies: Sequence[FirstReply]) -> list[float]:
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


def build_reply_times_figure(applications: Sequence[Application]) -> Figure:
    figure, axes = new_figure(6.4, 4.6)
    replies = first_replies(applications)
    if not replies:
        show_empty_message(axes, "No replies in this time range")
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

    axes.set_yticks(range(len(rows)))
    axes.set_yticklabels(row_labels, fontsize=TEXT_BODY, color=INK_SECONDARY)
    axes.set_ylim(len(rows) - 0.5, -0.75)  # all replies on top
    longest = max(reply.days for reply in replies)
    axes.set_xlim(-max(longest * 0.04, 0.5), longest * 1.08 + 1)
    axes.xaxis.get_major_locator().set_params(integer=True)
    axes.set_xlabel(
        "Days from applying to the first reply",
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
        "answered  ·  Ø = average",
        transform=axes.transAxes,
        fontsize=TEXT_SMALL,
        color=INK_SECONDARY,
        va="bottom",
    )
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure
