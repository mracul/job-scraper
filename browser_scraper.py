"""Browser-based scraper using Selenium for sites with strong anti-bot measures."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from threading import Lock
from urllib.parse import urlencode, urljoin, urlparse, parse_qs, urlunparse
import time
import random
import markdownify
from models import Job


class BrowserScraper:
    """Browser-based scraper using Selenium for anti-bot resistant scraping.
    
    Supported sources:
        - seek: Seek.com.au job listings
        - jora: Jora.com job listings  
        - all: Both Seek and Jora (Seek first, then Jora)
    """

    def __init__(
        self,
        headless: bool = True,
        delay: float = 1.5,
        browser: str = "chrome",
    ):
        """
        Initialize the browser scraper.

        Args:
            headless: Run browser in headless mode (set False to see browser)
            delay: Delay between actions (default 1.5s for fast mode)
            browser: Browser to use: "chrome" or "edge". Default is "chrome".
        """
        self.headless = headless
        self.delay = delay
        self.browser = browser
        # Used by _configure_options(use_profile=True) to persist a stable browser profile.
        # Keeping it internal (no CLI flag) matches the prior Seek-style setup.
        self.profile_dir = ".browser_profiles/default"
        self.driver = None

    def setup_driver(self):
        """Set up WebDriver with anti-detection options."""
        if self.driver:
            return  # Already set up
        
        # Prefer Chrome. Do not implicitly fall back to Edge because a system
        # msedgedriver in PATH can be incompatible with the installed Edge.
        browsers_to_try = []
        if self.browser == "auto":
            browsers_to_try = ["chrome"]
        else:
            browsers_to_try = [self.browser]
        
        last_error = None
        for browser in browsers_to_try:
            try:
                if browser == "chrome":
                    self._setup_chrome()
                else:
                    self._setup_edge()
                print(f"Using {browser.capitalize()} browser")
                return
            except WebDriverException as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        
        raise WebDriverException(f"Could not start any browser. Last error: {last_error}")

    def _setup_chrome(self):
        """Set up Chrome WebDriver."""
        options = ChromeOptions()
        self._configure_options(options, use_profile=True)
        
        # Try system-installed driver first, then fall back to webdriver-manager
        try:
            # Try using system chromedriver
            self.driver = webdriver.Chrome(options=options)
        except WebDriverException:
            # Fall back to webdriver-manager
            from webdriver_manager.chrome import ChromeDriverManager
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        
        self._configure_driver()

    def _setup_edge(self):
        """Set up Edge WebDriver."""
        options = EdgeOptions()
        self._configure_options(options, use_profile=True)
        
        # Try system-installed driver first, then fall back to webdriver-manager
        try:
            # Try using system msedgedriver (e.g., C:\Windows\msedgedriver.exe)
            self.driver = webdriver.Edge(options=options)
        except WebDriverException:
            # Fall back to webdriver-manager
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            service = EdgeService(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=options)
        
        self._configure_driver()

    def _configure_options(self, options, use_profile: bool = True):
        """Configure browser options for anti-detection."""
        if self.headless:
            options.add_argument('--headless=new')
            # Headless-specific stability options
            options.add_argument('--disable-gpu')
            options.add_argument('--remote-debugging-port=0')

        # Persist a real browser profile to reduce repeated bot checks.
        # IMPORTANT: do not share profiles across parallel worker drivers.
        # IMPORTANT: profile persistence can cause crashes in headless mode, so skip it.
        if use_profile and self.profile_dir and not self.headless:
            try:
                from pathlib import Path

                profile_path = Path(self.profile_dir)
                profile_path.mkdir(parents=True, exist_ok=True)
                options.add_argument(f"--user-data-dir={profile_path.resolve()}")
                options.add_argument("--profile-directory=Default")
            except Exception:
                pass

        # Anti-detection options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option('useAutomationExtension', False)

        # Viewport
        if use_profile and self.profile_dir and not self.headless:
            # Keep stable fingerprint with persisted profile.
            options.add_argument('--window-size=1600,1000')
        else:
            width = random.randint(1200, 1920)
            height = random.randint(900, 1080)
            options.add_argument(f'--window-size={width},{height}')

        # User agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        if use_profile and self.profile_dir and not self.headless:
            # Cloudflare clearance cookies can be tied to a fingerprint; keep UA stable for a reused profile.
            options.add_argument(f'--user-agent={user_agents[0]}')
        else:
            options.add_argument(f'--user-agent={random.choice(user_agents)}')

        # Additional options
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')

    def _configure_driver(self):
        """Configure driver after creation."""
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def human_like_delay(self):
        """Add a random human-like delay (fast mode)."""
        time.sleep(self.delay + random.uniform(0.5, 1.5))

    def scroll_page(self):
        """Scroll the page to simulate human behavior."""
        if self.driver:
            scroll_amount = random.randint(300, 700)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.5, 1.5))

    def fetch_job_details(self, jobs: list[Job], max_jobs: int = None, workers: int = 10) -> list[Job]:
        """
        Fetch full job descriptions from job detail pages using parallel workers.
        
        Args:
            jobs: List of Job objects to fetch details for
            max_jobs: Maximum number of jobs to fetch (None = all)
            workers: Number of parallel browser instances (default: 10 for 6-core/12-thread CPU)
        """
        jobs_to_fetch = jobs[:max_jobs] if max_jobs else jobs
        total = len(jobs_to_fetch)
        
        if total == 0:
            return jobs
        
        # Limit workers to number of jobs
        workers = min(workers, total)

        print(f"\nFetching full descriptions for {total} jobs using {workers} parallel workers (driver reuse enabled)...")
        
        # Progress tracking with thread safety
        progress_lock = Lock()
        completed_count = [0]
        success_count = [0]
        
        def fetch_single_job_with_driver(driver, job: Job) -> bool:
            """Fetch details for a single job using an existing browser instance."""
            try:
                driver.get(job.url)
                time.sleep(self.delay + random.uniform(0.3, 0.8))

                full_desc = None

                if job.source == "seek":
                    for selector in [
                        "[data-automation='jobAdDetails']",
                        "[data-automation='jobDescription']",
                        ".job-description",
                        "[class*='jobDescription']",
                        "div[data-automation='jobAdDetails'] div",
                    ]:
                        try:
                            desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
                            html = desc_elem.get_attribute("innerHTML")
                            if html:
                                full_desc = markdownify.markdownify(html, heading_style="ATX").strip()
                            else:
                                full_desc = desc_elem.text.strip()
                            
                            if full_desc and len(full_desc) > 50:
                                break
                        except NoSuchElementException:
                            continue

                elif job.source == "jora":
                    for selector in [
                        "#job-description-container",
                        ".job-description",
                        ".description",
                        "[class*='description']",
                        ".job-details",
                        "#job-description",
                    ]:
                        try:
                            desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
                            html = desc_elem.get_attribute("innerHTML")
                            if html:
                                full_desc = markdownify.markdownify(html, heading_style="ATX").strip()
                            else:
                                full_desc = desc_elem.text.strip()

                            if full_desc and len(full_desc) > 50:
                                break
                        except NoSuchElementException:
                            continue

                if full_desc:
                    job.full_description = full_desc
                    return True
                return False
            except Exception:
                return False

        # Build a job queue for workers
        job_queue: Queue[Job] = Queue()
        for job in jobs_to_fetch:
            job_queue.put(job)

        def worker_loop(worker_id: int) -> None:
            driver = None
            try:
                driver = self._create_worker_driver()
                while True:
                    try:
                        job = job_queue.get_nowait()
                    except Exception:
                        break

                    ok = fetch_single_job_with_driver(driver, job)
                    with progress_lock:
                        if ok:
                            success_count[0] += 1
                        completed_count[0] += 1
                        current = completed_count[0]
                        print(
                            f"  Progress: {current}/{total} jobs processed ({success_count[0]} with descriptions)"
                        )

                    job_queue.task_done()
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        
        # Use ThreadPoolExecutor for parallel fetching (one driver per thread)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker_loop, i) for i in range(workers)]
            for _ in as_completed(futures):
                pass
        
        print(f"Fetched details for {success_count[0]} of {total} jobs")
        return jobs

    def _create_worker_driver(self):
        """Create a new WebDriver instance for a worker thread."""
        # Try Chrome first (more reliable), then Edge
        browsers_to_try = ["chrome", "edge"]
        
        for browser in browsers_to_try:
            try:
                if browser == "chrome":
                    options = ChromeOptions()
                    self._configure_options(options, use_profile=False)
                    return webdriver.Chrome(options=options)
                else:
                    options = EdgeOptions()
                    self._configure_options(options, use_profile=False)
                    return webdriver.Edge(options=options)
            except WebDriverException:
                continue
        
        raise WebDriverException("Could not create worker browser instance")

    def fetch_job_details_sequential(self, jobs: list[Job], max_jobs: int = None) -> list[Job]:
        """Fetch full job descriptions sequentially (original method, kept for fallback)."""
        if not self.driver:
            self.setup_driver()
        
        jobs_to_fetch = jobs[:max_jobs] if max_jobs else jobs
        print(f"\nFetching full descriptions for {len(jobs_to_fetch)} jobs (sequential mode)...")
        
        for i, job in enumerate(jobs_to_fetch, 1):
            try:
                print(f"  [{i}/{len(jobs_to_fetch)}] Fetching: {job.title[:40]}...")
                
                self.driver.get(job.url)
                time.sleep(self.delay + random.uniform(0.5, 1.0))
                
                # Try to find job description based on source
                full_desc = None
                
                        try:
                            desc_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            html = desc_elem.get_attribute("innerHTML")
                            if html:
                                full_desc = markdownify.markdownify(html, heading_style="ATX").strip()
                            else:
                                full_desc = desc_elem.text.strip()
                            
                            if full_desc and len(full_desc) > 50:
                                break
                        except NoSuchElementException:
                            continue
                
                elif job.source == "jora":
                    # Jora job description selectors
                    for selector in [
                        "#job-description-container",
                        ".job-description",
                        ".description",
                        "[class*='description']",
                        ".job-details",
                        "#job-description"
                    ]:
                        try:
                            desc_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            html = desc_elem.get_attribute("innerHTML")
                            if html:
                                full_desc = markdownify.markdownify(html, heading_style="ATX").strip()
                            else:
                                full_desc = desc_elem.text.strip()

                            if full_desc and len(full_desc) > 50:
                                break
                        except NoSuchElementException:
                            continue
                
                if full_desc:
                    job.full_description = full_desc
                    
            except Exception as e:
                print(f"    Error fetching details: {e}")
                continue
        
        print(f"Fetched details for {sum(1 for j in jobs_to_fetch if j.full_description)} jobs")
        return jobs

    # ==================== SEEK SCRAPER ====================
    
    def scrape_seek(self, keywords: str, location: str, max_pages: int = 3) -> list[Job]:
        """Scrape Seek using browser automation."""
        self.setup_driver()
        
        jobs = []
        # Build URL like: https://www.seek.com.au/help-desk-it-jobs/in-Auburn-NSW
        keywords_slug = keywords.lower().replace(' ', '-')
        location_slug = location.replace(' ', '-')
        
        print(f"Scraping Seek for '{keywords}' in '{location}'...")
        
        try:
            for page in range(1, max_pages + 1):
                if page == 1:
                    url = f"https://www.seek.com.au/{keywords_slug}-jobs/in-{location_slug}"
                else:
                    url = f"https://www.seek.com.au/{keywords_slug}-jobs/in-{location_slug}?page={page}"
                    
                print(f"  Browser scraping Seek page {page}: {url}")
                
                self.driver.get(url)
                self.human_like_delay()
                
                # Wait for job cards to load
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 
                            "[data-automation='normalJob'], article[data-testid]"))
                    )
                except TimeoutException:
                    print("    No job cards found - page may have loaded differently")
                    # Try scrolling to trigger lazy loading
                    self.scroll_page()
                    time.sleep(2)
                
                # Scroll down to load all jobs
                for _ in range(3):
                    self.scroll_page()
                
                # Find job cards
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[data-automation='normalJob'], article[data-card-type='JobCard']")
                
                if not job_cards:
                    # Try alternative selectors
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, 
                        "article[data-testid], [data-job-id]")
                
                page_jobs = 0
                for card in job_cards:
                    try:
                        job = self._parse_seek_card(card)
                        if job:
                            jobs.append(job)
                            page_jobs += 1
                    except Exception as e:
                        continue
                
                print(f"    Found {page_jobs} jobs on page {page}")
                
                if page_jobs == 0:
                    print("  No jobs found on this page, stopping.")
                    break
                
                # Check for next page
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR,
                        "[data-automation='page-next'], a[aria-label='Next']")
                    if 'disabled' in next_button.get_attribute('class') or '':
                        break
                except NoSuchElementException:
                    break
                    
        except Exception as e:
            print(f"Error scraping Seek with browser: {e}")
        
        print(f"Total jobs found on Seek: {len(jobs)}")
        return jobs
    
    def _parse_seek_card(self, card) -> Job | None:
        """Parse a job card element from Seek."""
        try:
            # Find title and link
            title_elem = None
            for selector in ["[data-automation='jobTitle']", "a[data-automation='jobTitle']", "h3 a", "[data-testid='job-title'] a"]:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not title_elem:
                return None
                
            title = title_elem.text.strip()
            url = title_elem.get_attribute("href")
            if url and not url.startswith("http"):
                url = "https://www.seek.com.au" + url

            # Find company
            company = "Not specified"
            for selector in ["[data-automation='jobCompany']", "[data-testid='company-name']", "a[data-automation='jobCompany']"]:
                try:
                    company_elem = card.find_element(By.CSS_SELECTOR, selector)
                    company = company_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue

            # Find location
            location = "Not specified"
            for selector in ["[data-automation='jobLocation']", "[data-testid='job-location']", "a[data-automation='jobLocation']"]:
                try:
                    location_elem = card.find_element(By.CSS_SELECTOR, selector)
                    location = location_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue

            # Find salary (if available)
            salary = None
            for selector in ["[data-automation='jobSalary']", "[data-testid='job-salary']", "span[data-automation='jobSalary']"]:
                try:
                    salary_elem = card.find_element(By.CSS_SELECTOR, selector)
                    salary = salary_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue

            # Find description
            description = ""
            for selector in ["[data-automation='jobShortDescription']", "[data-testid='job-snippet']"]:
                try:
                    desc_elem = card.find_element(By.CSS_SELECTOR, selector)
                    description = desc_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue

            # Find listing date (e.g., "2d ago", "30d+ ago")
            date_posted = None
            for selector in ["[data-automation='jobListingDate']", "[data-testid='listing-date']", "span[data-automation='jobListingDate']", "time", ".listing-date"]:
                try:
                    date_elems = card.find_elements(By.CSS_SELECTOR, selector)
                    for elem in date_elems:
                        text = elem.text.strip()
                        if text:
                            date_posted = text
                            break
                    if date_posted:
                        break
                except Exception:
                    continue

            if not title:
                return None
                
            return Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                url=url,
                source="seek",
                date_posted=date_posted
            )

        except Exception as e:
            return None

    # ==================== JORA SCRAPER ====================

    def scrape_jora(self, keywords: str, location: str, max_pages: int = 3) -> list[Job]:
        """Scrape Jora using browser automation (Seek-style Selenium approach)."""
        self.setup_driver()

        jobs: list[Job] = []

        print(f"Scraping Jora for '{keywords}' in '{location}'...")

        url = self._build_jora_search_url(keywords=keywords, location=location)
        current_page = 1
        next_url: str | None = url

        try:
            while next_url and current_page <= max_pages:
                print(f"  Browser scraping Jora page {current_page}: {next_url}")
                self.driver.get(next_url)
                self.human_like_delay()

                # Wait for results to appear
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                "a[href*='/job/'], article, [data-testid*='job'], [class*='job']",
                            )
                        )
                    )
                except TimeoutException:
                    print("    No job results detected on this page")
                    break

                # Scroll to load lazy content
                for _ in range(3):
                    self.scroll_page()

                job_cards = self._find_jora_job_cards()
                if not job_cards:
                    print("    No job cards found on this page")
                    break

                page_jobs = 0
                for card in job_cards:
                    try:
                        job = self._parse_jora_card(card)
                        if job:
                            jobs.append(job)
                            page_jobs += 1
                    except Exception:
                        continue

                print(f"    Found {page_jobs} jobs on page {current_page}")
                if page_jobs == 0:
                    break

                # Try to discover a stable next-page URL from the page itself
                next_url = self._find_jora_next_page_url()
                current_page += 1

        except Exception as e:
            print(f"Error scraping Jora with browser: {e}")

        print(f"Total jobs found on Jora: {len(jobs)}")
        return jobs

    def _build_jora_search_url(self, keywords: str, location: str) -> str:
        """Build a Jora AU search URL using query parameters.

        Example:
            https://au.jora.com/j?a=14d&disallow=true&l=City+of+Sydney+NSW&q=it+support&sp=facet_listed_date
        """
        params: dict[str, str] = {
            "a": "14d",
            "disallow": "true",
            "sp": "facet_listed_date",
            "q": keywords,
            "l": location,
        }
        return "https://au.jora.com/j?" + urlencode(params)

    def _find_jora_job_cards(self):
        """Best-effort job card detection on Jora results pages."""
        # Prefer article-style cards; fall back to any container that includes a /job/ link.
        cards = []
        for selector in [
            "article",
            "[data-testid*='job']",
            "[class*='jobCard']",
            "[class*='job-card']",
            "[class*='result']",
        ]:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    cards = found
                    break
            except Exception:
                continue

        if not cards:
            try:
                # As a last resort: use link ancestors
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/']")
                for link in links:
                    try:
                        card = link.find_element(By.XPATH, "./ancestor::article[1]")
                    except Exception:
                        try:
                            card = link.find_element(By.XPATH, "./ancestor::div[1]")
                        except Exception:
                            card = None
                    if card:
                        cards.append(card)
            except Exception:
                pass

        # Deduplicate elements while preserving order
        unique = []
        seen_ids = set()
        for c in cards:
            try:
                key = c.id
            except Exception:
                key = None
            if key and key in seen_ids:
                continue
            if key:
                seen_ids.add(key)
            unique.append(c)
        return unique

    def _parse_jora_card(self, card) -> Job | None:
        """Parse a job card element from Jora."""
        try:
            title = ""
            url = ""

            # Title + link
            link = None
            for selector in [
                "a[href*='/job/']",
                "a[href*='au.jora.com/job']",
            ]:
                try:
                    candidates = card.find_elements(By.CSS_SELECTOR, selector)
                    for c in candidates:
                        t = (c.text or "").strip()
                        if t:
                            link = c
                            title = t
                            break
                    if link:
                        break
                except Exception:
                    continue

            if link:
                url = (link.get_attribute("href") or "").strip()
                if not title:
                    title = (link.get_attribute("title") or link.get_attribute("aria-label") or "").strip()

            if url and url.startswith("/"):
                url = "https://au.jora.com" + url

            if not title or not url:
                return None

            # Company
            company = "Not specified"
            for selector in [
                "[data-testid*='company']",
                "[class*='company']",
                "a[href*='/company']",
            ]:
                try:
                    elem = card.find_element(By.CSS_SELECTOR, selector)
                    txt = (elem.text or "").strip()
                    if txt:
                        company = txt
                        break
                except Exception:
                    continue

            # Location
            loc = "Not specified"
            for selector in [
                "[data-testid*='location']",
                "[class*='location']",
            ]:
                try:
                    elem = card.find_element(By.CSS_SELECTOR, selector)
                    txt = (elem.text or "").strip()
                    if txt:
                        loc = txt
                        break
                except Exception:
                    continue

            # Salary (optional)
            salary = None
            for selector in [
                "[class*='salary']",
                "[data-testid*='salary']",
            ]:
                try:
                    elem = card.find_element(By.CSS_SELECTOR, selector)
                    txt = (elem.text or "").strip()
                    if txt:
                        salary = txt
                        break
                except Exception:
                    continue

            # Description snippet (best-effort)
            description = ""
            for selector in [
                "[class*='snippet']",
                "[class*='summary']",
                "p",
            ]:
                try:
                    elem = card.find_element(By.CSS_SELECTOR, selector)
                    txt = (elem.text or "").strip()
                    if txt and txt != title:
                        description = txt
                        break
                except Exception:
                    continue

            # Date posted (best-effort)
            date_posted = None
            for selector in [
                "[class*='date']",
                "[data-testid*='date']",
                "time",
                "[class*='posted']",
                "[class*='listing-date']",
            ]:
                try:
                    elem = card.find_element(By.CSS_SELECTOR, selector)
                    txt = (elem.text or "").strip()
                    if txt:
                        date_posted = txt
                        break
                except Exception:
                    continue

            return Job(
                title=title,
                company=company,
                location=loc,
                salary=salary,
                description=description,
                url=url,
                source="jora",
                date_posted=date_posted,
            )
        except Exception:
            return None

    def _find_jora_next_page_url(self) -> str | None:
        """Attempt to discover a stable next-page URL on Jora."""
        def _normalize_candidate_href(href: str) -> str | None:
            href = (href or "").strip()
            if not href:
                return None
            lowered = href.lower()
            if lowered.startswith("javascript:") or lowered.startswith("#"):
                return None

            current_url = getattr(self.driver, "current_url", None)
            if href.startswith("?") and current_url:
                try:
                    parsed_current = urlparse(current_url)
                    current_qs = parse_qs(parsed_current.query, keep_blank_values=True)
                    update_qs = parse_qs(href[1:], keep_blank_values=True)
                    current_qs.update(update_qs)
                    merged_query = urlencode(current_qs, doseq=True)
                    merged = parsed_current._replace(query=merged_query, fragment="")
                    return urlunparse(merged)
                except Exception:
                    pass

            base = getattr(self.driver, "current_url", None) or "https://au.jora.com/"
            try:
                joined = urljoin(base, href)
                parsed_joined = urlparse(joined)
                joined = urlunparse(parsed_joined._replace(fragment=""))
                if joined.startswith("http://") or joined.startswith("https://"):
                    return joined
            except Exception:
                return None
            return None

        def _extract_page_number(url: str) -> int | None:
            try:
                qs = parse_qs(urlparse(url).query)
                for key in ("page", "p"):
                    raw = (qs.get(key) or [None])[0]
                    if raw is None:
                        continue
                    return int(raw)
            except Exception:
                return None
            return None

        def _iter_elements(selector: str):
            if not self.driver:
                return []
            try:
                if hasattr(self.driver, "find_elements"):
                    return self.driver.find_elements(By.CSS_SELECTOR, selector) or []
            except Exception:
                pass
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                return [elem] if elem else []
            except Exception:
                return []

        current_url = getattr(self.driver, "current_url", None) or ""
        current_url_norm = _normalize_candidate_href(current_url) or current_url
        current_page = _extract_page_number(current_url_norm) or 1

        # Highest-confidence selectors first.
        for selector in ("a[rel='next']", "a[aria-label*='Next']", "a[title*='Next']"):
            for elem in _iter_elements(selector):
                try:
                    href = elem.get_attribute("href")
                except Exception:
                    href = None
                normalized = _normalize_candidate_href(href or "")
                if normalized and normalized != current_url_norm:
                    return normalized

        # Fallback: collect pagination-like links and choose the smallest page > current.
        candidates: list[str] = []
        for selector in ("a[href*='page=']", "a[href*='p=']"):
            for elem in _iter_elements(selector):
                try:
                    href = elem.get_attribute("href")
                except Exception:
                    href = None
                normalized = _normalize_candidate_href(href or "")
                if not normalized:
                    continue
                if normalized == current_url_norm:
                    continue
                candidates.append(normalized)

        if not candidates:
            return None

        unique_candidates: list[str] = []
        seen = set()
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            unique_candidates.append(c)

        best_url: str | None = None
        best_page: int | None = None
        for c in unique_candidates:
            page_num = _extract_page_number(c)
            if page_num is None:
                continue
            if page_num <= current_page:
                continue
            if best_page is None or page_num < best_page:
                best_page = page_num
                best_url = c

        return best_url or unique_candidates[0]

    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                # Fail soft: driver can occasionally time out on shutdown after heavy parallel use
                pass
            finally:
                self.driver = None

    def scrape_all(self, keywords: str, location: str, max_pages: int = 3) -> list[Job]:
        """Scrape both Seek and Jora (Seek first, then Jora)."""
        all_jobs = []
        
        # Scrape Seek first
        seek_jobs = self.scrape_seek(keywords, location, max_pages)
        all_jobs.extend(seek_jobs)
        
        # Add delay between sites
        print(f"\nWaiting before scraping Jora...")
        time.sleep(self.delay + random.uniform(1, 2))
        
        # Scrape Jora
        jora_jobs = self.scrape_jora(keywords, location, max_pages)
        all_jobs.extend(jora_jobs)
        
        # Close the browser
        self.close()
        
        return all_jobs


# Default search values
DEFAULT_KEYWORDS = "help desk it"
DEFAULT_LOCATION = "Auburn NSW"


def main():
    """Main function for browser-based scraping."""
    from models import JobCollection
    from datetime import datetime
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser-based job scraper for Seek and Jora")
    parser.add_argument("--pages", "-p", type=int, default=3, help="Max pages to scrape per site")
    parser.add_argument("--source", "-s", choices=["all", "seek", "jora"], default="all", help="Site to scrape")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv", help="Output format")
    parser.add_argument("--visible", "-v", action="store_true", help="Show browser window (not headless)")
    parser.add_argument("--delay", "-d", type=float, default=3.0, help="Base delay between requests")
    args = parser.parse_args()
    
    # Interactive prompts
    print("\n" + "=" * 60)
    print("Browser-Based Job Scraper")
    print("=" * 60)
    
    keywords = input(f"\nEnter job title/keywords [{DEFAULT_KEYWORDS}]: ").strip()
    if not keywords:
        keywords = DEFAULT_KEYWORDS
    
    location = input(f"Enter location [{DEFAULT_LOCATION}]: ").strip()
    if not location:
        location = DEFAULT_LOCATION
    
    print(f"\n{'='*60}")
    print(f"Searching for '{keywords}' in '{location}'")
    print(f"{'='*60}\n")
    
    # Create scraper
    scraper = BrowserScraper(headless=not args.visible, delay=args.delay)
    collection = JobCollection()
    
    try:
        if args.source == "all":
            jobs = scraper.scrape_all(keywords, location, args.pages)
            collection.add_all(jobs)
        elif args.source == "seek":
            jobs = scraper.scrape_seek(keywords, location, args.pages)
            collection.add_all(jobs)
            scraper.close()
        else:
            jobs = scraper.scrape_jora(keywords, location, args.pages)
            collection.add_all(jobs)
            scraper.close()
    except Exception as e:
        print(f"Error during scraping: {e}")
        scraper.close()
    
    print(f"\n{'='*60}")
    print(f"Total jobs found: {len(collection)}")
    print(f"{'='*60}\n")
    
    # Generate output filename
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"jobs_{timestamp}.{args.format}"
    
    if not args.output.endswith(f".{args.format}"):
        args.output = f"{args.output}.{args.format}"
    
    # Export results
    if len(collection) > 0:
        if args.format == "csv":
            collection.to_csv(args.output)
        else:
            collection.to_json(args.output)
        
        # Print sample
        print("\nSample of jobs found:")
        print("-" * 60)
        for job in list(collection)[:5]:
            print(f"\n📋 {job.title}")
            print(f"   🏢 {job.company}")
            print(f"   📍 {job.location}")
            if job.salary:
                print(f"   💰 {job.salary}")
            print(f"   🔗 {job.url[:70]}...")
    else:
        print("No jobs found.")


if __name__ == "__main__":
    main()
