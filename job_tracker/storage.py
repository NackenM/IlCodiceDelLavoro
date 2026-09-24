"""CSV-backed storage for job applications."""
from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "applications.csv"

STATUS_APPLIED = "Applied"
STATUS_ONLINE_ASSESSMENT = "Online Assessment"
STATUS_ROUND_1 = "Interview - 1st Round"
STATUS_ROUND_2 = "Interview - 2nd Round"
STATUS_ROUND_3 = "Interview - 3rd Round"
STATUS_CODING_CHALLENGE = "Coding Challenge"
STATUS_REJECTED = "Rejected"
STATUS_OFFER = "Offer"

# Dropdown / sort order. Coding Challenge is listed after the 1st round,
# where it usually happens, but it is optional and can follow any round.
STATUS_CHOICES = [
    STATUS_APPLIED,
    STATUS_ONLINE_ASSESSMENT,
    STATUS_ROUND_1,
    STATUS_CODING_CHALLENGE,
    STATUS_ROUND_2,
    STATUS_ROUND_3,
    STATUS_REJECTED,
    STATUS_OFFER,
]

# Each status has a corresponding date column, so the date a stage was
# reached is recorded even if the application later moves past it.
STATUS_DATE_COLUMNS = {
    STATUS_APPLIED: "date_applied",
    STATUS_ONLINE_ASSESSMENT: "date_online_assessment",
    STATUS_ROUND_1: "date_round_1",
    STATUS_ROUND_2: "date_round_2",
    STATUS_ROUND_3: "date_round_3",
    STATUS_CODING_CHALLENGE: "date_coding_challenge",
    STATUS_REJECTED: "date_rejected",
    STATUS_OFFER: "date_offer",
}

# Forward pipeline order for the charts. Coding Challenge (optional, between
# rounds) and Rejected (an exit reachable from any stage) are side stages
# outside the sequence, so skipping them never looks like a stalled pipeline.
FUNNEL_ORDER = [
    STATUS_APPLIED,
    STATUS_ONLINE_ASSESSMENT,
    STATUS_ROUND_1,
    STATUS_ROUND_2,
    STATUS_ROUND_3,
    STATUS_OFFER,
]
ROUNDS = [STATUS_ROUND_1, STATUS_ROUND_2, STATUS_ROUND_3]

# Each interview round is tagged with a format and a focus, abbreviated to a
# letter in the list ("Interview - 2nd Round · V T").
ROUND_FORMATS = {"On-site": "O", "Virtual": "V", "Phone": "P"}
ROUND_FOCUSES = {"Technical": "T", "HR": "H", "Hiring manager": "M"}
# A round without a format set counts as virtual.
DEFAULT_ROUND_FORMAT = "Virtual"
ROUND_TAG_COLUMNS = {
    STATUS_ROUND_1: ("round_1_format", "round_1_focus"),
    STATUS_ROUND_2: ("round_2_format", "round_2_focus"),
    STATUS_ROUND_3: ("round_3_format", "round_3_focus"),
}

COLUMNS = [
    "id",
    "job_title",
    "company",
    "contact_email",
    "url",
    "job_description",
    "salary",
    "status",
    "notes",
    "last_update",
    *STATUS_DATE_COLUMNS.values(),
    *(col for pair in ROUND_TAG_COLUMNS.values() for col in pair),
]

# First amount in a free-text salary: "65.000", "65,000", "65 000", "72.5k".
_SALARY_NUMBER_RE = re.compile(r"\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d+)?")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_emails(raw: str) -> str:
    """Split on commas/semicolons/whitespace and re-join as "a@x.com, b@y.com".

    Raises ValueError naming the first address that doesn't look like an email.
    """
    addresses = [a for a in re.split(r"[,;\s]+", raw) if a]
    for address in addresses:
        if not _EMAIL_RE.match(address):
            raise ValueError(address)
    return ", ".join(addresses)


def salary_amount(text: str) -> float | None:
    """First amount in a free-text salary, for sorting, e.g. "65-75k €" ->
    65000, "€70.000 / year" -> 70000; None if there is no number. The period
    (monthly / yearly) is not interpreted."""
    match = _SALARY_NUMBER_RE.search(text)
    if not match:
        return None
    number = match.group()
    if re.fullmatch(r"\d{1,3}(?:[.,\s]\d{3})+", number):
        amount = float(re.sub(r"[.,\s]", "", number))  # thousands separators
    else:
        amount = float(number.replace(",", "."))
    if amount < 1000 and "k" in text.lower():
        amount *= 1000
    return amount


def round_format(row, round_status: str) -> str:
    """The round's format, falling back to DEFAULT_ROUND_FORMAT when unset."""
    return row[ROUND_TAG_COLUMNS[round_status][0]] or DEFAULT_ROUND_FORMAT


def round_tags(row, round_status: str) -> list[str]:
    """[format, focus] of an interview round; the focus only when set."""
    focus = row[ROUND_TAG_COLUMNS[round_status][1]]
    return [round_format(row, round_status), *([focus] if focus else [])]


def round_tag_letters(row, round_status: str) -> str:
    """Format + focus letters of an interview round, e.g. "V T"."""
    format_letter = ROUND_FORMATS.get(round_format(row, round_status), "")
    focus_letter = ROUND_FOCUSES.get(row[ROUND_TAG_COLUMNS[round_status][1]], "")
    return " ".join(letter for letter in (format_letter, focus_letter) if letter)


def coding_challenge_position(row) -> str:
    """Where the (optional) coding challenge fell, from the dates: "after 1st
    Round", "before 1st Round", or "" without a coding challenge date."""
    when = row[STATUS_DATE_COLUMNS[STATUS_CODING_CHALLENGE]]
    if not when:
        return ""
    # ISO dates compare correctly as strings; same-day counts as "after".
    before = [r for r in ROUNDS if row[STATUS_DATE_COLUMNS[r]] and row[STATUS_DATE_COLUMNS[r]] <= when]
    if not before:
        return "before 1st Round"
    return "after " + before[-1].removeprefix("Interview - ")


def status_label(row) -> str:
    """Status as shown in the list: rounds carry their tag letters, the
    coding challenge where it happened."""
    status = row["status"]
    if status in ROUND_TAG_COLUMNS and (letters := round_tag_letters(row, status)):
        return f"{status} \u00b7 {letters}"
    if status == STATUS_CODING_CHALLENGE and (position := coding_challenge_position(row)):
        return f"{status} ({position})"
    return status


def ensure_csv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        pd.DataFrame(columns=COLUMNS).to_csv(CSV_PATH, index=False)


# Interview stages before the 1st/2nd/3rd-round layout, oldest first:
# (status, date column, format implied by the stage name).
_LEGACY_INTERVIEWS = [
    ("Interview - Initial", "date_interview_initial", ""),
    ("Interview - Virtual", "date_interview_virtual", "Virtual"),
    ("Interview - 2nd Round", "date_interview_2nd", ""),
    ("Interview - 3rd Round", "date_interview_3rd", ""),
    ("Interview - On-site", "date_interview_onsite", "On-site"),
]


def _migrate_legacy_interviews(df: pd.DataFrame) -> pd.DataFrame:
    """Move the old interview stages into rounds 1-3 in date order, keeping
    the format the old stage name implied. Dates beyond a 3rd round are kept
    in the notes rather than dropped."""
    df = df.copy()
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for idx, row in df.iterrows():
        held = sorted(
            (row[col], order, status, fmt)
            for order, (status, col, fmt) in enumerate(_LEGACY_INTERVIEWS)
            if col in df.columns and row[col].strip()
        )
        new_status_for = {}
        for (when, _, status, fmt), round_status in zip(held, ROUNDS):
            df.at[idx, STATUS_DATE_COLUMNS[round_status]] = when
            df.at[idx, ROUND_TAG_COLUMNS[round_status][0]] = fmt
            new_status_for[status] = round_status
        if len(held) > len(ROUNDS):
            extra = ", ".join(f"{status} {when}" for when, _, status, _ in held[len(ROUNDS):])
            df.at[idx, "notes"] = " | ".join(p for p in (row["notes"], f"Further interviews: {extra}") if p)

        status = row["status"]
        if status in dict((s, c) for s, c, _ in _LEGACY_INTERVIEWS):
            # The old stage without a date maps to the furthest round reached.
            latest = ROUNDS[min(len(held), len(ROUNDS)) - 1] if held else STATUS_ROUND_1
            df.at[idx, "status"] = new_status_for.get(status, latest)
    return df


def load_applications() -> pd.DataFrame:
    ensure_csv()
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    if any(col in df.columns for _, col, _ in _LEGACY_INTERVIEWS):
        # One-time upgrade of the file; the original is kept next to it.
        backup = CSV_PATH.with_name(f"{CSV_PATH.stem}.before-rounds.csv")
        if not backup.exists():
            backup.write_bytes(CSV_PATH.read_bytes())
        df = _migrate_legacy_interviews(df)
        save_all(df)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS].copy()


def save_all(df: pd.DataFrame) -> None:
    ensure_csv()
    df[COLUMNS].to_csv(CSV_PATH, index=False)


def add_application(record: dict) -> str:
    df = load_applications()
    new_id = str(uuid.uuid4())[:8]
    row = {col: record.get(col, "") for col in COLUMNS}
    row["id"] = new_id
    row["last_update"] = date.today().isoformat()
    df.loc[len(df)] = row
    save_all(df)
    return new_id


def update_application(app_id: str, updates: dict) -> None:
    df = load_applications()
    idx = df.index[df["id"] == app_id]
    if len(idx) == 0:
        raise ValueError(f"No application with id {app_id}")
    for key, value in updates.items():
        df.loc[idx, key] = value
    df.loc[idx, "last_update"] = date.today().isoformat()
    save_all(df)


def delete_application(app_id: str) -> None:
    df = load_applications()
    df = df[df["id"] != app_id]
    save_all(df)
