"""Statistics charts: success rate, outcomes per company, company share."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from matplotlib.colors import to_rgba
from matplotlib.figure import Figure

from ..companies import group_by_company
from ..model import NO_COMPANY, Application
from ..outcomes import SUCCESS_TARGETS, Outcome, count_outcomes
from .style import (
    BASELINE,
    CATEGORICAL,
    GRIDLINE,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    OUTCOME_COLORS,
    SURFACE,
    TITLE_STYLE,
    HoverTarget,
    attach_hover,
    new_figure,
    plural,
    show_empty_message,
    style_bar_axes,
    truncate,
)

NO_APPLICATIONS_MESSAGE = "No applications in this time range"
DONUT_WEDGE_STYLE = {"width": 0.36, "edgecolor": SURFACE, "linewidth": 2}
# Not-targeted outcomes in the success donut are drawn this faint.
DIMMED_ALPHA = 0.18
COMPANY_BARS_MAX = 15
# One color per slice; one more than this becomes "Other".
COMPANY_SLICES_MAX = len(CATEGORICAL) - 1


def _draw_donut_center(axes, headline: str, caption: str) -> None:
    axes.text(
        0,
        0.08,
        headline,
        ha="center",
        va="center",
        fontsize=28,
        color=INK_PRIMARY,
    )
    axes.text(
        0,
        -0.2,
        caption,
        ha="center",
        va="center",
        fontsize=8.5,
        color=INK_SECONDARY,
    )


def build_success_rate_figure(
    applications: Sequence[Application],
    target: str,
    today: date | None = None,
) -> Figure:
    """Donut of all outcomes; those counting toward `target` (a key of
    SUCCESS_TARGETS) are highlighted, the rate sits in the middle."""
    figure, axes = new_figure(6.4, 4.6)
    total = len(applications)
    if not total:
        show_empty_message(axes, NO_APPLICATIONS_MESSAGE)
        return figure

    counts = count_outcomes(applications, today)
    targeted = SUCCESS_TARGETS[target]
    hits = sum(counts[outcome] for outcome in targeted)
    shown = [outcome for outcome in Outcome if counts[outcome]]
    _, labels = axes.pie(
        [counts[outcome] for outcome in shown],
        colors=[
            OUTCOME_COLORS[outcome]
            if outcome in targeted
            else to_rgba(OUTCOME_COLORS[outcome], DIMMED_ALPHA)
            for outcome in shown
        ],
        startangle=90,
        counterclock=False,
        labels=[f"{outcome}  {counts[outcome]}" for outcome in shown],
        labeldistance=1.12,
        wedgeprops=DONUT_WEDGE_STYLE,
        textprops={"fontsize": 8.5},
    )
    for outcome, label in zip(shown, labels, strict=True):
        is_targeted = outcome in targeted
        label.set_color(INK_PRIMARY if is_targeted else INK_MUTED)
        label.set_fontweight("bold" if is_targeted else "normal")

    _draw_donut_center(
        axes, f"{hits / total:.0%}", f"{hits} of {total} applications"
    )
    axes.set_title(f"{target} rate", pad=12, **TITLE_STYLE)
    axes.set_aspect("equal")

    figure.tight_layout()
    return figure


def build_company_outcomes_figure(
    applications: Sequence[Application],
    today: date | None = None,
    max_companies: int = COMPANY_BARS_MAX,
) -> Figure:
    """One horizontal bar per company, split into the outcomes of the
    applications sent there; most-applied-to companies on top."""
    figure, axes = new_figure(6.4, 4.6)
    groups = group_by_company(applications)
    if not groups:
        show_empty_message(axes, NO_APPLICATIONS_MESSAGE)
        return figure

    shown, hidden = groups[:max_companies], groups[max_companies:]
    widest = max(group.size for group in shown)
    label_gap = max(widest * 0.015, 0.08)
    hover_targets = []
    outcomes_present: set[Outcome] = set()
    for y, group in enumerate(shown):
        left = 0
        for outcome, members in group.by_outcome(today).items():
            if not members:
                continue
            outcomes_present.add(outcome)
            (segment,) = axes.barh(
                y,
                len(members),
                left=left,
                height=0.62,
                color=OUTCOME_COLORS[outcome],
                edgecolor=SURFACE,
                linewidth=1.5,
                zorder=3,
            )
            titles = "\n".join(f"• {a.job_title or a.id}" for a in members)
            hover_targets.append(
                HoverTarget(
                    segment,
                    f"{group.name} — {outcome}  ({len(members)})\n{titles}",
                )
            )
            left += len(members)
        axes.text(
            left + label_gap,
            y,
            str(left),
            ha="left",
            va="center",
            fontsize=9,
            color=INK_PRIMARY,
        )

    # Outcome legend in display order, only for outcomes that appear.
    for outcome in Outcome:
        if outcome in outcomes_present:
            axes.barh(0, 0, color=OUTCOME_COLORS[outcome], label=outcome)
    axes.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        frameon=False,
        fontsize=7.5,
        labelcolor=INK_SECONDARY,
        handlelength=1.2,
    )

    applied_repeatedly = sum(1 for group in groups if group.size > 1)
    subtitle = [plural(len(groups), "company", "companies")]
    if applied_repeatedly:
        subtitle.append(f"{applied_repeatedly} applied to more than once")
    if hidden:
        subtitle.append(f"top {len(shown)} shown")
    axes.set_title("Applications by company", pad=24, **TITLE_STYLE)
    axes.text(
        0,
        1.02,
        "  ·  ".join(subtitle),
        transform=axes.transAxes,
        fontsize=8.5,
        color=INK_SECONDARY,
        va="bottom",
    )

    axes.set_yticks(range(len(shown)))
    axes.set_yticklabels(
        [truncate(group.name) for group in shown],
        fontsize=8.5,
        color=INK_SECONDARY,
    )
    axes.invert_yaxis()
    axes.set_xlim(0, widest * 1.12)
    axes.xaxis.get_major_locator().set_params(integer=True)
    axes.set_xlabel("Applications", fontsize=9, color=INK_SECONDARY)
    style_bar_axes(axes, value_axis="x")
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    return figure


@dataclass(frozen=True)
class CompanySlice:
    label: str
    count: int
    color: str
    tooltip_lines: list[str]


def company_share_slices(
    applications: Sequence[Application],
    max_slices: int = COMPANY_SLICES_MAX,
) -> list[CompanySlice]:
    """The top companies by name; the rest folded into one "Other" slice.
    Applications without a company get their own neutral slice rather than
    counting as a company."""
    groups = group_by_company(applications)
    named = [group for group in groups if group.has_company]
    shown, rest = named[:max_slices], named[max_slices:]
    if len(rest) == 1:  # a lone company reads better by name than "Other"
        shown, rest = shown + rest, []
    slices = [
        CompanySlice(
            group.name,
            group.size,
            CATEGORICAL[index % len(CATEGORICAL)],
            [a.job_title or a.id for a in group.applications],
        )
        for index, group in enumerate(shown)
    ]
    if rest:
        slices.append(
            CompanySlice(
                f"Other ({plural(len(rest), 'company', 'companies')})",
                sum(group.size for group in rest),
                BASELINE,
                [f"{group.name}  ({group.size})" for group in rest],
            )
        )
    slices.extend(
        CompanySlice(
            NO_COMPANY,
            group.size,
            GRIDLINE,
            [a.job_title or a.id for a in group.applications],
        )
        for group in groups
        if not group.has_company
    )
    return slices


def build_company_share_figure(
    applications: Sequence[Application],
    max_slices: int = COMPANY_SLICES_MAX,
) -> Figure:
    """Donut of each company's share of all applications."""
    figure, axes = new_figure(6.4, 4.6)
    total = len(applications)
    if not total:
        show_empty_message(axes, NO_APPLICATIONS_MESSAGE)
        return figure

    slices = company_share_slices(applications, max_slices)
    wedges, _ = axes.pie(
        [company_slice.count for company_slice in slices],
        colors=[company_slice.color for company_slice in slices],
        startangle=90,
        counterclock=False,
        wedgeprops=DONUT_WEDGE_STYLE,
    )
    axes.legend(
        wedges,
        [f"{s.label}  {s.count} ({s.count / total:.0%})" for s in slices],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=8,
        labelcolor=INK_SECONDARY,
        handlelength=1.2,
    )
    hover_targets = [
        HoverTarget(
            wedge,
            f"{s.label}  —  {s.count} of {total} ({s.count / total:.0%})\n"
            + "\n".join(f"• {line}" for line in s.tooltip_lines),
        )
        for wedge, s in zip(wedges, slices, strict=True)
    ]

    company_count = sum(
        1 for group in group_by_company(applications) if group.has_company
    )
    company_word = "company" if company_count == 1 else "companies"
    _draw_donut_center(
        axes, str(company_count), f"{company_word} · {total} applications"
    )
    axes.set_title("Share of applications by company", pad=12, **TITLE_STYLE)
    axes.set_aspect("equal")
    attach_hover(figure, axes, hover_targets)

    figure.tight_layout()
    figure.subplots_adjust(right=0.6)  # room for the legend beside the donut
    return figure
