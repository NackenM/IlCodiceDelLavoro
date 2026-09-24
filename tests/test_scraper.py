"""Parsing job postings (no network: only the HTML parsing is tested)."""

from job_tracker.scraper import MIN_DESCRIPTION_LENGTH, parse_posting_html

URL = "https://jobs.example/42"
LONG_TEXT = "Build things. " * (MIN_DESCRIPTION_LENGTH // 10)


def test_title_from_h1_and_description_from_known_container():
    html = f"""
        <html><head><title>Careers | Acme</title></head><body>
        <h1>Backend Engineer</h1>
        <nav>Home About</nav>
        <div class="job-description">{LONG_TEXT}</div>
        </body></html>
    """
    posting = parse_posting_html(html, URL)
    assert posting.title == "Backend Engineer"
    assert posting.description == LONG_TEXT.strip()
    assert posting.url == URL


def test_title_falls_back_to_the_page_title():
    posting = parse_posting_html(
        "<html><head><title>Data Analyst</title></head></html>", URL
    )
    assert posting.title == "Data Analyst"


def test_short_matches_fall_back_to_the_whole_body():
    html = "<body><main>Too short</main><p>Apply now</p></body>"
    posting = parse_posting_html(html, URL)
    assert posting.description == "Too short\nApply now"


def test_empty_page():
    posting = parse_posting_html("", URL)
    assert (posting.title, posting.description) == ("", "")
