import os
import pathlib

import pytest


@pytest.mark.network
def test_jora_retrieves_at_least_one_job():
    """Network smoke test: ensures Jora search returns >= 1 job.

    Notes:
        - This uses Selenium (BrowserScraper).
        - Keep this stable: scrape only 1 page.
    """

    # Lazily import so test collection doesn't require selenium to be importable everywhere.
    from browser_scraper import BrowserScraper

    # Reduce risk of auth gate: query only first page.
    keywords = "it support"
    location = "City of Sydney NSW"

    scraper = BrowserScraper(headless=True, delay=1.5)

    try:
        jobs = scraper.scrape_jora(keywords=keywords, location=location, max_pages=1)
    finally:
        scraper.close()

    assert len(jobs) >= 1, "Jora returned 0 jobs. Try rerunning with --visible to observe any blocking."


def test_jora_url_builder_matches_expected_shape():
    from browser_scraper import BrowserScraper

    s = BrowserScraper(headless=True)
    url = s._build_jora_search_url(keywords="it support", location="City of Sydney NSW")

    assert url.startswith("https://au.jora.com/j?")
    assert "q=it+support" in url
    assert "l=City+of+Sydney+NSW" in url
    assert "sp=facet_listed_date" in url
    assert "disallow=true" in url
    assert "a=14d" in url
