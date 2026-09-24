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
STATUS_CODING_CHALLENGE = "Coding Challenge"
STATUS_INTERVIEW_INITIAL = "Interview - Initial"
STATUS_INTERVIEW_VIRTUAL = "Interview - Virtual"
STATUS_INTERVIEW_2ND = "Interview - 2nd Round"
STATUS_INTERVIEW_3RD = "Interview - 3rd Round"
STATUS_INTERVIEW_ONSITE = "Interview - On-site"
STATUS_REJECTED = "Rejected"
STATUS_OFFER = "Offer"

STATUS_CHOICES = [
    STATUS_APPLIED,
    STATUS_CODING_CHALLENGE,
    STATUS_INTERVIEW_INITIAL,
    STATUS_INTERVIEW_VIRTUAL,
    STATUS_INTERVIEW_2ND,
    STATUS_INTERVIEW_3RD,
    STATUS_INTERVIEW_ONSITE,
    STATUS_REJECTED,
    STATUS_OFFER,
]

# Each status has a corresponding date column, so the date a stage was
# reached is recorded even if the application later moves past it.
STATUS_DATE_COLUMNS = {
    STATUS_APPLIED: "date_applied",
    STATUS_CODING_CHALLENGE: "date_coding_challenge",
    STATUS_INTERVIEW_INITIAL: "date_interview_initial",
    STATUS_INTERVIEW_VIRTUAL: "date_interview_virtual",
    STATUS_INTERVIEW_2ND: "date_interview_2nd",
    STATUS_INTERVIEW_3RD: "date_interview_3rd",
    STATUS_INTERVIEW_ONSITE: "date_interview_onsite",
    STATUS_REJECTED: "date_rejected",
    STATUS_OFFER: "date_offer",
}

# Forward pipeline order for the waterfall chart. Rejected is an exit state
# reachable from any stage, so it is excluded here and drawn as its own bar.
FUNNEL_ORDER = [s for s in STATUS_CHOICES if s != STATUS_REJECTED]

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


def ensure_csv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        pd.DataFrame(columns=COLUMNS).to_csv(CSV_PATH, index=False)


def load_applications() -> pd.DataFrame:
    ensure_csv()
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
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
