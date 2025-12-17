"""Data models for job listings."""
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime
import json
import csv
import os
import re


@dataclass
class Job:
    """Represents a job listing."""
    title: str
    company: str
    location: str
    salary: Optional[str]
    description: str
    url: str
    source: str  # 'seek' or 'jora'
    full_description: Optional[str] = None  # Full job description from detail page
    date_posted: Optional[str] = None  # Date the job was posted (e.g., "2d ago", "30d+ ago")
    # Scoring fields (optional, populated when --enable-scoring is used)
    score: Optional[int] = None
    classification: Optional[str] = None  # APPLY, STRETCH, IGNORE
    matched_signals: Optional[str] = None
    exclude_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert job to dictionary."""
        return asdict(self)
    

class JobCollection:
    """Collection of job listings."""

    def __init__(self):
        self.jobs: list[Job] = []
        self.run_folder: Optional[str] = None
        self.search_keywords: Optional[str] = None
        self.search_location: Optional[str] = None
        self.bundle_names: Optional[list[str]] = None  # For bundled scrapes

    def add(self, job: Job):
        """Add a job to the collection."""
        self.jobs.append(job)

    def add_all(self, jobs: list[Job]):
        """Add multiple jobs to the collection."""
        self.jobs.extend(jobs)

    def set_search_params(self, keywords: str, location: str):
        """Store the search parameters used for this collection."""
        self.search_keywords = keywords
        self.search_location = location

    def set_bundle_params(self, bundle_names: list[str]):
        """Store bundle information for bundled scrapes."""
        self.bundle_names = bundle_names

    def create_run_folder(self, base_folder: str = "scraped_data") -> str:
        """Create a folder for this scraping run named after search params or bundle."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # For bundled scrapes, use bundle name + timestamp
        if self.bundle_names:
            # Create a bundle name from the selected bundles
            # Remove emoji prefix (like "1️⃣ ", "2️⃣ ") and clean up
            bundle_name = self.bundle_names[0]
            # Remove emoji number prefix
            bundle_name = re.sub(r'^\d+️⃣\s+', '', bundle_name)
            # Remove time descriptors in parentheses
            bundle_name = re.sub(r'\s*\([^)]*\)\s*$', '', bundle_name)
            # Take first few words and make it filesystem safe
            bundle_name = bundle_name.strip()[:25].replace(' ', '_')
            # Final sanitization
            safe_bundle = re.sub(r'[<>:"/\\|?*]', '', bundle_name)
            folder_name = f"{safe_bundle}_{timestamp}"
        # For regular searches, use keywords + location + timestamp
        elif self.search_keywords and self.search_location:
            # Sanitize for filesystem
            safe_keywords = re.sub(r'[<>:"/\\|?*]', '', self.search_keywords)[:30].strip().replace(' ', '_')
            safe_location = re.sub(r'[<>:"/\\|?*]', '', self.search_location)[:20].strip().replace(' ', '_')
            folder_name = f"{safe_keywords}_{safe_location}_{timestamp}"
        else:
            folder_name = f"run_{timestamp}"
        
        self.run_folder = os.path.join(base_folder, folder_name)
        os.makedirs(self.run_folder, exist_ok=True)
        return self.run_folder

    def __len__(self):
        return len(self.jobs)

    def __iter__(self):
        return iter(self.jobs)