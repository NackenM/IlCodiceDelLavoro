"""Closing the app cleanly on Ctrl+C / kill (e.g. PyCharm's Stop or Rerun).

On macOS, Tk 9 installs a C signal handler that tears Tcl down from inside
the handler; the resulting <Destroy> callbacks re-enter Python without the
GIL and abort the interpreter. Re-registering Python handlers after Tk is
created replaces it, so the shutdown runs on the main thread instead.
"""

from __future__ import annotations

import signal
import tkinter as tk
from collections.abc import Iterator
from contextlib import contextmanager

STOP_SIGNALS = {
    getattr(signal, name)
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
    if hasattr(signal, name)
}
# mainloop only looks at pending Python signals between Tk events.
SIGNAL_CHECK_INTERVAL_MS = 200


@contextmanager
def stop_signals_held_back() -> Iterator[None]:
    """Block the stop signals while the window is built: until our handlers
    replace Tk's, a signal would hit Tk's handler mid-startup. A signal
    arriving meanwhile stays pending and is handled on leaving the block."""
    signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, STOP_SIGNALS)


def close_on_stop_signals(root: tk.Tk) -> None:
    for stop_signal in STOP_SIGNALS:
        signal.signal(stop_signal, lambda *_: root.destroy())

    # Keep a steady trickle of events coming while the app sits idle, so a
    # signal is noticed promptly.
    def heartbeat() -> None:
        root.after(SIGNAL_CHECK_INTERVAL_MS, heartbeat)

    heartbeat()
