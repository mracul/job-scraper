import pytest
from selenium.common.exceptions import NoSuchElementException


class _FakeElement:
    def __init__(self, href: str):
        self._href = href

    def get_attribute(self, name: str):
        if name == "href":
            return self._href
        return None


class _FakeDriver:
    """Minimal fake Selenium driver for testing next-page discovery."""

    def __init__(self, selector_to_href: dict[str, str]):
        self._selector_to_href = selector_to_href

    def find_element(self, by, selector: str):
        # BrowserScraper._find_jora_next_page_url passes (By.CSS_SELECTOR, selector)
        if selector in self._selector_to_href:
            return _FakeElement(self._selector_to_href[selector])
        raise NoSuchElementException(f"No element for selector: {selector}")


def test_jora_next_page_url_prefers_rel_next_and_normalizes_relative():
    from browser_scraper import BrowserScraper

    scraper = BrowserScraper(headless=True)
    scraper.driver = _FakeDriver({
        "a[rel='next']": "/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2",
    })

    next_url = scraper._find_jora_next_page_url()
    assert next_url == (
        "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2"
    )


def test_jora_next_page_url_falls_back_to_next_label_and_keeps_absolute():
    from browser_scraper import BrowserScraper

    scraper = BrowserScraper(headless=True)
    scraper.driver = _FakeDriver({
        "a[aria-label*='Next']": "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2",
    })

    next_url = scraper._find_jora_next_page_url()
    assert next_url.startswith("https://au.jora.com/")
    assert "page=2" in next_url


def test_jora_next_page_url_returns_none_when_missing():
    from browser_scraper import BrowserScraper

    scraper = BrowserScraper(headless=True)
    scraper.driver = _FakeDriver({})

    assert scraper._find_jora_next_page_url() is None
