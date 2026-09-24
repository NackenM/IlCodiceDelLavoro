"""Waterfall / funnel visualization of the application pipeline."""
from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure

from . import storage

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
COLOR_OFFER = "#0ca30c"
COLOR_REJECTED = "#d03b3b"

# Ordinal blue ramp (light -> dark) for the forward funnel stages.
BLUE_RAMP = [
    "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
    "#2a78d6", "#256abf", "#1c5cab", "#184f95",
]

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


def _reached_count(df: pd.DataFrame, status: str) -> int:
    col = storage.STATUS_DATE_COLUMNS[status]
    return int((df[col].astype(str).str.strip() != "").sum())


def build_waterfall_figure(df: pd.DataFrame) -> Figure:
    fig = Figure(figsize=(8.5, 4.6), dpi=100, facecolor=SURFACE)
    ax = fig.add_subplot(111)
    ax.set_facecolor(SURFACE)

    total = len(df)
    stages = storage.FUNNEL_ORDER
    funnel_values = [_reached_count(df, s) for s in stages]
    rejected = _reached_count(df, storage.STATUS_REJECTED)

    labels = [SHORT_LABELS[s] for s in stages] + ["Rejected"]
    values = funnel_values + [rejected]

    colors = []
    for i, s in enumerate(stages):
        if s == storage.STATUS_OFFER:
            colors.append(COLOR_OFFER)
        else:
            colors.append(BLUE_RAMP[min(i, len(BLUE_RAMP) - 1)])
    colors.append(COLOR_REJECTED)

    x = list(range(len(values)))
    bars = ax.bar(x, values, color=colors, width=0.62, zorder=3)

    # Step connectors between consecutive funnel bars (Rejected sits apart,
    # as an exit stat rather than a forward pipeline stage).
    for i in range(len(funnel_values) - 1):
        ax.plot(
            [i + 0.31, i + 1 - 0.31],
            [funnel_values[i], funnel_values[i + 1]],
            color=BASELINE, linewidth=1.2, zorder=2,
        )

    max_val = max(values) if values else 0
    for rect, val in zip(bars, values):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
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
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for name, spine in ax.spines.items():
        if name in ("top", "right"):
            spine.set_visible(False)
        else:
            spine.set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, length=0)

    fig.tight_layout()
    return fig
