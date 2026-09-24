"""Shared look of all charts: palette, axes styling, hover tooltips."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ..outcomes import Outcome
from ..stages import Stage

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Categorical palette, in fixed order, so each application or company keeps
# one identity. Past eight entries the hues repeat with a hatch texture, so
# identity never depends on a cycled color alone.
CATEGORICAL = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
]
HATCHES = ["", "////", "\\\\\\\\", "...."]

# One color per outcome, shared by every chart. Offer and the rejections
# use the reserved status colors; always shown with a text label.
OUTCOME_COLORS = {
    Outcome.OFFER: "#0ca30c",
    Outcome.IN_PROGRESS: "#2a78d6",
    Outcome.REJECTED_AFTER_STAGE: "#d03b3b",
    Outcome.REJECTED_RIGHT_AWAY: "#ec835a",
    Outcome.GHOSTED: "#4a3aa7",
    Outcome.AWAITING_REPLY: "#eda100",
}

# Stage names under the bars.
STAGE_AXIS_LABELS = {
    Stage.APPLIED: "Applied",
    Stage.ONLINE_ASSESSMENT: "Online\nAssessment",
    Stage.ROUND_1: "1st Round",
    Stage.ROUND_2: "2nd Round",
    Stage.ROUND_3: "3rd Round",
    Stage.CODING_CHALLENGE: "Coding\nChallenge",
    Stage.REJECTED: "Rejected",
    Stage.OFFER: "Offer",
}

LABEL_MAX_LENGTH = 30
TITLE_STYLE = {"fontsize": 11, "color": INK_PRIMARY, "loc": "left"}


def categorical_style(index: int) -> tuple[str, str]:
    """(color, hatch) of the `index`-th entry in a categorical series."""
    color = CATEGORICAL[index % len(CATEGORICAL)]
    hatch = HATCHES[(index // len(CATEGORICAL)) % len(HATCHES)]
    return color, hatch


def new_figure(width: float = 8.5, height: float = 4.6) -> tuple[Figure, Axes]:
    figure = Figure(figsize=(width, height), dpi=100, facecolor=SURFACE)
    axes = figure.add_subplot(111)
    axes.set_facecolor(SURFACE)
    return figure, axes


def show_empty_message(axes: Axes, message: str) -> None:
    axes.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        fontsize=10,
        color=INK_MUTED,
        transform=axes.transAxes,
    )
    axes.axis("off")


def style_bar_axes(axes: Axes, value_axis: str = "y") -> None:
    """Light grid along the value axis; only the left and bottom spines."""
    axes.grid(axis=value_axis, color=GRIDLINE, linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    for name, spine in axes.spines.items():
        spine.set_visible(name in ("left", "bottom"))
        spine.set_color(BASELINE)
    axes.tick_params(colors=INK_MUTED, length=0)


def truncate(label: str, max_length: int = LABEL_MAX_LENGTH) -> str:
    if len(label) <= max_length:
        return label
    return label[: max_length - 1] + "…"


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """ "1 offer", "2 offers", "3 companies" (with an explicit plural)."""
    word = singular if count == 1 else (plural_form or singular + "s")
    return f"{count} {word}"


@dataclass(frozen=True)
class HoverTarget:
    """A chart element and the tooltip it shows under the mouse."""

    artist: Artist
    tooltip: str


def attach_hover(
    figure: Figure, axes: Axes, targets: Sequence[HoverTarget]
) -> None:
    """Show the tooltip of the first target under the mouse; earlier
    targets win where they overlap."""
    tooltip = axes.annotate(
        "",
        xy=(0, 0),
        xytext=(12, 12),
        textcoords="offset points",
        fontsize=8,
        color=INK_PRIMARY,
        zorder=10,
        bbox={"boxstyle": "round,pad=0.4", "fc": SURFACE, "ec": BASELINE},
    )
    tooltip.set_visible(False)

    def on_mouse_move(event) -> None:
        hovered = None
        if event.inaxes is axes:
            hovered = next(
                (t for t in targets if t.artist.contains(event)[0]), None
            )
        if hovered is None:
            if tooltip.get_visible():
                tooltip.set_visible(False)
                figure.canvas.draw_idle()
            return
        tooltip.set_text(hovered.tooltip)
        tooltip.xy = (event.xdata, event.ydata)
        # Flip the tooltip left of the cursor on the right half of the plot.
        on_right_half = event.x > axes.bbox.x0 + axes.bbox.width / 2
        tooltip.set_position((-12, 12) if on_right_half else (12, 12))
        tooltip.set_horizontalalignment("right" if on_right_half else "left")
        tooltip.set_visible(True)
        figure.canvas.draw_idle()

    figure.canvas.mpl_connect("motion_notify_event", on_mouse_move)
