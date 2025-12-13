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

    def __init__(self, selector_to_href: dict[str, str | list[str]], current_url: str = "https://au.jora.com/j"):
        self.current_url = current_url
        self._selector_to_hrefs: dict[str, list[str]] = {}
        for selector, hrefs in selector_to_href.items():
            if isinstance(hrefs, list):
                self._selector_to_hrefs[selector] = hrefs
            else:
                self._selector_to_hrefs[selector] = [hrefs]

    def find_elements(self, by, selector: str):
        # BrowserScraper._find_jora_next_page_url passes (By.CSS_SELECTOR, selector)
        hrefs = self._selector_to_hrefs.get(selector, [])
        return [_FakeElement(href) for href in hrefs]

    def find_element(self, by, selector: str):
        found = self.find_elements(by, selector)
        if found:
            return found[0]
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


def test_jora_next_page_url_fallback_skips_current_page_and_picks_next():
    from browser_scraper import BrowserScraper

    current_url = (
        "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=1"
    )
    scraper = BrowserScraper(headless=True)
    scraper.driver = _FakeDriver(
        {
            "a[href*='page=']": [
                current_url,
                "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2",
                "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=10",
            ]
        },
        current_url=current_url,
    )

    assert "page=2" in (scraper._find_jora_next_page_url() or "")


def test_jora_next_page_url_normalizes_query_only_href_by_merging():
    from browser_scraper import BrowserScraper

    current_url = (
        "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=1"
    )
    scraper = BrowserScraper(headless=True)
    scraper.driver = _FakeDriver({"a[rel='next']": "?page=2"}, current_url=current_url)

    next_url = scraper._find_jora_next_page_url() or ""
    assert next_url.startswith("https://au.jora.com/j?")
    assert "page=2" in next_url
    assert "q=it+support" in next_url
    assert "l=City+of+Sydney+NSW" in next_url


def test_scrape_jora_paginates_across_pages_without_real_browser(monkeypatch):
    import browser_scraper
    from browser_scraper import BrowserScraper
    from models import Job

    class _NoWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, condition):
            return True

    monkeypatch.setattr(browser_scraper, "WebDriverWait", _NoWait)

    class _LoopDriver:
        def __init__(self):
            self.visited: list[str] = []
            self.current_url: str = ""

        def get(self, url: str):
            self.current_url = url
            self.visited.append(url)

    scraper = BrowserScraper(headless=True)
    driver = _LoopDriver()
    scraper.driver = driver

    monkeypatch.setattr(scraper, "human_like_delay", lambda: None)
    monkeypatch.setattr(scraper, "scroll_page", lambda: None)

    cards_page_1 = [object(), object()]
    cards_page_2 = [object()]

    def _fake_find_cards():
        if "page=2" in (driver.current_url or ""):
            return cards_page_2
        return cards_page_1

    def _fake_parse_card(card):
        return Job(
            title="t",
            company="c",
            location="l",
            salary=None,
            description="",
            url=f"{driver.current_url}#{id(card)}",
            source="jora",
        )

    def _fake_next_page():
        if "page=2" in (driver.current_url or ""):
            return None
        return "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2"

    monkeypatch.setattr(scraper, "_find_jora_job_cards", _fake_find_cards)
    monkeypatch.setattr(scraper, "_parse_jora_card", _fake_parse_card)
    monkeypatch.setattr(scraper, "_find_jora_next_page_url", _fake_next_page)

    jobs = scraper.scrape_jora(keywords="it support", location="City of Sydney NSW", max_pages=5)

    assert len(driver.visited) == 2
    assert len(jobs) == 3
    assert any("page=2" in u for u in driver.visited)


def test_scrape_jora_honors_max_pages(monkeypatch):
    import browser_scraper
    from browser_scraper import BrowserScraper
    from models import Job

    class _NoWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, condition):
            return True

    monkeypatch.setattr(browser_scraper, "WebDriverWait", _NoWait)

    class _LoopDriver:
        def __init__(self):
            self.visited: list[str] = []
            self.current_url: str = ""

        def get(self, url: str):
            self.current_url = url
            self.visited.append(url)

    scraper = BrowserScraper(headless=True)
    driver = _LoopDriver()
    scraper.driver = driver

    monkeypatch.setattr(scraper, "human_like_delay", lambda: None)
    monkeypatch.setattr(scraper, "scroll_page", lambda: None)
    monkeypatch.setattr(scraper, "_find_jora_job_cards", lambda: [object()])
    monkeypatch.setattr(
        scraper,
        "_parse_jora_card",
        lambda c: Job(title="t", company="c", location="l", salary=None, description="", url=driver.current_url, source="jora"),
    )
    monkeypatch.setattr(
        scraper,
        "_find_jora_next_page_url",
        lambda: "https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date&page=2",
    )

    jobs = scraper.scrape_jora(keywords="it support", location="City of Sydney NSW", max_pages=1)

    assert len(driver.visited) == 1
    assert len(jobs) == 1
