"""Finding a company's website and logo, and the tiles shown for it. The
web is replaced by a fake session; nothing here goes online."""

import io

import pytest
from PIL import Image

from job_tracker.logos import (
    LOGO_URL,
    SUGGEST_URL,
    TILE_SIZE,
    candidate_domains,
    domain_from_email,
    domain_from_url,
    find_logo,
    initials,
    initials_tile,
    logo_tile,
    name_key,
    pick_suggestion,
    registrable_domain,
)

from .factories import make_application


def png_bytes(size=(40, 20), color="red"):
    data = io.BytesIO()
    Image.new("RGBA", size, color).save(data, format="PNG")
    return data.getvalue()


class FakeResponse:
    def __init__(self, status_code, content=b"", json_data=None):
        self.status_code = status_code
        self.content = content
        self._json = json_data
        self.headers = {
            "Content-Type": "image/png" if content else "application/json"
        }

    def json(self):
        return self._json


class FakeSession:
    """Logos for the domains in `logos`, `suggestions` for any name."""

    def __init__(self, logos=(), suggestions=()):
        self.logos = set(logos)
        self.suggestions = list(suggestions)
        self.requested = []

    def get(self, url, params=None, **kwargs):
        self.requested.append(params["query"] if params else url)
        if url == SUGGEST_URL:
            return FakeResponse(200, json_data=self.suggestions)
        for domain in self.logos:
            if url == LOGO_URL.format(domain=domain):
                return FakeResponse(200, content=png_bytes())
        return FakeResponse(404)


@pytest.mark.parametrize(
    ("host", "domain"),
    [
        ("careers.acme.com", "acme.com"),
        ("acme.com", "acme.com"),
        ("jobs.acme.co.uk", "acme.co.uk"),
        ("WWW.Acme.DE.", "acme.de"),
    ],
)
def test_registrable_domain(host, domain):
    assert registrable_domain(host) == domain


@pytest.mark.parametrize(
    ("contact_email", "domain"),
    [
        ("talent@careers.acme.com", "acme.com"),
        ("jane@gmail.com, hr@acme.de", "acme.de"),
        ("jane@gmail.com", None),
        ("", None),
    ],
)
def test_domain_from_email_skips_freemail(contact_email, domain):
    assert domain_from_email(contact_email) == domain


@pytest.mark.parametrize(
    ("url", "domain"),
    [
        ("https://jobs.acme.com/posting/42", "acme.com"),
        ("https://www.linkedin.com/jobs/view/1", None),
        ("https://acme.jobs.personio.de/job/7", None),
        ("https://boards.greenhouse.io/acme/jobs/1", None),
        ("not a url", None),
        ("", None),
    ],
)
def test_domain_from_url_skips_job_boards(url, domain):
    assert domain_from_url(url) == domain


def test_candidate_domains_put_email_first_and_list_each_once():
    applications = [
        make_application(url="https://jobs.acme.com/1"),
        make_application(contact_email="hr@acme-careers.de"),
        make_application(url="https://acme.com/2"),
    ]
    assert candidate_domains(applications) == ["acme-careers.de", "acme.com"]


def test_name_key_ignores_case_punctuation_and_legal_forms():
    assert name_key("ACME Robotics GmbH") == "acme robotics"
    assert name_key("Helsing AI") == name_key("Helsing")
    assert name_key("The Helsing Group") == "helsing"


# Recorded answers of the company autocomplete.
HELSING_SUGGESTIONS = [
    {"name": "Helsingin Sanomat", "domain": "hs.fi"},
    {"name": "Helsing", "domain": "helsing.ai"},
]
N26_SUGGESTIONS = [
    {"name": "Netflix", "domain": "netflix.com"},
    {"name": "Nike", "domain": "nike.com"},
]


BOSCH_SUGGESTIONS = [
    {"name": "Bosch Global", "domain": "bosch.com"},
    {"name": "Bosch Power Tools NA", "domain": "boschtools.com"},
]


def test_pick_suggestion_prefers_the_same_name():
    assert pick_suggestion("Helsing AI", HELSING_SUGGESTIONS) == "helsing.ai"


def test_pick_suggestion_then_takes_a_name_starting_with_it():
    assert pick_suggestion("Bosch", BOSCH_SUGGESTIONS) == "bosch.com"
    # "Helsingin" only starts with the letters, not the word.
    assert pick_suggestion("Helsing", HELSING_SUGGESTIONS[:1]) is None


def test_pick_suggestion_leaves_other_names_alone():
    assert pick_suggestion("N26", N26_SUGGESTIONS) is None
    assert pick_suggestion("GmbH", HELSING_SUGGESTIONS) is None


def test_find_logo_tries_the_applications_domains_first():
    session = FakeSession(logos={"acme.com"}, suggestions=[])
    applications = [make_application(url="https://jobs.acme.com/1")]
    assert find_logo(session, "Acme", applications) is not None
    assert session.requested == [LOGO_URL.format(domain="acme.com")]


def test_find_logo_falls_back_to_the_name():
    session = FakeSession(
        logos={"helsing.ai"}, suggestions=HELSING_SUGGESTIONS
    )
    applications = [make_application(contact_email="hr@helsing.example")]
    assert find_logo(session, "Helsing AI", applications) is not None
    assert session.requested == [
        LOGO_URL.format(domain="helsing.example"),
        "Helsing AI",
        LOGO_URL.format(domain="helsing.ai"),
    ]


def test_find_logo_gives_up_without_a_matching_name():
    session = FakeSession(logos={"netflix.com"}, suggestions=N26_SUGGESTIONS)
    assert find_logo(session, "N26", [make_application()]) is None


@pytest.mark.parametrize("size", [(400, 100), (10, 30), (64, 64)])
def test_logo_tile_is_square_and_keeps_the_corners_clear(size):
    tile = logo_tile(png_bytes(size))
    assert tile.size == (TILE_SIZE, TILE_SIZE)
    assert tile.mode == "RGBA"
    assert tile.getpixel((0, 0))[3] == 0  # rounded off
    assert tile.getpixel((TILE_SIZE // 2, TILE_SIZE // 2))[:3] == (255, 0, 0)


@pytest.mark.parametrize(
    ("company", "letters"),
    [
        ("Acme Robotics GmbH", "AR"),
        ("helios", "H"),
        ("The Helsing Group", "H"),
        ("N26", "N"),
        ("AG", "A"),  # nothing but a legal form: keep it anyway
    ],
)
def test_initials(company, letters):
    assert initials(company) == letters


def test_initials_tile_keeps_its_color_across_runs():
    first, again = initials_tile("Acme"), initials_tile("acme")
    assert first.size == (TILE_SIZE, TILE_SIZE)
    assert first.tobytes() == initials_tile("Acme").tobytes()
    corner = (TILE_SIZE // 2, 3)
    assert first.getpixel(corner) == again.getpixel(corner)
