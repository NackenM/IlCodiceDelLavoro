"""Charts of the application pipeline: outcome waterfall, per-application
progress, statistics (success rate, companies) and per-application timelines."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from matplotlib.colors import to_rgba
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from matplotlib.patches import Patch

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
# Interview-round segments in the progress chart show the round's format:
# on-site rounds are solid like every other stage, virtual (also the default
# when unset) and phone rounds a light tint of the application's color with a
# dashed or dotted outline.
FORMAT_LINESTYLES = {"Virtual": (0, (4, 2)), "Phone": (0, (1, 1.6))}
FORMAT_TINT_ALPHA = 0.3

COLOR_TOTAL = INK_SECONDARY
DIMMED_ALPHA = 0.18

SHORT_LABELS = {
    storage.STATUS_APPLIED: "Applied",
    storage.STATUS_ONLINE_ASSESSMENT: "Online\nAssessment",
    storage.STATUS_ROUND_1: "1st Round",
    storage.STATUS_ROUND_2: "2nd Round",
    storage.STATUS_ROUND_3: "3rd Round",
    storage.STATUS_CODING_CHALLENGE: "Coding\nChallenge",
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


def _row_tooltip(row: pd.Series, stage: str | None = None) -> str:
    lines = [row["company"] or "(no company)", row["job_title"], f"Status: {row['status'] or '--'}"]
    if stage in storage.ROUND_TAG_COLUMNS:
        lines.append(f"{SHORT_LABELS[stage]}: {' · '.join(storage.round_tags(row, stage))}")
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
    # A step for every round, even at zero, so the layout stays the same as
    # the data changes. The online assessment is optional, so like in the
    # progress chart it only appears once some application has one.
    has_assessment = any(_reached(r, storage.STATUS_ONLINE_ASSESSMENT) for r in rows)
    for stage in storage.FUNNEL_ORDER[1:-1]:
        if stage == storage.STATUS_ONLINE_ASSESSMENT and not has_assessment:
            continue
        rejected_here = [r for r in by_outcome[outcomes.REJECTED_LATER] if outcomes.rejection_stage(r) == stage]
        steps.append((
            "Rejected after\n" + SHORT_LABELS[stage], rejected_here,
            OUTCOME_COLORS[outcomes.REJECTED_LATER], False,
        ))
    # Still open: in an interview round or waiting for a first reply.
    steps.append((
        "In progress", by_outcome[outcomes.IN_PROGRESS] + by_outcome[outcomes.AWAITING],
        OUTCOME_COLORS[outcomes.IN_PROGRESS], False,
    ))
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
    ax.set_xticklabels([s[0] for s in steps], fontsize=7.5, color=INK_SECONDARY)
    ax.set_ylabel("Applications", fontsize=9, color=INK_SECONDARY)
    ax.set_ylim(0, total * 1.18 if total else 1)
    _style_bar_axes(ax)
    _attach_hover(fig, ax, segments)

    fig.tight_layout()
    return fig


def build_progress_figure(df: pd.DataFrame) -> Figure:
    fig, ax = _new_axes()

    total = len(df)
    # The online assessment is optional (not every company has one): its bar
    # is left out while nobody has reached it, and the connectors bypass it.
    assessment = storage.STATUS_ONLINE_ASSESSMENT
    stages = [
        s for s in storage.FUNNEL_ORDER
        if s != assessment or any(_reached(row, s) for _, row in df.iterrows())
    ]
    # Side stages after the forward pipeline: the optional coding challenge
    # and rejections.
    columns = stages + [storage.STATUS_CODING_CHALLENGE, storage.STATUS_REJECTED]
    labels = [SHORT_LABELS[s] for s in columns[:-1]] + ["Rejected"]
    x = list(range(len(columns)))

    # Style is assigned by CSV row order, so an application keeps its look
    # as others are added. Stacking puts the applications that got furthest
    # at the bottom, so each one forms a flat band that ends where it stopped.
    rows = [row for _, row in df.iterrows()]
    round_formats = {
        (row["id"], status): storage.round_format(row, status)
        for row in rows for status in storage.ROUNDS if _reached(row, status)
    }
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
            outline = FORMAT_LINESTYLES.get(round_formats.get((row["id"], status), ""))
            (patch,) = ax.bar(
                col_idx, 1, bottom=values[col_idx], width=0.62,
                color=to_rgba(color, FORMAT_TINT_ALPHA) if outline else color,
                hatch=hatch, hatchcolor=SURFACE, edgecolor=SURFACE, linewidth=1.5,
                label=label, zorder=3,
            )
            if outline:
                # Inset so the outline doesn't merge into the segments around it.
                ax.bar(
                    col_idx, 0.84, bottom=values[col_idx] + 0.08, width=0.54, fill=False,
                    edgecolor=color, linestyle=outline, linewidth=1.6, zorder=4,
                )
            label = "_nolegend_"  # one legend entry per application
            values[col_idx] += 1
            segments.append((patch, _row_tooltip(row, status)))
    funnel_values = values[: len(stages)]

    # Step connectors between consecutive funnel bars (the side stages sit
    # apart, outside the forward pipeline).
    linked = [i for i, s in enumerate(stages) if s != assessment]
    for a, b in zip(linked, linked[1:]):
        ax.plot(
            [a + 0.31, b - 0.31],
            [funnel_values[a], funnel_values[b]],
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

    if any(round_formats.values()):
        key = ax.legend(
            handles=[
                Patch(facecolor=INK_MUTED, label="On-site"),
                *(Patch(facecolor=to_rgba(INK_MUTED, FORMAT_TINT_ALPHA), edgecolor=INK_MUTED,
                        linestyle=style, linewidth=1.2, label=fmt)
                  for fmt, style in FORMAT_LINESTYLES.items()),
            ],
            loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, frameon=False,
            fontsize=7.5, labelcolor=INK_SECONDARY, handlelength=1.6, borderaxespad=0.3,
        )
        ax.add_artist(key)  # keep it when the application legend is added below
    if rows:
        legend_rows = 30  # one legend column up to this many applications
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


def build_company_share_figure(df: pd.DataFrame, max_slices: int = len(CATEGORICAL) - 1) -> Figure:
    """Donut of each company's share of all applications; companies past
    `max_slices` are folded into one "Other" slice."""
    fig, ax = _new_axes(figsize=(6.4, 4.6))
    groups = outcomes.group_by_company(df)
    total = len(df)

    if not total:
        ax.text(0.5, 0.5, "No applications in this time range", ha="center", va="center",
                fontsize=10, color=INK_MUTED, transform=ax.transAxes)
        ax.axis("off")
        return fig

    # (label, application count, color, tooltip lines). Applications without
    # a company get their own neutral slice rather than counting as a company.
    named = [g for g in groups if g[0] != outcomes.NO_COMPANY]
    unnamed = [apps for company, apps in groups if company == outcomes.NO_COMPANY]
    shown, rest = named[:max_slices], named[max_slices:]
    if len(rest) == 1:  # a lone company reads better by name than as "Other"
        shown, rest = shown + rest, []
    slices = [
        (company, len(apps), CATEGORICAL[i % len(CATEGORICAL)],
         [r["job_title"] or r["id"] for r, _ in apps])
        for i, (company, apps) in enumerate(shown)
    ]
    if rest:
        slices.append((
            f"Other ({len(rest)} compan{'ies' if len(rest) != 1 else 'y'})",
            sum(len(apps) for _, apps in rest), BASELINE,
            [f"{company}  ({len(apps)})" for company, apps in rest],
        ))
    for apps in unnamed:
        slices.append((outcomes.NO_COMPANY, len(apps), GRIDLINE, [r["job_title"] or r["id"] for r, _ in apps]))

    wedges, _ = ax.pie(
        [count for _, count, _, _ in slices], colors=[color for _, _, color, _ in slices],
        startangle=90, counterclock=False,
        wedgeprops={"width": 0.36, "edgecolor": SURFACE, "linewidth": 2},
    )
    ax.legend(
        wedges, [f"{label}  {count} ({count / total:.0%})" for label, count, _, _ in slices],
        loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False,
        fontsize=8, labelcolor=INK_SECONDARY, handlelength=1.2,
    )
    segments = [
        (wedge, f"{label}  —  {count} of {total} ({count / total:.0%})\n"
                + "\n".join(f"• {line}" for line in lines))
        for wedge, (label, count, _, lines) in zip(wedges, slices)
    ]

    ax.text(0, 0.08, str(len(named)), ha="center", va="center", fontsize=28, color=INK_PRIMARY)
    ax.text(0, -0.2, f"compan{'ies' if len(named) != 1 else 'y'} · {total} applications",
            ha="center", va="center", fontsize=8.5, color=INK_SECONDARY)
    ax.set_title("Share of applications by company", fontsize=11, color=INK_PRIMARY, loc="left", pad=12)
    ax.set_aspect("equal")
    _attach_hover(fig, ax, segments)

    fig.tight_layout()
    fig.subplots_adjust(right=0.6)  # room for the legend beside the donut
    return fig


TIMELINE_LABELS = {
    storage.STATUS_APPLIED: "Applied",
    storage.STATUS_ONLINE_ASSESSMENT: "OA",
    storage.STATUS_ROUND_1: "1st",
    storage.STATUS_ROUND_2: "2nd",
    storage.STATUS_ROUND_3: "3rd",
    storage.STATUS_CODING_CHALLENGE: "CC",
    storage.STATUS_REJECTED: "Rejected",
    storage.STATUS_OFFER: "Offer",
}
TIMELINE_COLORS = {
    storage.STATUS_APPLIED: INK_SECONDARY,
    storage.STATUS_ONLINE_ASSESSMENT: "#eda100",
    storage.STATUS_ROUND_1: "#2a78d6",
    storage.STATUS_ROUND_2: "#2a78d6",
    storage.STATUS_ROUND_3: "#2a78d6",
    storage.STATUS_CODING_CHALLENGE: "#4a3aa7",
    storage.STATUS_REJECTED: OUTCOME_COLORS[outcomes.REJECTED_LATER],
    storage.STATUS_OFFER: OUTCOME_COLORS[outcomes.OFFER],
}
# Day counts on segments narrower than this share of the time axis are left
# to the hover tooltip instead of colliding with the markers.
TIMELINE_MIN_LABEL_SHARE = 0.035
# Rough width of one label character as a share of the time axis, used to
# stagger stage labels that would overlap.
TIMELINE_CHAR_SHARE = 0.011


def _timeline_events(row: pd.Series) -> list[tuple[date, list[str]]]:
    """(day, stages reached that day) in date order; same-day stages share a
    marker, listed in pipeline order."""
    by_day: dict[date, list[str]] = {}
    for status in storage.STATUS_CHOICES:
        value = row[storage.STATUS_DATE_COLUMNS[status]]
        if value:
            by_day.setdefault(date.fromisoformat(value), []).append(status)
    return sorted(by_day.items())


def _stage_detail(row: pd.Series, status: str) -> str:
    if status in storage.ROUND_TAG_COLUMNS:
        return f"{status} ({' · '.join(storage.round_tags(row, status))})"
    if status == storage.STATUS_CODING_CHALLENGE and (position := storage.coding_challenge_position(row)):
        return f"{status} ({position})"
    return status


def build_timeline_figure(df: pd.DataFrame, today: date | None = None) -> Figure:
    """One row per application: a marker per stage reached, the days between
    consecutive stages on the line, and a dashed tail up to today for
    applications that are still open."""
    today = today or date.today()
    rows = [row for _, row in df.iterrows()]
    fig, ax = _new_axes(figsize=(9, 1.4 + 0.62 * max(len(rows), 1)))
    timelines = [(row, _timeline_events(row)) for row in rows]
    all_days = [day for _, events in timelines for day, _ in events]
    if not all_days:
        ax.text(0.5, 0.5, "The selected applications have no stage dates yet", ha="center", va="center",
                fontsize=10, color=INK_MUTED, transform=ax.transAxes)
        ax.axis("off")
        return fig

    open_rows = {row["id"] for row, _ in timelines
                 if outcomes.classify(row, today) in (outcomes.IN_PROGRESS, outcomes.AWAITING, outcomes.GHOSTED)}
    start = min(all_days)
    end = max(all_days + ([today] if open_rows else []))
    span = max((end - start).days, 1)

    # (artist, tooltip text) for the hover; markers are checked before the
    # line segments they sit on.
    markers, segments = [], []
    for y, (row, events) in enumerate(timelines):
        if not events:
            ax.text(start, y, "  no stage dates", va="center", fontsize=8, color=INK_MUTED)
            continue
        days = [day for day, _ in events]
        (line,) = ax.plot(days, [y] * len(days), color=BASELINE, linewidth=2.2, zorder=2)
        for (d0, s0), (d1, s1) in zip(events, events[1:]):
            gap = (d1 - d0).days
            if gap and gap / span >= TIMELINE_MIN_LABEL_SHARE:
                ax.text(d0 + (d1 - d0) / 2, y - 0.14, f"{gap}d", ha="center", va="bottom",
                        fontsize=7.5, color=INK_SECONDARY, zorder=5)
            (hit,) = ax.plot([d0, d1], [y, y], color="none", linewidth=8, zorder=1)
            segments.append((hit, f"{TIMELINE_LABELS[s0[-1]]} → {TIMELINE_LABELS[s1[0]]}: {gap} days\n"
                                  f"{d0:%d.%m.%Y} → {d1:%d.%m.%Y}"))

        last_day = days[-1]
        total_days = (last_day - days[0]).days
        if row["id"] in open_rows and today > last_day:
            ax.plot([last_day, today], [y, y], color=BASELINE, linewidth=1.6,
                    linestyle=(0, (3, 2)), zorder=2)
            outcome = outcomes.classify(row, today).lower()
            total_days = (today - days[0]).days
            summary, summary_at = f"{total_days}d so far · {outcome}", today
        else:
            summary, summary_at = f"{total_days}d in total", last_day
        ax.annotate(summary, (summary_at, y), xytext=(9, 0), textcoords="offset points",
                    va="center", fontsize=7.5, color=INK_SECONDARY)

        level, prev_day, prev_text = 0, None, ""
        for day, stages in events:
            color = TIMELINE_COLORS[stages[-1]]
            (marker,) = ax.plot([day], [y], marker="o", markersize=8, color=color,
                                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=4)
            text = "+".join(TIMELINE_LABELS[s] for s in stages)
            # Step the stage label down when it would run into the previous one.
            needed = ((len(prev_text) + len(text)) / 2 + 2) * TIMELINE_CHAR_SHARE
            crowded = prev_day is not None and (day - prev_day).days / span < needed
            level = 1 - level if crowded else 0
            prev_day, prev_text = day, text
            ax.text(day, y + 0.2 + 0.17 * level, text,
                    ha="center", va="top", fontsize=7.5, color=color, zorder=5)
            details = "\n".join(_stage_detail(row, s) for s in stages)
            markers.append((marker, f"{day:%d.%m.%Y}\n{details}"))

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([_legend_label(row) for row in rows], fontsize=8.5, color=INK_SECONDARY)
    ax.set_ylim(len(rows) - 0.35, -0.6)  # first selected application on top
    # Room on the right for the "Nd so far" summaries.
    ax.set_xlim(start - timedelta(days=span * 0.03), end + timedelta(days=span * 0.22))
    ax.xaxis.set_major_formatter(DateFormatter("%d.%m."))
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for name, spine in ax.spines.items():
        spine.set_visible(name == "bottom")
        spine.set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, length=0, labelsize=8)
    ax.set_title(f"Timeline  ·  {len(rows)} application{'s' if len(rows) != 1 else ''}",
                 fontsize=11, color=INK_PRIMARY, loc="left", pad=12)
    _attach_hover(fig, ax, markers + segments)

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
