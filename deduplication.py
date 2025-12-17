"""
Job Deduplication Logic
Handles deduplication of job listings based on URL and Title/Company/Description matching.
"""

import re
import unicodedata
from typing import List, Tuple, Set, Optional

from models import Job

class Deduplicator:
    """Handles deduplication of job listings."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for consistent comparison."""
        if not text:
            return ""
        # Normalize unicode characters
        text = unicodedata.normalize("NFKC", text)
        # Lowercase
        text = text.lower()
        # Remove special characters and extra whitespace
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _get_fuzzy_match_key(job: Job) -> str:
        """Generate a key for fuzzy matching based on title, company, and location."""
        # Normalize fields
        n_title = Deduplicator.normalize_text(job.title)
        n_company = Deduplicator.normalize_text(job.company)
        
        # Create a simplified location for cross-site deduplication
        # Normalize suburbs to their parent city to catch cross-site duplicates
        n_location = Deduplicator.normalize_text(job.location)
        
        # Sydney metro area
        sydney_suburbs = ["sydney", "auburn", "bankstown", "parramatta", "marrickville", "rydalmere", 
                         "villawood", "macquarie park", "st leonards", "riverwood", "milsons point", "wetherill park"]
        if any(suburb in n_location for suburb in sydney_suburbs) or "sydney" in n_location:
            n_location = "sydney"
        # Melbourne metro area  
        elif "melbourne" in n_location:
            n_location = "melbourne"
        # Brisbane metro area
        elif "brisbane" in n_location:
            n_location = "brisbane"
        
        # Create composite key
        return f"{n_title}|{n_company}|{n_location}"

    @staticmethod
    def deduplicate_jobs(jobs: List[Job], seen_urls: Set[str] = None) -> Tuple[List[Job], int, int]:
        """
        Deduplicate jobs based on URL and Title/Company matching.
        
        Args:
            jobs: List of Job objects to deduplicate
            seen_urls: Set of URLs already processed in previous runs (optional)
            
        Returns:
            Tuple containing:
            - List of unique jobs
            - Count of duplicates removed by URL
            - Count of duplicates removed by fuzzy matching (cross-site)
        """
        unique_jobs = []
        seen_keys = set()
        
        # Initialize with previously seen URLs if provided
        seen_url_set = set(seen_urls) if seen_urls else set()
        
        url_dupes = 0
        fuzzy_dupes = 0
        
        for job in jobs:
            # 1. URL-based deduplication
            if job.url:
                # Check against seen_urls (from previous runs) and current batch
                if job.url in seen_url_set:
                    url_dupes += 1
                    continue
                seen_url_set.add(job.url)
            
            # 2. Fuzzy matching (Cross-site deduplication)
            # Only apply if we have enough info
            if job.title and job.company and job.company.lower() != "not specified":
                key = Deduplicator._get_fuzzy_match_key(job)
                
                # If we've seen this job key before, it's likely a cross-site duplicate
                # (e.g. same job on Seek and Jora)
                if key in seen_keys:
                    fuzzy_dupes += 1
                    continue
                
                seen_keys.add(key)
            
            unique_jobs.append(job)
            
        return unique_jobs, url_dupes, fuzzy_dupes
