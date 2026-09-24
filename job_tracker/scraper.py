"""Best-effort extraction of a job title & description from a posting URL.

This is a heuristic parse of arbitrary third-party HTML, so results are
always shown to the user for review/editing before being saved -- never
trust it as ground truth.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; JobApplicationTracker/1.0)"

DESCRIPTION_SELECTORS = [
    '[class*="job-description"]',
    '[class*="jobDescription"]',
    '[id*="job-description"]',
    '[id*="jobDescription"]',
    '[class*="job-details"]',
    "article",
    "main",
]


def fetch_and_parse(url: str, timeout: int = 15) -> dict:
    """Fetch `url` and return a best-effort {title, description, url}."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    elif soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)

    description = ""
    for selector in DESCRIPTION_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) > 200:
                description = text
                break

    if not description:
        body = soup.find("body")
        description = body.get_text("\n", strip=True) if body else ""

    return {"title": title, "description": description, "url": url}
