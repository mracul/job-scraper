import pytest
from selenium.common.exceptions import NoSuchElementException
from browser_scraper import BrowserScraper
from models import Job

class MockWebElement:
    def __init__(self, tag="div", text="", attributes=None, children=None):
        self.tag_name = tag
        self._text = text
        self.attributes = attributes or {}
        self.children = children or {} # dict of selector -> list of MockWebElement

    @property
    def text(self):
        return self._text

    @property
    def id(self):
        return "mock_id"

    def get_attribute(self, name):
        return self.attributes.get(name)

    def find_element(self, by, value):
        # We assume by is CSS_SELECTOR for simplicity in this mock
        found = self.children.get(value)
        if found:
            return found[0]
        raise NoSuchElementException(f"No element found for {value}")

    def find_elements(self, by, value):
        return self.children.get(value, [])

def test_jora_url_builder_matches_expected_shape():
    # Moved from test_indeed_smoke.py
    s = BrowserScraper(headless=True)
    url = s._build_jora_search_url(keywords="it support", location="City of Sydney NSW")

    assert url.startswith("https://au.jora.com/j?")
    assert "q=it+support" in url
    assert "l=City+of+Sydney+NSW" in url
    assert "sp=facet_listed_date" in url
    assert "disallow=true" in url
    assert "a=14d" in url

def test_parse_seek_card_valid():
    scraper = BrowserScraper(headless=True)
    
    # Construct a mock card
    # Seek uses selectors like "[data-automation='jobTitle']"
    
    title_el = MockWebElement(tag="a", text="Software Engineer", attributes={"href": "/job/123"})
    company_el = MockWebElement(text="Tech Corp")
    location_el = MockWebElement(text="Sydney")
    salary_el = MockWebElement(text="$100k")
    desc_el = MockWebElement(text="Great job")
    date_el = MockWebElement(text="2d ago")

    card = MockWebElement(children={
        "[data-automation='jobTitle']": [title_el],
        "[data-automation='jobCompany']": [company_el],
        "[data-automation='jobLocation']": [location_el],
        "[data-automation='jobSalary']": [salary_el],
        "[data-automation='jobShortDescription']": [desc_el],
        "[data-automation='jobListingDate']": [date_el]
    })

    job = scraper._parse_seek_card(card)
    
    assert job is not None
    assert job.title == "Software Engineer"
    assert job.company == "Tech Corp"
    assert job.location == "Sydney"
    assert job.salary == "$100k"
    assert job.description == "Great job"
    assert job.date_posted == "2d ago"
    assert job.url == "https://www.seek.com.au/job/123"

def test_parse_seek_card_missing_optional_fields():
    scraper = BrowserScraper(headless=True)
    
    title_el = MockWebElement(tag="a", text="Minimal Job", attributes={"href": "/job/999"})
    # Only title is mandatory for _parse_seek_card to return a Job
    
    card = MockWebElement(children={
        "[data-automation='jobTitle']": [title_el]
    })

    job = scraper._parse_seek_card(card)
    
    assert job is not None
    assert job.title == "Minimal Job"
    assert job.company == "Not specified"
    assert job.location == "Not specified"
    assert job.salary is None
    assert job.date_posted is None

def test_parse_jora_card_valid():
    scraper = BrowserScraper(headless=True)
    
    # Jora uses "a[href*='/job/']"
    link_el = MockWebElement(tag="a", text="Admin Assistant", attributes={"href": "/job/456", "title": "Admin Assistant"})
    company_el = MockWebElement(text="Office Works")
    loc_el = MockWebElement(text="Melbourne")
    desc_el = MockWebElement(text="Data entry")
    date_el = MockWebElement(text="Yesterday")
    
    card = MockWebElement(children={
        "a[href*='/job/']": [link_el],
        "[class*='company']": [company_el],
        "[class*='location']": [loc_el],
        "[class*='summary']": [desc_el],
        "[class*='date']": [date_el]
    })
    
    job = scraper._parse_jora_card(card)
    
    assert job is not None
    assert job.title == "Admin Assistant"
    assert job.company == "Office Works"
    assert job.location == "Melbourne"
    assert job.url == "https://au.jora.com/job/456"
    assert job.description == "Data entry"
    assert job.date_posted == "Yesterday"

def test_parse_jora_card_missing_title_returns_none():
    scraper = BrowserScraper(headless=True)
    # Card with no link/title
    card = MockWebElement(children={})
    job = scraper._parse_jora_card(card)
    assert job is None
