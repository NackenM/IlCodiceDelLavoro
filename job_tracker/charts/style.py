"""Shared look of all charts: palette, axes styling, hover tooltips."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.transforms import Bbox
from PIL.Image import Image

from ..model import Application
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
    Stage.GHOSTED: "Ghosted",
    Stage.OFFER: "Offer",
}

LABEL_MAX_LENGTH = 30
HIGHLIGHT_NAME_MAX_LENGTH = 60
# Text sizes, in points. The Tk canvas shows charts at standard resolution,
# so on a Retina display they are scaled up and soften; nothing is set
# smaller than TEXT_SMALL to keep them readable there.
TEXT_SMALL = 9  # legends, tooltips, labels on the plot
TEXT_BODY = 10  # tick and axis labels, bar values
TEXT_TITLE = 12
TITLE_STYLE = {"fontsize": TEXT_TITLE, "color": INK_PRIMARY, "loc": "left"}
# Tooltips list at most this many entries; the rest are counted.
TOOLTIP_MAX_ENTRIES = 12

# An application picked out in a chart: everything else is drawn this
# faint, and its own part outlined.
DIMMED_ALPHA = 0.25
HIGHLIGHT_EDGE_WIDTH = 2

# A company name -> its logo tile (see `job_tracker.logos`).
LogoLookup = Callable[[str], Image]
# Row logos are this many points square, this far left of the plot.
ROW_LOGO_POINTS = 18
ROW_LOGO_GAP_POINTS = 8


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
        fontsize=TEXT_BODY,
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
    axes.tick_params(colors=INK_SECONDARY, labelsize=TEXT_BODY, length=0)


def truncate(label: str, max_length: int = LABEL_MAX_LENGTH) -> str:
    if len(label) <= max_length:
        return label
    return label[: max_length - 1] + "…"


def draw_subtitle(axes: Axes, text: str) -> None:
    """A line under the title (which needs pad=22 to make room). Left out
    of the layout, so a long one can't squeeze the plot to fit it."""
    subtitle = axes.text(
        0,
        1.02,
        text,
        transform=axes.transAxes,
        fontsize=TEXT_SMALL,
        color=INK_SECONDARY,
        va="bottom",
    )
    subtitle.set_in_layout(False)


def highlight_subtitle(application: Application, where: str) -> str:
    """ "■ Company · Job title  →  where it is", the name shortened to fit
    above the plot."""
    name = truncate(application.display_name, HIGHLIGHT_NAME_MAX_LENGTH)
    return f"■ {name}  →  {where}"


def row_label_pad(base_pad: float, logos: LogoLookup | None) -> float:
    """Tick label pad that leaves room for `add_row_logos`."""
    if logos is None:
        return base_pad
    return base_pad + ROW_LOGO_POINTS + ROW_LOGO_GAP_POINTS


def add_row_logos(
    axes: Axes, rows: Sequence[tuple[float, str]], logos: LogoLookup
) -> None:
    """The logo of each (y, company) row between its tick label and the
    plot; the labels need `row_label_pad` to make room."""
    for y, company in rows:
        tile = logos(company)
        axes.add_artist(
            AnnotationBbox(
                OffsetImage(tile, zoom=ROW_LOGO_POINTS / tile.width),
                (0, y),
                xycoords=("axes fraction", "data"),
                xybox=(-ROW_LOGO_GAP_POINTS, 0),
                boxcoords="offset points",
                box_alignment=(1, 0.5),
                frameon=False,
                pad=0,
                annotation_clip=False,
            )
        )


def bullet_list(
    entries: Sequence[str], max_entries: int = TOOLTIP_MAX_ENTRIES
) -> str:
    """One "• entry" line each; past `max_entries` the rest are summed up
    in a closing "… and N more" line."""
    lines = [f"• {entry}" for entry in entries[:max_entries]]
    if len(entries) > max_entries:
        lines.append(f"… and {len(entries) - max_entries} more")
    return "\n".join(lines)


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
    targets win where they overlap.

    Moving the tooltip only repaints the area it covered and now covers,
    on top of a copy of the chart taken after every full draw, so it stays
    quick on charts too large to redraw at mouse speed."""
    tooltip = axes.annotate(
        "",
        xy=(0, 0),
        xytext=(12, 12),
        textcoords="offset points",
        fontsize=TEXT_SMALL,
        color=INK_PRIMARY,
        zorder=10,
        bbox={"boxstyle": "round,pad=0.4", "fc": SURFACE, "ec": BASELINE},
        animated=True,  # left out of full draws, painted by `repaint`
    )
    tooltip.set_visible(False)
    background = None
    shown_area: Bbox | None = None  # where the tooltip is painted now

    def repaint() -> None:
        nonlocal shown_area
        canvas = figure.canvas
        dirty = []
        if shown_area is not None:
            # Restoring the whole copy is a quick memory copy; only the
            # dirty area is handed on to the screen.
            canvas.restore_region(background)
            dirty.append(shown_area)
            shown_area = None
        if tooltip.get_visible():
            axes.draw_artist(tooltip)
            shown_area = Bbox.intersection(
                Bbox.union(
                    [
                        tooltip.get_window_extent(),
                        tooltip.get_bbox_patch().get_window_extent(),
                    ]
                ).padded(2),
                figure.bbox,
            )
            if shown_area is not None:
                dirty.append(shown_area)
        if dirty:
            canvas.blit(Bbox.union(dirty))

    def on_draw(_event) -> None:
        nonlocal background, shown_area
        background = figure.canvas.copy_from_bbox(figure.bbox)
        shown_area = None
        if tooltip.get_visible():
            repaint()

    def on_mouse_move(event) -> None:
        hovered = None
        if event.inaxes is axes:
            hovered = next(
                (t for t in targets if t.artist.contains(event)[0]), None
            )
        if hovered is None:
            if tooltip.get_visible():
                tooltip.set_visible(False)
                if background is not None:
                    repaint()
            return
        tooltip.set_text(hovered.tooltip)
        tooltip.xy = (event.xdata, event.ydata)
        # Flip the tooltip left of the cursor on the right half of the plot.
        on_right_half = event.x > axes.bbox.x0 + axes.bbox.width / 2
        tooltip.set_position((-12, 12) if on_right_half else (12, 12))
        tooltip.set_horizontalalignment("right" if on_right_half else "left")
        tooltip.set_visible(True)
        if background is None:  # not drawn yet
            figure.canvas.draw_idle()
        else:
            repaint()

    figure.canvas.mpl_connect("draw_event", on_draw)
    figure.canvas.mpl_connect("motion_notify_event", on_mouse_move)
