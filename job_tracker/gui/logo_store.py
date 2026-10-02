"""Company logos for the windows: fetched once per session in the
background, kept in memory only."""

from __future__ import annotations

import base64
import io
import queue
import threading
import time
import tkinter as tk
from collections.abc import Callable, Iterable

import requests
from PIL import Image

from ..companies import company_key, group_by_company
from ..logos import find_logo, initials_tile
from ..model import Application

WORKERS = 8
POLL_INTERVAL_MS = 150
# Listeners hear about newly arrived logos at most this often, and once
# more when the last one is in.
NOTIFY_INTERVAL_SECONDS = 0.6

_Job = tuple[str, str, list[Application]]  # key, company name, applications


class LogoStore:
    """Hands out each company's logo tile, or its initials until (or
    unless) a logo is found.

    `request` queues the companies not looked up yet; background threads
    fetch them, and the main thread picks the results up and tells the
    subscribers, so only it touches Tk.
    """

    def __init__(self, root: tk.Misc):
        self._root = root
        self._logos: dict[str, Image.Image | None] = {}  # None: none found
        self._initials: dict[str, Image.Image] = {}
        self._photos: dict[tuple[str, int, bool], tk.PhotoImage] = {}
        self._jobs: queue.Queue[_Job] = queue.Queue()
        self._results: queue.Queue[tuple[str, Image.Image | None]] = (
            queue.Queue()
        )
        self._pending = 0
        self._new_since_notify = False
        self._last_notify = 0.0
        # (listener, only once all requested logos are in)
        self._listeners: list[tuple[Callable[[], None], bool]] = []
        self._new_since_all_in = False
        self._polling = False
        for _ in range(WORKERS):
            # Daemon threads: closing the app never waits for a request.
            threading.Thread(target=self._work, daemon=True).start()

    # -- lookups ---------------------------------------------------------

    def request(self, applications: Iterable[Application]) -> None:
        """Start looking up the logos of companies not seen yet."""
        for group in group_by_company(applications):
            key = company_key(group.name)
            if not group.has_company or key in self._logos:
                continue
            self._logos[key] = None
            self._pending += 1
            self._jobs.put((key, group.name, group.applications))
        if self._pending and not self._polling:
            self._polling = True
            self._root.after(POLL_INTERVAL_MS, self._poll)

    def image(self, company: str) -> Image.Image:
        """The logo tile, or the initials tile while there is none."""
        key = company_key(company)
        logo = self._logos.get(key)
        if logo is not None:
            return logo
        if key not in self._initials:
            self._initials[key] = initials_tile(" ".join(company.split()))
        return self._initials[key]

    def photo(self, company: str, size: int) -> tk.PhotoImage:
        """`image` as a Tk image `size` pixels square, for widgets."""
        key = company_key(company)
        has_logo = self._logos.get(key) is not None
        cache_key = (key, size, has_logo)
        if cache_key not in self._photos:
            tile = self.image(company).resize(
                (size, size), Image.Resampling.LANCZOS
            )
            png = io.BytesIO()
            tile.save(png, format="PNG")
            self._photos[cache_key] = tk.PhotoImage(
                master=self._root,
                data=base64.b64encode(png.getvalue()),
                format="png",
            )
        return self._photos[cache_key]

    def subscribe(
        self, listener: Callable[[], None], once_all_in: bool = False
    ) -> Callable[[], None]:
        """Call `listener` as logos arrive, or with `once_all_in` only when
        the last one requested is in (for views slow to redraw); returns
        the unsubscribe."""
        entry = (listener, once_all_in)
        self._listeners.append(entry)
        return lambda: self._listeners.remove(entry)

    def subscribe_while(
        self,
        window: tk.Toplevel,
        listener: Callable[[], None],
        once_all_in: bool = False,
    ) -> None:
        """`subscribe` until `window` closes."""
        unsubscribe = self.subscribe(listener, once_all_in)

        def on_destroy(event: tk.Event) -> None:
            if event.widget is window:  # not one of its children
                unsubscribe()

        window.bind("<Destroy>", on_destroy, add="+")

    # -- background ------------------------------------------------------

    def _work(self) -> None:
        session = requests.Session()  # one per thread
        while True:
            key, company, applications = self._jobs.get()
            try:
                logo = find_logo(session, company, applications)
            except Exception:  # offline, timeout, odd image: keep initials
                logo = None
            self._results.put((key, logo))

    def _poll(self) -> None:
        while True:
            try:
                key, logo = self._results.get_nowait()
            except queue.Empty:
                break
            self._pending -= 1
            if logo is not None:
                self._logos[key] = logo
                self._new_since_notify = self._new_since_all_in = True
        now = time.monotonic()
        notify = self._new_since_notify and (
            not self._pending
            or now - self._last_notify >= NOTIFY_INTERVAL_SECONDS
        )
        notify_all_in = self._new_since_all_in and not self._pending
        if notify:
            self._new_since_notify = False
            self._last_notify = now
        if notify_all_in:
            self._new_since_all_in = False
        for listener, once_all_in in list(self._listeners):
            if notify_all_in if once_all_in else notify:
                listener()
        if self._pending:
            self._root.after(POLL_INTERVAL_MS, self._poll)
        else:
            self._polling = False
