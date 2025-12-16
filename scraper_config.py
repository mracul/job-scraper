"""Configuration for web scrapers (selectors, URLs, etc)."""

SEEK_SELECTORS = {
    "job_card": "[data-automation='normalJob'], article[data-card-type='JobCard']",
    "job_card_fallback": "article[data-testid], [data-job-id]",
    "next_button": "[data-automation='page-next'], a[aria-label='Next']",
    "job_title": ["[data-automation='jobTitle']", "a[data-automation='jobTitle']", "h3 a", "[data-testid='job-title'] a"],
    "company": ["[data-automation='jobCompany']", "[data-testid='company-name']", "a[data-automation='jobCompany']"],
    "location": ["[data-automation='jobLocation']", "[data-testid='job-location']", "a[data-automation='jobLocation']"],
    "salary": ["[data-automation='jobSalary']", "[data-testid='job-salary']", "span[data-automation='jobSalary']"],
    "description_snippet": ["[data-automation='jobShortDescription']", "[data-testid='job-snippet']"],
    "date_posted": ["[data-automation='jobListingDate']", "[data-testid='listing-date']", "span[data-automation='jobListingDate']", "time", ".listing-date"],
    "full_description": [
        "[data-automation='jobAdDetails']",
        "[data-automation='jobDescription']",
        ".job-description",
        "[class*='jobDescription']",
        "div[data-automation='jobAdDetails'] div",
    ],
}

JORA_SELECTORS = {
    "job_card": [
        "article",
        "[data-testid*='job']",
        "[class*='jobCard']",
        "[class*='job-card']",
        "[class*='result']",
    ],
    "next_button_candidates": ["a[rel='next']", "a[aria-label*='Next']", "a[title*='Next']"],
    "job_link": ["a[href*='/job/']", "a[href*='au.jora.com/job']"],
    "company": ["[data-testid*='company']", "[class*='company']", "a[href*='/company']"],
    "location": ["[data-testid*='location']", "[class*='location']"],
    "salary": ["[class*='salary']", "[data-testid*='salary']"],
    "description_snippet": ["[class*='snippet']", "[class*='summary']", "p"],
    "date_posted": ["[class*='date']", "[data-testid*='date']", "time", "[class*='posted']", "[class*='listing-date']"],
    "full_description": [
        "#job-description-container",
        ".job-description",
        ".description",
        "[class*='description']",
        ".job-details",
        "#job-description",
    ],
}
