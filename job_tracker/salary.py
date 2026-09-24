"""Reading an amount out of a free-text salary, for sorting."""

from __future__ import annotations

import re

# "65.000", "65,000" and "65 000" (thousands separators) ...
_THOUSANDS_GROUPED = r"\d{1,3}(?:[.,\s]\d{3})+"
# ... or a plain / decimal number like "65" or "72.5".
_PLAIN_NUMBER = r"\d+(?:[.,]\d+)?"
_FIRST_NUMBER = re.compile(f"{_THOUSANDS_GROUPED}|{_PLAIN_NUMBER}")


def parse_salary_amount(text: str) -> float | None:
    """First amount in a free-text salary, e.g. "65-75k €" -> 65000 and
    "€70.000 / year" -> 70000; None when there is no number.

    The period (monthly / yearly) is not interpreted.
    """
    match = _FIRST_NUMBER.search(text)
    if not match:
        return None
    number = match.group()
    if re.fullmatch(_THOUSANDS_GROUPED, number):
        amount = float(re.sub(r"[.,\s]", "", number))
    else:
        amount = float(number.replace(",", "."))
    if amount < 1000 and "k" in text.lower():
        amount *= 1000
    return amount
