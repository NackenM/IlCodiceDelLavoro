"""Progress by application: one stacked bar per stage, one colored segment
per application that reached it."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from matplotlib.axes import Axes
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from ..model import Application
from ..stages import INTERVIEW_ROUNDS, PIPELINE, RoundFormat, Stage
from .style import (
    BASELINE,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    STAGE_AXIS_LABELS,
    SURFACE,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    categorical_style,
    new_figure,
    style_bar_axes,
    truncate,
)

BAR_WIDTH = 0.62
# Side stages drawn after the forward pipeline.
SIDE_STAGES = (Stage.CODING_CHALLENGE, Stage.REJECTED)
# Interview-round segments show the round's format: on-site rounds are
# solid like every other stage, virtual (also the default) and phone rounds
# a light tint of the application's color with a dashed or dotted outline.
FORMAT_OUTLINES = {
    RoundFormat.VIRTUAL: (0, (4, 2)),
    RoundFormat.PHONE: (0, (1, 1.6)),
}
TINT_ALPHA = 0.3
# The application legend stays in one column up to this many entries.
LEGEND_ROWS_PER_COLUMN = 30


def shown_stages(applications: Sequence[Application]) -> list[Stage]:
    """The pipeline stages with a bar. The online assessment is optional
    (not every company has one), so it only shows once somebody reached
    it."""
    return [
        stage
        for stage in PIPELINE
        if stage is not Stage.ONLINE_ASSESSMENT
        or any(a.has_reached(stage) for a in applications)
    ]


def _segment_tooltip(application: Application, stage: Stage) -> str:
    lines = [
        application.company_display_name,
        application.job_title,
        f"Status: {application.status}",
    ]
    if stage in INTERVIEW_ROUNDS:
        tags = " · ".join(application.tags_of(stage).descriptions())
        lines.append(f"{STAGE_AXIS_LABELS[stage]}: {tags}")
    return "\n".join(line for line in lines if line)


def _draw_format_key(axes: Axes) -> None:
    """Small key above the plot explaining the round outlines."""
    handles = [Patch(facecolor=INK_MUTED, label=RoundFormat.ON_SITE)]
    handles += [
        Patch(
            facecolor=to_rgba(INK_MUTED, TINT_ALPHA),
            edgecolor=INK_MUTED,
            linestyle=outline,
            linewidth=1.2,
            label=round_format,
        )
        for round_format, outline in FORMAT_OUTLINES.items()
    ]
    key = axes.legend(
        handles=handles,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=3,
        frameon=False,
        fontsize=7.5,
        labelcolor=INK_SECONDARY,
        handlelength=1.6,
        borderaxespad=0.3,
    )
    axes.add_artist(key)  # keep it when the application legend is added


def build_progress_figure(applications: Sequence[Application]) -> Figure:
    figure, axes = new_figure()
    pipeline_stages = shown_stages(applications)
    columns = [*pipeline_stages, *SIDE_STAGES]

    # Colors follow the CSV order, so an application keeps its look as
    # others are added. The applications that got furthest are stacked at
    # the bottom, so each forms a flat band that ends where it stopped.
    styles = {a.id: categorical_style(i) for i, a in enumerate(applications)}
    stacking_order = sorted(
        enumerate(applications),
        key=lambda item: (-item[1].furthest_pipeline_index(), item[0]),
    )

    column_heights = [0] * len(columns)
    hover_targets = []
    any_round_reached = False
    for _, application in stacking_order:
        color, hatch = styles[application.id]
        legend_label = truncate(application.display_name)
        for x, stage in enumerate(columns):
            if not application.has_reached(stage):
                continue
            outline = None
            if stage in INTERVIEW_ROUNDS:
                any_round_reached = True
                round_format = application.tags_of(stage).effective_format
                outline = FORMAT_OUTLINES.get(round_format)
            (segment,) = axes.bar(
                x,
                1,
                bottom=column_heights[x],
                width=BAR_WIDTH,
                color=to_rgba(color, TINT_ALPHA) if outline else color,
                hatch=hatch,
                hatchcolor=SURFACE,
                edgecolor=SURFACE,
                linewidth=1.5,
                label=legend_label,
                zorder=3,
            )
            if outline:
                # Inset, so the outline doesn't merge into its neighbours.
                axes.bar(
                    x,
                    0.84,
                    bottom=column_heights[x] + 0.08,
                    width=BAR_WIDTH - 0.08,
                    fill=False,
                    edgecolor=color,
                    linestyle=outline,
                    linewidth=1.6,
                    zorder=4,
                )
            legend_label = "_nolegend_"  # one legend entry per application
            column_heights[x] += 1
            hover_targets.append(
                HoverTarget(segment, _segment_tooltip(application, stage))
            )

    # Step connectors between the pipeline bars; they bypass the optional
    # online assessment, and the side stages stand apart.
    linked = [
        x
        for x, stage in enumerate(pipeline_stages)
        if stage is not Stage.ONLINE_ASSESSMENT
    ]
    for left, right in pairwise(linked):
        axes.plot(
            [left + BAR_WIDTH / 2, right - BAR_WIDTH / 2],
            [column_heights[left], column_heights[right]],
            color=BASELINE,
            linewidth=1.2,
            zorder=2,
        )

    tallest = max(column_heights, default=0)
    for x, height in enumerate(column_heights):
        axes.text(
            x,
            height + max(tallest * 0.02, 0.15),
            str(height),
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK_PRIMARY,
        )

    axes.set_xticks(range(len(columns)))
    axes.set_xticklabels(
        [STAGE_AXIS_LABELS[stage] for stage in columns],
        fontsize=8.5,
        color=INK_SECONDARY,
    )
    axes.set_ylabel("Applications", fontsize=9, color=INK_SECONDARY)
    axes.set_title(
        f"Application Pipeline  ·  {len(applications)} total",
        pad=12,
        **TITLE_STYLE,
    )
    axes.set_ylim(0, tallest * 1.18 if tallest else 1)
    style_bar_axes(axes)

    if any_round_reached:
        _draw_format_key(axes)
    if applications:
        axes.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1),
            frameon=False,
            fontsize=7.5,
            labelcolor=INK_SECONDARY,
            handlelength=1.4,
            reverse=True,
            ncol=-(-len(applications) // LEGEND_ROWS_PER_COLUMN),
        )
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure
