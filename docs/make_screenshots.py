"""Take the README screenshots: `python docs/make_screenshots.py [OUT_DIR]`.

Opens the app on the bundled example data, shows each window and view in
turn and captures it, title bar included, into OUT_DIR (docs/screenshots by
default). macOS only, as it uses `screencapture`; the terminal running it
needs the Screen Recording permission. Keep the mouse out of the way, as
the windows open on the left of the screen.

The windows are drawn in the light appearance, whatever the system uses,
and logos are left as initials tiles: the example companies are made up,
and a web lookup could find a real company of the same name.
"""

from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

import click
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # run as a script, not as a module

import job_tracker.gui.logo_store as logo_store  # noqa: E402
from job_tracker.gui.add_dialog import AddApplicationDialog  # noqa: E402
from job_tracker.gui.edit_dialog import EditApplicationDialog  # noqa: E402
from job_tracker.gui.main_window import MainWindow  # noqa: E402
from job_tracker.gui.stats_dialog import (  # noqa: E402
    CALENDAR_VIEW,
    StatisticsDialog,
)
from job_tracker.gui.timeline_dialog import TimelineDialog  # noqa: E402
from job_tracker.repository import (  # noqa: E402
    DEFAULT_CSV_PATH,
    ApplicationRepository,
)

DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "screenshots"
# The application highlighted in the main window, the one opened for
# editing, and a mix for the timeline: offers, a rejection, still open and
# ghosted.
HIGHLIGHTED = "Vertex Systems · Platform Engineer"
EDITED = "Acme Robotics · Backend Engineer"
TIMELINE = [
    "Acme Robotics · Backend Engineer",
    "Beacon Insights · Data Analyst",
    "Vertex Systems · Platform Engineer",
    "Lumen Softworks · Frontend Engineer",
    "Helios AI · MLOps Engineer",
    "Evergreen Energy · Data Platform Engineer",
    "Helios AI · Research Engineer",
    "Brightpath Health · Full-Stack Developer",
]
STATISTICS_VIEWS = [
    ("Success rate", "statistics-success-rate.png"),
    ("By company", "statistics-by-company.png"),
    ("Company share", "statistics-company-share.png"),
    ("Reply times", "statistics-reply-times.png"),
]


def light(window: tk.Misc) -> None:
    window.update_idletasks()  # Tk needs the window made first
    window.tk.call(
        "::tk::unsupported::MacWindowStyle", "appearance", window, "aqua"
    )


def settle(window: tk.Misc, seconds: float = 0.6) -> None:
    window.update()
    time.sleep(seconds)
    window.update()


def shot(window: tk.Misc, path: Path) -> None:
    """The window with its title bar, at one pixel per point (a Retina
    capture is scaled down), so the images match in size."""
    window.lift()
    window.focus_force()
    settle(window)
    x, y = window.winfo_x(), window.winfo_y()
    width = window.winfo_width()
    height = window.winfo_height() + window.winfo_rooty() - y
    subprocess.run(
        ["screencapture", "-x", "-R", f"{x},{y},{width},{height}", str(path)],
        check=True,
    )
    image = Image.open(path)
    if image.width != width:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    image.save(path, optimize=True)
    click.echo(f"{path.name}: {width}x{height}")


def find_child(window: tk.Misc, kind: type) -> tk.Misc:
    return next(c for c in window.winfo_children() if isinstance(c, kind))


def take_screenshots(out_dir: Path) -> None:
    main = MainWindow(ApplicationRepository(DEFAULT_CSV_PATH))
    light(main)
    main.geometry("1340x800+60+60")
    settle(main, 1.0)
    applications = {a.display_name: a for a in main.applications}

    # Main window: the waterfall, an application highlighted in it, and
    # the progress chart.
    shot(main, out_dir / "main-window.png")
    main.application_list.tree.selection_set(applications[HIGHLIGHTED].id)
    settle(main, 0.5)
    shot(main, out_dir / "main-highlight.png")
    main.application_list.tree.selection_set([])
    main.chart_view.set("Progress by application")
    main._show_chart()
    shot(main, out_dir / "main-progress.png")

    add = AddApplicationDialog(
        main, main.repository, [], on_saved=lambda: None
    )
    light(add)
    add.geometry("+90+70")
    shot(add, out_dir / "add-application.png")
    add.destroy()

    main._open_edit_dialog(applications[EDITED])
    edit = find_child(main, EditApplicationDialog)
    light(edit)
    edit.geometry("+90+40")
    shot(edit, out_dir / "edit-application.png")
    edit.destroy()

    stats = StatisticsDialog(main, main.applications, main.logos)
    light(stats)
    stats.geometry("860x640+90+70")
    for view, name in STATISTICS_VIEWS:
        stats.view.set(view)
        stats._redraw()
        shot(stats, out_dir / name)
    stats.view.set(CALENDAR_VIEW)
    stats.activity_kind.set("All stage dates")
    stats._redraw()
    shot(stats, out_dir / "statistics-calendar.png")
    stats.destroy()

    timeline = TimelineDialog(
        main, [applications[name] for name in TIMELINE], main.logos
    )
    light(timeline)
    timeline.geometry("+90+40")
    shot(timeline, out_dir / "timeline.png")
    timeline.destroy()
    main.destroy()


@click.command()
@click.argument(
    "out_dir",
    required=False,
    default=DEFAULT_OUT_DIR,
    type=click.Path(file_okay=False, path_type=Path),
)
def run(out_dir: Path) -> None:
    """Take the README screenshots into OUT_DIR (docs/screenshots)."""
    if sys.platform != "darwin":
        raise click.ClickException("Taking screenshots needs macOS.")
    out_dir.mkdir(parents=True, exist_ok=True)
    logo_store.find_logo = lambda *_: None  # initials only, no web lookups
    take_screenshots(out_dir)


if __name__ == "__main__":
    run()
