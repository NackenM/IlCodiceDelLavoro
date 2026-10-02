"""Company logos from the web, without any API key or account.

A company's website comes from its contact email or job posting URL, or
else from Clearbit's public company autocomplete; the logo for that website
from Hunter's public logo service. Logos are turned into square tiles of
one look, and companies without a logo get a tile with their initials.
"""

from __future__ import annotations

import io
import re
import zlib
from collections.abc import Iterable, Sequence
from functools import cache
from typing import Protocol
from urllib.parse import urlparse

from matplotlib.font_manager import FontProperties, findfont
from PIL import Image, ImageDraw, ImageFont

from .charts.style import CATEGORICAL, GRIDLINE
from .model import Application

SUGGEST_URL = "https://autocomplete.clearbit.com/v1/companies/suggest"
LOGO_URL = "https://logos.hunter.io/{domain}"
REQUEST_TIMEOUT = 8  # seconds
USER_AGENT = "IlCodiceDelLavoro job tracker"

# Addresses at these domains say nothing about the company.
FREEMAIL_DOMAINS = frozenset(
    {
        "aol.com",
        "gmail.com",
        "gmx.at",
        "gmx.ch",
        "gmx.de",
        "gmx.net",
        "googlemail.com",
        "hotmail.com",
        "icloud.com",
        "live.com",
        "mail.de",
        "me.com",
        "outlook.com",
        "posteo.de",
        "proton.me",
        "protonmail.com",
        "t-online.de",
        "web.de",
        "yahoo.com",
        "yahoo.de",
    }
)
# Postings hosted here are on a job board or applicant tracking system,
# not on the company's own website.
JOB_BOARD_DOMAINS = frozenset(
    {
        "arbeitsagentur.de",
        "ashbyhq.com",
        "bamboohr.com",
        "glassdoor.com",
        "glassdoor.de",
        "greenhouse.io",
        "indeed.com",
        "join.com",
        "kununu.com",
        "lever.co",
        "linkedin.com",
        "monster.de",
        "myworkdayjobs.com",
        "personio.com",
        "personio.de",
        "recruitee.com",
        "smartrecruiters.com",
        "softgarden.io",
        "stepstone.de",
        "successfactors.com",
        "successfactors.eu",
        "teamtailor.com",
        "welcometothejungle.com",
        "wellfound.com",
        "workable.com",
        "workday.com",
        "xing.com",
        "ycombinator.com",
    }
)
# Words left out when comparing company names, so "Helsing AI" matches
# "Helsing" and "ACME GmbH" matches "Acme".
NAME_NOISE_WORDS = frozenset(
    {
        "ab",
        "ag",
        "ai",
        "bv",
        "co",
        "company",
        "corp",
        "corporation",
        "gmbh",
        "group",
        "holding",
        "holdings",
        "inc",
        "kg",
        "kgaa",
        "llc",
        "ltd",
        "limited",
        "nv",
        "plc",
        "sa",
        "sarl",
        "se",
        "spa",
        "the",
        "ug",
    }
)
# Second-level labels under which companies register, as in "acme.co.uk".
_SHARED_SECOND_LEVELS = frozenset({"ac", "co", "com", "gov", "net", "org"})
_EMAIL_SEPARATORS = re.compile(r"[,;\s]+")
_NON_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")

# Tiles are drawn this many pixels square, at 4x and scaled down for
# smooth corners.
TILE_SIZE = 64
_SUPERSAMPLE = 4
_CORNER_SHARE = 0.22
# The logo fills this share of its tile; the rest is a white margin.
_LOGO_SHARE = 0.78


# -- the company's website ---------------------------------------------------


def registrable_domain(host: str) -> str:
    """ "careers.acme.com" -> "acme.com", "jobs.acme.co.uk" ->
    "acme.co.uk"."""
    labels = host.lower().strip(".").split(".")
    keep = 2
    if (
        len(labels) >= 3
        and labels[-2] in _SHARED_SECOND_LEVELS
        and len(labels[-1]) == 2
    ):
        keep = 3
    return ".".join(labels[-keep:])


def domain_from_email(contact_email: str) -> str | None:
    """The first company domain among the contact addresses."""
    for address in _EMAIL_SEPARATORS.split(contact_email):
        if "@" not in address:
            continue
        domain = registrable_domain(address.rsplit("@", 1)[1])
        if domain not in FREEMAIL_DOMAINS:
            return domain
    return None


def domain_from_url(url: str) -> str | None:
    """The posting's domain, unless a job board hosts it."""
    host = urlparse(url.strip()).hostname
    if not host or "." not in host:
        return None
    domain = registrable_domain(host)
    return None if domain in JOB_BOARD_DOMAINS else domain


def candidate_domains(applications: Iterable[Application]) -> list[str]:
    """The company's domains found in its applications, email ones first
    (a posting may still sit on a recruiter's site), each once."""
    applications = list(applications)
    found = [domain_from_email(a.contact_email) for a in applications]
    found += [domain_from_url(a.url) for a in applications]
    return list(dict.fromkeys(domain for domain in found if domain))


def name_key(name: str) -> str:
    """The name reduced for comparing: lower case, words only, legal forms
    and other noise words left out."""
    words = _NON_ALPHANUMERIC.sub(" ", name.casefold()).split()
    return " ".join(word for word in words if word not in NAME_NOISE_WORDS)


def pick_suggestion(company: str, suggestions: Sequence[dict]) -> str | None:
    """The domain of the first suggestion with the same name, else of the
    first whose name starts with it as whole words ("Bosch" -> "Bosch
    Global", not "Helsing" -> "Helsingin Sanomat"). A near miss is no
    match: better no logo than another company's."""
    key = name_key(company)
    if not key:
        return None
    named = [
        (name_key(s.get("name", "")), s.get("domain")) for s in suggestions
    ]
    for matches in (
        lambda other: other == key,
        lambda other: other.startswith(key + " "),
    ):
        for other, domain in named:
            if domain and matches(other):
                return domain
    return None


# -- fetching ------------------------------------------------------------


class HttpSession(Protocol):
    """The part of `requests.Session` used here."""

    def get(self, url: str, **kwargs): ...


def suggest_domain(session: HttpSession, company: str) -> str | None:
    response = session.get(
        SUGGEST_URL,
        params={"query": company},
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    if response.status_code != 200:
        return None
    return pick_suggestion(company, response.json())


def fetch_logo(session: HttpSession, domain: str) -> bytes | None:
    """The logo image for `domain`; None where there is none (404)."""
    response = session.get(
        LOGO_URL.format(domain=domain),
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    content_type = response.headers.get("Content-Type", "")
    if response.status_code != 200 or not content_type.startswith("image/"):
        return None
    return response.content


def find_logo(
    session: HttpSession, company: str, applications: Iterable[Application]
) -> Image.Image | None:
    """The company's logo tile: tried at the domains its applications
    point to, then at the domain its name is known under."""
    tried = set()
    for domain in candidate_domains(applications):
        tried.add(domain)
        if data := fetch_logo(session, domain):
            return logo_tile(data)
    domain = suggest_domain(session, company)
    if (
        domain
        and domain not in tried
        and (data := fetch_logo(session, domain))
    ):
        return logo_tile(data)
    return None


# -- tiles -----------------------------------------------------------------


def _rounded_tile(color: str) -> Image.Image:
    """A blank rounded square at the supersampled size."""
    size = TILE_SIZE * _SUPERSAMPLE
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=round(size * _CORNER_SHARE),
        fill=color,
        outline=GRIDLINE,
        width=_SUPERSAMPLE,
    )
    return tile


def _finish(tile: Image.Image) -> Image.Image:
    return tile.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)


def logo_tile(data: bytes) -> Image.Image:
    """The logo centred on a white rounded square, keeping its shape."""
    logo = Image.open(io.BytesIO(data)).convert("RGBA")
    tile = _rounded_tile("white")
    inner = round(tile.width * _LOGO_SHARE)
    logo.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    if logo.width < inner and logo.height < inner:  # small: scale it up
        factor = inner / max(logo.size)
        logo = logo.resize(
            (round(logo.width * factor), round(logo.height * factor)),
            Image.Resampling.LANCZOS,
        )
    position = (
        (tile.width - logo.width) // 2,
        (tile.height - logo.height) // 2,
    )
    tile.alpha_composite(logo, position)
    return _finish(tile)


def initials(company: str) -> str:
    """Up to two capital letters, from the first words that aren't legal
    forms: "Acme Robotics GmbH" -> "AR"."""
    words = [
        word
        for word in re.split(r"[^\w]+", company)
        if word and word.casefold() not in NAME_NOISE_WORDS
    ] or company.split()
    return "".join(word[0] for word in words[:2]).upper()


@cache
def _initials_font() -> ImageFont.FreeTypeFont:
    path = findfont(FontProperties(family="DejaVu Sans", weight="bold"))
    return ImageFont.truetype(path, round(TILE_SIZE * _SUPERSAMPLE * 0.4))


def initials_tile(company: str) -> Image.Image:
    """The company's initials on a rounded square in a color of its own,
    the same on every run."""
    color = CATEGORICAL[
        zlib.crc32(company.casefold().encode()) % len(CATEGORICAL)
    ]
    tile = _rounded_tile(color)
    ImageDraw.Draw(tile).text(
        (tile.width / 2, tile.height / 2),
        initials(company),
        fill="white",
        font=_initials_font(),
        anchor="mm",
    )
    return _finish(tile)
