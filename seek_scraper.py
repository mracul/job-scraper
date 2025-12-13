"""Scraper for Seek.com.au job listings."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
import time
import re
import random
from models import Job


class SeekScraper:
    """Scraper for Seek.com.au"""

    BASE_URL = "https://www.seek.com.au"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    def __init__(self, delay: float = 1.0):
        """
        Initialize the Seek scraper.
        
        Args:
            delay: Delay between requests in seconds to be respectful
        """
        self.session = requests.Session()
        self.base_delay = delay
        self.max_retries = 3

    def get_randomized_headers(self) -> dict:
        """Get randomized headers to avoid detection."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        ]
        
        headers = self.HEADERS.copy()
        headers["User-Agent"] = random.choice(user_agents)
        return headers

    def build_search_url(self, keywords: str, location: str, page: int = 1) -> str:
        """
        Build the search URL for Seek.
        
        Args:
            keywords: Job search keywords
            location: Location to search in (e.g., "Auburn NSW" or "Auburn NSW 2144")
            page: Page number (1-indexed)
            
        Returns:
            The full search URL
        """
        # Seek uses URL path format: /keyword-jobs/in-Location-State-Postcode
        # Example: /help-desk-it-jobs/in-Auburn-NSW-2144
        keywords_slug = keywords.lower().replace(' ', '-')
        location_slug = location.replace(' ', '-')
        
        url = f"{self.BASE_URL}/{keywords_slug}-jobs/in-{location_slug}"
        
        if page > 1:
            url += f"?page={page}"
            
        return url

    def parse_job_card(self, card) -> Job | None:
        """
        Parse a job card element into a Job object.
        
        Args:
            card: BeautifulSoup element containing job card
            
        Returns:
            Job object or None if parsing fails
        """
        try:
            # Find job title and link
            title_elem = card.find('a', {'data-automation': 'jobTitle'})
            if not title_elem:
                title_elem = card.find('a', attrs={'data-automation': re.compile('jobTitle')})
            if not title_elem:
                # Try alternative selectors
                title_elem = card.select_one('h3 a, [data-automation*="title"] a')
            
            if not title_elem:
                return None
                
            title = title_elem.get_text(strip=True)
            job_url = title_elem.get('href', '')
            if job_url and not job_url.startswith('http'):
                job_url = self.BASE_URL + job_url

            # Find company name
            company_elem = card.find('a', {'data-automation': 'jobCompany'})
            if not company_elem:
                company_elem = card.find(attrs={'data-automation': re.compile('company')})
            if not company_elem:
                company_elem = card.select_one('[data-automation*="company"]')
            company = company_elem.get_text(strip=True) if company_elem else "Not specified"

            # Find location
            location_elem = card.find('a', {'data-automation': 'jobLocation'})
            if not location_elem:
                location_elem = card.find(attrs={'data-automation': re.compile('location')})
            if not location_elem:
                location_elem = card.select_one('[data-automation*="location"]')
            location = location_elem.get_text(strip=True) if location_elem else "Not specified"

            # Find salary (if available)
            salary_elem = card.find(attrs={'data-automation': 'jobSalary'})
            if not salary_elem:
                salary_elem = card.select_one('[data-automation*="salary"]')
            salary = salary_elem.get_text(strip=True) if salary_elem else None

            # Find description/teaser
            desc_elem = card.find(attrs={'data-automation': 'jobShortDescription'})
            if not desc_elem:
                desc_elem = card.select_one('[data-automation*="description"], [data-automation*="teaser"]')
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            return Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                url=job_url,
                source="seek"
            )

        except Exception as e:
            print(f"Error parsing job card: {e}")
            return None

    def scrape_page(self, url: str) -> tuple[list[Job], bool]:
        """
        Scrape a single page of job listings.
        
        Args:
            url: The URL to scrape
            
        Returns:
            Tuple of (list of jobs, has_more_pages)
        """
        jobs = []
        has_more = False

        for attempt in range(self.max_retries):
            try:
                # Use randomized headers for each attempt
                headers = self.get_randomized_headers()
                
                response = self.session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find job cards - Seek uses various article/div structures
                job_cards = soup.find_all('article', {'data-automation': 'normalJob'})
                
                if not job_cards:
                    # Try alternative selectors
                    job_cards = soup.select('[data-automation="normalJob"], [data-card-type="JobCard"]')
                
                if not job_cards:
                    # Fallback to finding job links
                    job_cards = soup.select('article[data-automation*="job"]')

                for card in job_cards:
                    job = self.parse_job_card(card)
                    if job:
                        jobs.append(job)

                # Check for next page
                next_page = soup.find('a', {'data-automation': 'page-next'})
                if not next_page:
                    next_page = soup.select_one('[aria-label*="Next"], [data-automation*="next"]')
                has_more = next_page is not None

                # Success - break out of retry loop
                break

            except requests.HTTPError as e:
                if e.response.status_code == 403:
                    if attempt < self.max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                        print(f"  403 Forbidden - retrying in {wait_time:.1f} seconds (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"  Failed after {self.max_retries} attempts - Seek is blocking requests")
                        print("  Consider using a VPN or waiting longer between requests")
                        return [], False
                else:
                    print(f"  HTTP Error {e.response.status_code}: {e}")
                    return [], False
            except requests.RequestException as e:
                print(f"  Error fetching {url}: {e}")
                return [], False
            except Exception as e:
                print(f"  Error parsing page: {e}")
                return [], False

        return jobs, has_more

    def scrape(self, keywords: str, location: str, max_pages: int = 5) -> list[Job]:
        """
        Scrape Seek for job listings.
        
        Args:
            keywords: Search keywords
            location: Location to search
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of Job objects
        """
        all_jobs = []
        
        print(f"Scraping Seek for '{keywords}' in '{location}'...")
        
        for page in range(1, max_pages + 1):
            url = self.build_search_url(keywords, location, page)
            print(f"  Scraping page {page}: {url}")
            
            jobs, has_more = self.scrape_page(url)
            all_jobs.extend(jobs)
            
            print(f"    Found {len(jobs)} jobs on page {page}")
            
            if not has_more:
                print("  No more pages available.")
                break
                
            if page < max_pages:
                # Add randomized delay to appear more human-like
                delay = self.base_delay + random.uniform(0, 1)
                time.sleep(delay)
        
        print(f"Total jobs found on Seek: {len(all_jobs)}")
        return all_jobs


if __name__ == "__main__":
    # Test the scraper
    scraper = SeekScraper()
    jobs = scraper.scrape("python developer", "sydney", max_pages=2)
    
    for job in jobs[:5]:
        print(f"\n{job.title} at {job.company}")
        print(f"  Location: {job.location}")
        print(f"  Salary: {job.salary}")
        print(f"  URL: {job.url}")
