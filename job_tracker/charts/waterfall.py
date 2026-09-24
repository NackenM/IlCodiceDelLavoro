"""Outcome waterfall: all applications at the start, each way they dropped
out (or are still open) subtracted in turn, offers left as the total."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from matplotlib.figure import Figure

from ..model import Application
from ..outcomes import Outcome, group_by_outcome, rejection_stage
from ..stages import PIPELINE, Stage
from .style import (
    BASELINE,
    INK_PRIMARY,
    INK_SECONDARY,
    OUTCOME_COLORS,
    STAGE_AXIS_LABELS,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    new_figure,
    plural,
    style_bar_axes,
)

BAR_WIDTH = 0.62
TOTAL_COLOR = INK_SECONDARY


@dataclass(frozen=True)
class WaterfallStep:
    label: str
    applications: Sequence[Application]
    color: str
    # A total stands on the baseline; other steps hang from the running
    # total and subtract from it.
    is_total: bool = False

    @property
    def count(self) -> int:
        return len(self.applications)


def waterfall_steps(
    applications: Sequence[Application], today: date | None = None
) -> list[WaterfallStep]:
    by_outcome = group_by_outcome(applications, today)

    def outcome_step(label: str, outcome: Outcome) -> WaterfallStep:
        return WaterfallStep(
            label, by_outcome[outcome], OUTCOME_COLORS[outcome]
        )

    steps = [
        WaterfallStep(
            "Applications", applications, TOTAL_COLOR, is_total=True
        ),
        outcome_step("Ghosted", Outcome.GHOSTED),
        outcome_step("Rejected\nright away", Outcome.REJECTED_RIGHT_AWAY),
    ]
    # A step for every round, even at zero, so the layout stays the same as
    # the data changes. The online assessment is optional, so it only
    # appears once some application has one.
    has_assessment = any(
        a.has_reached(Stage.ONLINE_ASSESSMENT) for a in applications
    )
    for stage in PIPELINE[1:-1]:
        if stage is Stage.ONLINE_ASSESSMENT and not has_assessment:
            continue
        rejected_here = [
            a
            for a in by_outcome[Outcome.REJECTED_AFTER_STAGE]
            if rejection_stage(a) is stage
        ]
        steps.append(
            WaterfallStep(
                f"Rejected after\n{STAGE_AXIS_LABELS[stage]}",
                rejected_here,
                OUTCOME_COLORS[Outcome.REJECTED_AFTER_STAGE],
            )
        )
    # Still open: in an interview round or waiting for a first reply.
    steps.append(
        WaterfallStep(
            "In progress",
            by_outcome[Outcome.IN_PROGRESS]
            + by_outcome[Outcome.AWAITING_REPLY],
            OUTCOME_COLORS[Outcome.IN_PROGRESS],
        )
    )
    steps.append(
        WaterfallStep(
            "Offers",
            by_outcome[Outcome.OFFER],
            OUTCOME_COLORS[Outcome.OFFER],
            is_total=True,
        )
    )
    return steps


def build_outcome_waterfall_figure(
    applications: Sequence[Application], today: date | None = None
) -> Figure:
    figure, axes = new_figure()
    total = len(applications)
    steps = waterfall_steps(applications, today)

    label_gap = max(total * 0.02, 0.15)
    running_total = total
    hover_targets = []
    for x, step in enumerate(steps):
        if step.is_total:
            bottom, top, value_text = 0, step.count, str(step.count)
        else:
            bottom, top = running_total - step.count, running_total
            value_text = f"−{step.count}" if step.count else "0"
            running_total -= step.count
        if step.count:
            (bar,) = axes.bar(
                x,
                top - bottom,
                bottom=bottom,
                width=BAR_WIDTH,
                color=step.color,
                zorder=3,
            )
            names = "\n".join(
                f"• {a.company or a.job_title or a.id}"
                for a in step.applications
            )
            one_line_label = step.label.replace("\n", " ")
            hover_targets.append(
                HoverTarget(bar, f"{one_line_label}  ({step.count})\n{names}")
            )
        axes.text(
            x,
            top + label_gap,
            value_text,
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK_PRIMARY,
        )
        if x < len(steps) - 1:
            # Connector at the running total, carried over to the next bar.
            axes.plot(
                [x + BAR_WIDTH / 2, x + 1 - BAR_WIDTH / 2],
                [running_total, running_total],
                color=BASELINE,
                linewidth=1,
                linestyle=(0, (3, 2)),
                zorder=2,
            )

    offers = steps[-1].count
    offer_rate = f"{offers / total:.0%}" if total else "--"
    axes.set_title(
        f"Application Outcomes  ·  {total} applied → "
        f"{plural(offers, 'offer')} ({offer_rate})",
        pad=12,
        **TITLE_STYLE,
    )
    axes.set_xticks(range(len(steps)))
    axes.set_xticklabels(
        [step.label for step in steps], fontsize=7.5, color=INK_SECONDARY
    )
    axes.set_ylabel("Applications", fontsize=9, color=INK_SECONDARY)
    axes.set_ylim(0, total * 1.18 if total else 1)
    style_bar_axes(axes)
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure
