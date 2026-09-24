"""Best-effort extraction of a job title & description from a posting URL.

This is a heuristic parse of arbitrary third-party HTML, so results are
always shown to the user for review/editing before being saved -- never
trust it as ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; JobApplicationTracker/1.0)"

# Tried in order; the first match with enough text wins.
DESCRIPTION_SELECTORS = [
    '[class*="job-description"]',
    '[class*="jobDescription"]',
    '[id*="job-description"]',
    '[id*="jobDescription"]',
    '[class*="job-details"]',
    "article",
    "main",
]
# Shorter matches are usually navigation or teasers, not the description.
MIN_DESCRIPTION_LENGTH = 200


@dataclass(frozen=True)
class ParsedPosting:
    title: str
    description: str
    url: str


def fetch_posting(url: str, timeout_seconds: int = 15) -> ParsedPosting:
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=timeout_seconds
    )
    response.raise_for_status()
    return parse_posting_html(response.text, url)


def parse_posting_html(html: str, url: str) -> ParsedPosting:
    soup = BeautifulSoup(html, "lxml")
    return ParsedPosting(
        title=_find_title(soup),
        description=_find_description(soup),
        url=url,
    )


def _find_title(soup: BeautifulSoup) -> str:
    for node in (soup.find("h1"), soup.title):
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
    return ""


def _find_description(soup: BeautifulSoup) -> str:
    for selector in DESCRIPTION_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) > MIN_DESCRIPTION_LENGTH:
                return text
    body = soup.find("body")
    return body.get_text("\n", strip=True) if body else ""
