"""Grouping applications by the company they were sent to."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from .model import NO_COMPANY, Application
from .outcomes import Outcome, group_by_outcome


def company_key(name: str) -> str:
    """Grouping key, so "ACME GmbH" and " acme  gmbh" are one company."""
    return " ".join(name.split()).casefold()


@dataclass
class CompanyGroup:
    """All applications to one company, under the spelling used first."""

    name: str
    applications: list[Application] = field(default_factory=list)

    @property
    def has_company(self) -> bool:
        return self.name != NO_COMPANY

    @property
    def size(self) -> int:
        return len(self.applications)

    def by_outcome(
        self, today: date | None = None
    ) -> dict[Outcome, list[Application]]:
        return group_by_outcome(self.applications, today)


def group_by_company(
    applications: Iterable[Application],
) -> list[CompanyGroup]:
    """Most-applied-to companies first; applications without a company are
    grouped last."""
    groups: dict[str, CompanyGroup] = {}
    for application in applications:
        key = company_key(application.company)
        group = groups.setdefault(
            key, CompanyGroup(application.company_display_name)
        )
        group.applications.append(application)
    return sorted(
        groups.values(),
        key=lambda group: (
            not group.has_company,
            -group.size,
            group.name.casefold(),
        ),
    )


def known_companies(applications: Iterable[Application]) -> list[str]:
    """Each company once, in the spelling `group_by_company` uses, A-Z."""
    return sorted(
        (
            group.name
            for group in group_by_company(applications)
            if group.has_company
        ),
        key=str.casefold,
    )
