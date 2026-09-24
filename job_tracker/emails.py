"""Validation of the contact email field."""

from __future__ import annotations

import re

_EMAIL_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SEPARATORS = re.compile(r"[,;\s]+")


class InvalidEmailError(ValueError):
    def __init__(self, address: str):
        super().__init__(f"'{address}' is not a valid email address.")
        self.address = address


def normalize_email_list(raw: str) -> str:
    """Split on commas, semicolons and whitespace and re-join as
    "a@x.com, b@y.com".

    Raises InvalidEmailError for the first address that doesn't look like
    an email.
    """
    addresses = [part for part in _SEPARATORS.split(raw) if part]
    for address in addresses:
        if not _EMAIL_ADDRESS.match(address):
            raise InvalidEmailError(address)
    return ", ".join(addresses)
