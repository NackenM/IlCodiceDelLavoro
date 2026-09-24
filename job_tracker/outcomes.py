"""Classify each application into exactly one outcome, for the summary charts."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pandas as pd

from . import storage

# An application with no reply at all counts as ghosted once it is this old;
# younger ones are still "awaiting reply".
GHOSTED_AFTER_DAYS = 30

OFFER = "Offer"
IN_PROGRESS = "In progress"
REJECTED_LATER = "Rejected after a stage"
REJECTED_EARLY = "Rejected right away"
GHOSTED = "Ghosted"
AWAITING = "Awaiting reply"

# Mutually exclusive, ordered for display.
OUTCOME_ORDER = [OFFER, IN_PROGRESS, REJECTED_LATER, REJECTED_EARLY, GHOSTED, AWAITING]

# Each success-rate target is a union of outcomes, measured against all
# applications in the selected time range.
TARGETS = {
    "Offer": {OFFER},
    "Interview or coding challenge": {OFFER, IN_PROGRESS, REJECTED_LATER},
    "Any reply (not ghosted)": {OFFER, IN_PROGRESS, REJECTED_LATER, REJECTED_EARLY},
    "Rejection": {REJECTED_LATER, REJECTED_EARLY},
    "Ghosted": {GHOSTED},
}

TIME_RANGES = {
    "All time": None,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "Last 12 months": 365,
}


def _has_date(row: pd.Series, status: str) -> bool:
    return str(row[storage.STATUS_DATE_COLUMNS[status]]).strip() != ""


def furthest_stage(row: pd.Series) -> int:
    """Index into FUNNEL_ORDER of the furthest stage reached (-1 if none).

    Uses both the stage dates and the current status, since the status can be
    changed without filling in the matching date.
    """
    reached = [i for i, s in enumerate(storage.FUNNEL_ORDER) if _has_date(row, s)]
    if row["status"] in storage.FUNNEL_ORDER:
        reached.append(storage.FUNNEL_ORDER.index(row["status"]))
    return max(reached, default=-1)


def classify(row: pd.Series, today: date | None = None) -> str:
    today = today or date.today()
    stage = furthest_stage(row)
    if stage == storage.FUNNEL_ORDER.index(storage.STATUS_OFFER):
        return OFFER
    rejected = _has_date(row, storage.STATUS_REJECTED) or row["status"] == storage.STATUS_REJECTED
    if rejected:
        return REJECTED_LATER if stage > 0 else REJECTED_EARLY
    if stage > 0:
        return IN_PROGRESS
    try:
        applied = date.fromisoformat(row["date_applied"])
    except ValueError:
        return AWAITING  # no usable date -- can't call it ghosted
    return GHOSTED if (today - applied).days >= GHOSTED_AFTER_DAYS else AWAITING


def rejection_stage(row: pd.Series) -> str:
    """The last stage an application reached before it was rejected."""
    return storage.FUNNEL_ORDER[max(furthest_stage(row), 0)]


def count_outcomes(df: pd.DataFrame, today: date | None = None) -> Counter:
    return Counter(classify(row, today) for _, row in df.iterrows())


def filter_by_time_range(df: pd.DataFrame, days: int | None, today: date | None = None) -> pd.DataFrame:
    """Keep applications whose applied date falls within the last `days` days."""
    if days is None:
        return df
    cutoff = ((today or date.today()) - timedelta(days=days)).isoformat()
    # ISO dates compare correctly as strings; blank dates drop out.
    return df[(df["date_applied"] != "") & (df["date_applied"] >= cutoff)]


NO_COMPANY = "(no company)"


def company_key(name: str) -> str:
    """Grouping key, so "ACME GmbH" and " acme  gmbh" count as one company."""
    return " ".join(name.split()).casefold()


def group_by_company(df: pd.DataFrame, today: date | None = None) -> list[tuple[str, list[tuple[pd.Series, str]]]]:
    """(company, [(row, outcome), ...]) pairs, most applications first.

    The display name is the spelling used on the first application to that
    company; applications without a company are grouped last.
    """
    groups: dict[str, tuple[str, list]] = {}
    for _, row in df.iterrows():
        key = company_key(row["company"])
        name = " ".join(row["company"].split()) or NO_COMPANY
        groups.setdefault(key, (name, []))[1].append((row, classify(row, today)))
    return sorted(groups.values(), key=lambda g: (g[0] == NO_COMPANY, -len(g[1]), g[0].casefold()))


def known_companies(df: pd.DataFrame) -> list[str]:
    """Each company once, in the spelling used by `group_by_company`, A-Z."""
    names: dict[str, str] = {}
    for company in df["company"]:
        if company.strip():
            names.setdefault(company_key(company), " ".join(company.split()))
    return sorted(names.values(), key=str.casefold)
