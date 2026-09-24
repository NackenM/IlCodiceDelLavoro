"""Charts of the application pipeline: outcome waterfall, per-application
progress, and the success-rate donut."""
from __future__ import annotations

import pandas as pd
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure

from . import outcomes, storage

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Categorical palette, in fixed order -- each application keeps one identity
# across every bar. Past eight applications the hues repeat with a hatch
# texture so identity never depends on a cycled color alone.
CATEGORICAL = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]
HATCHES = ["", "////", "\\\\\\\\", "...."]

LEGEND_LABEL_MAX = 30
COMPANY_BARS_MAX = 15

# One color per outcome, shared by the waterfall and the donut. Offer and the
# rejections use the reserved status colors; always shown with a text label.
OUTCOME_COLORS = {
    outcomes.OFFER: "#0ca30c",
    outcomes.IN_PROGRESS: "#2a78d6",
    outcomes.REJECTED_LATER: "#d03b3b",
    outcomes.REJECTED_EARLY: "#ec835a",
    outcomes.GHOSTED: "#4a3aa7",
    outcomes.AWAITING: "#eda100",
}
COLOR_TOTAL = INK_SECONDARY
DIMMED_ALPHA = 0.18

SHORT_LABELS = {
    storage.STATUS_APPLIED: "Applied",
    storage.STATUS_CODING_CHALLENGE: "Coding\nChallenge",
    storage.STATUS_INTERVIEW_INITIAL: "Initial\nInterview",
    storage.STATUS_INTERVIEW_VIRTUAL: "Virtual\nInterview",
    storage.STATUS_INTERVIEW_2ND: "2nd Round",
    storage.STATUS_INTERVIEW_3RD: "3rd Round",
    storage.STATUS_INTERVIEW_ONSITE: "On-site",
    storage.STATUS_OFFER: "Offer",
}


def _reached(row: pd.Series, status: str) -> bool:
    return str(row[storage.STATUS_DATE_COLUMNS[status]]).strip() != ""


def _furthest_stage(row: pd.Series) -> int:
    reached = [i for i, s in enumerate(storage.FUNNEL_ORDER) if _reached(row, s)]
    return max(reached, default=-1)


def _legend_label(row: pd.Series) -> str:
    label = " · ".join(p for p in (row["company"], row["job_title"]) if p) or row["id"]
    if len(label) > LEGEND_LABEL_MAX:
        label = label[: LEGEND_LABEL_MAX - 1] + "…"
    return label


def _new_axes(figsize=(8.5, 4.6)):
    fig = Figure(figsize=figsize, dpi=100, facecolor=SURFACE)
    ax = fig.add_subplot(111)
    ax.set_facecolor(SURFACE)
    return fig, ax


def _style_bar_axes(ax) -> None:
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for name, spine in ax.spines.items():
        if name in ("top", "right"):
            spine.set_visible(False)
        else:
            spine.set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, length=0)


def _row_tooltip(row: pd.Series) -> str:
    lines = [row["company"] or "(no company)", row["job_title"], f"Status: {row['status'] or '--'}"]
    return "\n".join(line for line in lines if line)


def build_outcome_waterfall_figure(df: pd.DataFrame) -> Figure:
    """Financial-style waterfall: all applications at the start, each way an
    application dropped out (or is still open) subtracted in turn, offers left
    over as the final total."""
    fig, ax = _new_axes()
    rows = [row for _, row in df.iterrows()]
    total = len(rows)
    by_outcome = {o: [r for r in rows if outcomes.classify(r) == o] for o in outcomes.OUTCOME_ORDER}

    # (tick label, applications in the bar, color, is_total)
    steps = [("Applications", rows, COLOR_TOTAL, True)]
    steps.append(("Ghosted", by_outcome[outcomes.GHOSTED], OUTCOME_COLORS[outcomes.GHOSTED], False))
    steps.append((
        "Rejected\nright away", by_outcome[outcomes.REJECTED_EARLY],
        OUTCOME_COLORS[outcomes.REJECTED_EARLY], False,
    ))
    for stage in storage.FUNNEL_ORDER[1:-1]:
        rejected_here = [r for r in by_outcome[outcomes.REJECTED_LATER] if outcomes.rejection_stage(r) == stage]
        if rejected_here:  # only stages where someone actually dropped out
            steps.append((
                "Rejected after\n" + SHORT_LABELS[stage].replace("\n", " "), rejected_here,
                OUTCOME_COLORS[outcomes.REJECTED_LATER], False,
            ))
    steps.append(("Awaiting\nreply", by_outcome[outcomes.AWAITING], OUTCOME_COLORS[outcomes.AWAITING], False))
    steps.append(("In progress", by_outcome[outcomes.IN_PROGRESS], OUTCOME_COLORS[outcomes.IN_PROGRESS], False))
    steps.append(("Offers", by_outcome[outcomes.OFFER], OUTCOME_COLORS[outcomes.OFFER], True))

    label_pad = max(total * 0.02, 0.15)
    running = total
    segments = []
    for i, (label, apps, color, is_total) in enumerate(steps):
        count = len(apps)
        if is_total:
            bottom, top, text = 0, count, str(count)
        else:
            bottom, top, text = running - count, running, f"\u2212{count}" if count else "0"
            running -= count
        if count:
            (patch,) = ax.bar(i, top - bottom, bottom=bottom, width=0.62, color=color, zorder=3)
            names = "\n".join(f"\u2022 {r['company'] or r['job_title'] or r['id']}" for r in apps)
            segments.append((patch, f"{label.replace(chr(10), ' ')}  ({count})\n{names}"))
        ax.text(i, top + label_pad, text, ha="center", va="bottom", fontsize=9, color=INK_PRIMARY)
        if i < len(steps) - 1:
            # Connector at the running total, carried over to the next bar.
            ax.plot([i + 0.31, i + 1 - 0.31], [running, running], color=BASELINE,
                    linewidth=1, linestyle=(0, (3, 2)), zorder=2)

    offers = len(by_outcome[outcomes.OFFER])
    rate = f"{offers / total:.0%}" if total else "--"
    ax.set_title(
        f"Application Outcomes  ·  {total} applied \u2192 {offers} offer{'s' if offers != 1 else ''} ({rate})",
        fontsize=11, color=INK_PRIMARY, loc="left", pad=12,
    )
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels([s[0] for s in steps], fontsize=8, color=INK_SECONDARY)
    ax.set_ylabel("Applications", fontsize=9, color=INK_SECONDARY)
    ax.set_ylim(0, total * 1.18 if total else 1)
    _style_bar_axes(ax)
    _attach_hover(fig, ax, segments)

    fig.tight_layout()
    return fig


def build_progress_figure(df: pd.DataFrame) -> Figure:
    fig, ax = _new_axes()

    total = len(df)
    stages = storage.FUNNEL_ORDER
    columns = stages + [storage.STATUS_REJECTED]
    labels = [SHORT_LABELS[s] for s in stages] + ["Rejected"]
    x = list(range(len(columns)))

    # Style is assigned by CSV row order, so an application keeps its look
    # as others are added. Stacking puts the applications that got furthest
    # at the bottom, so each one forms a flat band that ends where it stopped.
    rows = [row for _, row in df.iterrows()]
    styles = {
        row["id"]: (CATEGORICAL[i % len(CATEGORICAL)], HATCHES[(i // len(CATEGORICAL)) % len(HATCHES)])
        for i, row in enumerate(rows)
    }
    stack_order = sorted(range(len(rows)), key=lambda i: (-_furthest_stage(rows[i]), i))

    values = [0] * len(columns)
    segments = []  # (patch, row) pairs for the hover tooltip
    for i in stack_order:
        row = rows[i]
        color, hatch = styles[row["id"]]
        label = _legend_label(row)
        for col_idx, status in enumerate(columns):
            if not _reached(row, status):
                continue
            (patch,) = ax.bar(
                col_idx, 1, bottom=values[col_idx], width=0.62, color=color,
                hatch=hatch, hatchcolor=SURFACE, edgecolor=SURFACE, linewidth=1.5,
                label=label, zorder=3,
            )
            label = "_nolegend_"  # one legend entry per application
            values[col_idx] += 1
            segments.append((patch, _row_tooltip(row)))
    funnel_values = values[: len(stages)]

    # Step connectors between consecutive funnel bars (Rejected sits apart,
    # as an exit stat rather than a forward pipeline stage).
    for i in range(len(funnel_values) - 1):
        ax.plot(
            [i + 0.31, i + 1 - 0.31],
            [funnel_values[i], funnel_values[i + 1]],
            color=BASELINE, linewidth=1.2, zorder=2,
        )

    max_val = max(values) if values else 0
    for col_idx, val in zip(x, values):
        ax.text(
            col_idx,
            val + max(max_val * 0.02, 0.15),
            str(val), ha="center", va="bottom", fontsize=9, color=INK_PRIMARY,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5, color=INK_SECONDARY)
    ax.set_ylabel("Applications", fontsize=9, color=INK_SECONDARY)
    ax.set_title(
        f"Application Pipeline  ·  {total} total",
        fontsize=11, color=INK_PRIMARY, loc="left", pad=12,
    )

    ax.set_ylim(0, max_val * 1.18 if max_val else 1)
    _style_bar_axes(ax)

    if rows:
        legend_rows = 18
        ax.legend(
            loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False,
            fontsize=7.5, labelcolor=INK_SECONDARY, handlelength=1.4, reverse=True,
            ncol=-(-len(rows) // legend_rows),
        )
    _attach_hover(fig, ax, segments)

    fig.tight_layout()
    return fig


def build_success_donut_figure(df: pd.DataFrame, target: str) -> Figure:
    """Donut of all outcomes; those counting toward `target` are highlighted
    and the rate (target / all applications) sits in the middle."""
    fig, ax = _new_axes(figsize=(6.4, 4.6))
    counts = outcomes.count_outcomes(df)
    total = len(df)
    target_outcomes = outcomes.TARGETS[target]
    hits = sum(counts[o] for o in target_outcomes)

    if not total:
        ax.text(0.5, 0.5, "No applications in this time range", ha="center", va="center",
                fontsize=10, color=INK_MUTED, transform=ax.transAxes)
        ax.axis("off")
        return fig

    shown = [o for o in outcomes.OUTCOME_ORDER if counts[o]]
    colors = [
        OUTCOME_COLORS[o] if o in target_outcomes else to_rgba(OUTCOME_COLORS[o], DIMMED_ALPHA)
        for o in shown
    ]
    wedges, texts = ax.pie(
        [counts[o] for o in shown], colors=colors, startangle=90, counterclock=False,
        labels=[f"{o}  {counts[o]}" for o in shown], labeldistance=1.12,
        wedgeprops={"width": 0.36, "edgecolor": SURFACE, "linewidth": 2},
        textprops={"fontsize": 8.5},
    )
    for outcome, text in zip(shown, texts):
        in_target = outcome in target_outcomes
        text.set_color(INK_PRIMARY if in_target else INK_MUTED)
        text.set_fontweight("bold" if in_target else "normal")

    ax.text(0, 0.08, f"{hits / total:.0%}", ha="center", va="center", fontsize=28, color=INK_PRIMARY)
    ax.text(0, -0.2, f"{hits} of {total} applications", ha="center", va="center",
            fontsize=8.5, color=INK_SECONDARY)
    ax.set_title(f"{target} rate", fontsize=11, color=INK_PRIMARY, loc="left", pad=12)
    ax.set_aspect("equal")

    fig.tight_layout()
    return fig


def build_company_figure(df: pd.DataFrame, max_companies: int = COMPANY_BARS_MAX) -> Figure:
    """One horizontal bar per company, split into the outcomes of the
    applications sent there; most-applied-to companies on top."""
    fig, ax = _new_axes(figsize=(6.4, 4.6))
    groups = outcomes.group_by_company(df)

    if not groups:
        ax.text(0.5, 0.5, "No applications in this time range", ha="center", va="center",
                fontsize=10, color=INK_MUTED, transform=ax.transAxes)
        ax.axis("off")
        return fig

    shown = groups[:max_companies]
    hidden = groups[max_companies:]
    max_count = max(len(apps) for _, apps in shown)
    label_pad = max(max_count * 0.015, 0.08)
    segments = []
    used_outcomes = set()
    for y, (company, apps) in enumerate(shown):
        left = 0
        for outcome in outcomes.OUTCOME_ORDER:
            rows = [row for row, o in apps if o == outcome]
            if not rows:
                continue
            used_outcomes.add(outcome)
            (patch,) = ax.barh(
                y, len(rows), left=left, height=0.62, color=OUTCOME_COLORS[outcome],
                edgecolor=SURFACE, linewidth=1.5, zorder=3,
            )
            titles = "\n".join(f"• {r['job_title'] or r['id']}" for r in rows)
            segments.append((patch, f"{company} — {outcome}  ({len(rows)})\n{titles}"))
            left += len(rows)
        ax.text(left + label_pad, y, str(left), ha="left", va="center", fontsize=9, color=INK_PRIMARY)

    # Outcome legend in display order, only for outcomes that appear.
    for outcome in outcomes.OUTCOME_ORDER:
        if outcome in used_outcomes:
            ax.barh(0, 0, color=OUTCOME_COLORS[outcome], label=outcome)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False,
              fontsize=7.5, labelcolor=INK_SECONDARY, handlelength=1.2)

    repeat = sum(1 for _, apps in groups if len(apps) > 1)
    subtitle = [f"{len(groups)} compan{'ies' if len(groups) != 1 else 'y'}"]
    if repeat:
        subtitle.append(f"{repeat} applied to more than once")
    if hidden:
        subtitle.append(f"top {len(shown)} shown")
    ax.set_title("Applications by company", fontsize=11, color=INK_PRIMARY, loc="left", pad=24)
    ax.text(0, 1.02, "  ·  ".join(subtitle), transform=ax.transAxes,
            fontsize=8.5, color=INK_SECONDARY, va="bottom")

    ax.set_yticks(range(len(shown)))
    ax.set_yticklabels(
        [c if len(c) <= LEGEND_LABEL_MAX else c[: LEGEND_LABEL_MAX - 1] + "…" for c, _ in shown],
        fontsize=8.5, color=INK_SECONDARY,
    )
    ax.invert_yaxis()
    ax.set_xlim(0, max_count * 1.12)
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("Applications", fontsize=9, color=INK_SECONDARY)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for name, spine in ax.spines.items():
        spine.set_visible(name in ("left", "bottom"))
        spine.set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, length=0)
    _attach_hover(fig, ax, segments)

    fig.tight_layout()
    return fig


def _attach_hover(fig: Figure, ax, segments) -> None:
    """Show a tooltip for the bar segment under the mouse; `segments` holds
    (patch, tooltip text) pairs."""
    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        fontsize=8, color=INK_PRIMARY, zorder=10,
        bbox={"boxstyle": "round,pad=0.4", "fc": SURFACE, "ec": BASELINE},
    )
    tooltip.set_visible(False)

    def on_move(event):
        hit = None
        if event.inaxes is ax:
            hit = next((text for patch, text in segments if patch.contains(event)[0]), None)
        if hit is None:
            if tooltip.get_visible():
                tooltip.set_visible(False)
                fig.canvas.draw_idle()
            return
        tooltip.set_text(hit)
        tooltip.xy = (event.xdata, event.ydata)
        # Flip the tooltip to the left of the cursor on the right half of the plot.
        right_half = event.x > ax.bbox.x0 + ax.bbox.width / 2
        tooltip.set_position((-12, 12) if right_half else (12, 12))
        tooltip.set_horizontalalignment("right" if right_half else "left")
        tooltip.set_visible(True)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)
