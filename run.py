"""Entry point: run with `python run.py [CSV_PATH]` (or
`.venv/bin/python run.py [CSV_PATH]`)."""

from pathlib import Path

import click

from job_tracker.gui.main_window import main
from job_tracker.repository import DEFAULT_CSV_PATH


@click.command()
@click.argument(
    "csv_path",
    required=False,
    default=DEFAULT_CSV_PATH,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
)
def run(csv_path: Path) -> None:
    """Open the job application tracker on CSV_PATH.

    Without CSV_PATH, the bundled example data in data/applications.csv is
    used. A file that does not exist yet is created with the first saved
    application.
    """
    main(csv_path)


if __name__ == "__main__":
    run()
