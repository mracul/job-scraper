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
    
    def to_file(self, folder: str, index: int) -> str:
        """Save job details to a text file."""
        # Create safe filename
        safe_title = re.sub(r'[<>:"/\\|?*]', '', self.title)[:50]
        safe_company = re.sub(r'[<>:"/\\|?*]', '', self.company)[:30]
        filename = f"{index:03d}_{safe_title}_{safe_company}.txt"
        filepath = os.path.join(folder, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"JOB DETAILS\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Title: {self.title}\n")
            f.write(f"Company: {self.company}\n")
            f.write(f"Location: {self.location}\n")
            f.write(f"Salary: {self.salary or 'Not specified'}\n")
            f.write(f"Posted: {self.date_posted or 'Not specified'}\n")
            f.write(f"Source: {self.source}\n")
            f.write(f"URL: {self.url}\n")
            f.write(f"\n{'='*60}\n")
            f.write(f"DESCRIPTION\n")
            f.write(f"{'='*60}\n\n")
            if self.full_description:
                f.write(self.full_description)
            else:
                f.write(self.description or "No description available.")
            f.write("\n")
        
        return filepath


class JobCollection:
    """Collection of job listings with export functionality."""

    def __init__(self):
        self.jobs: list[Job] = []
        self.run_folder: Optional[str] = None
        self.search_keywords: Optional[str] = None
        self.search_location: Optional[str] = None

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

    def create_run_folder(self, base_folder: str = "scraped_data") -> str:
        """Create a folder for this scraping run named after search params."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create folder name from search params if available
        if self.search_keywords and self.search_location:
            # Sanitize for filesystem
            safe_keywords = re.sub(r'[<>:"/\\|?*]', '', self.search_keywords)[:30].strip().replace(' ', '_')
            safe_location = re.sub(r'[<>:"/\\|?*]', '', self.search_location)[:20].strip().replace(' ', '_')
            folder_name = f"{safe_keywords}_{safe_location}_{timestamp}"
        else:
            folder_name = f"run_{timestamp}"
        
        self.run_folder = os.path.join(base_folder, folder_name)
        os.makedirs(self.run_folder, exist_ok=True)
        return self.run_folder

    def save_all_jobs(self, base_folder: str = "scraped_data") -> str:
        """Save all jobs to individual files in a timestamped folder."""
        if not self.jobs:
            print("No jobs to save.")
            return ""
        
        # Create run folder if not exists
        if not self.run_folder:
            self.create_run_folder(base_folder)
        
        # Create jobs subfolder
        jobs_folder = os.path.join(self.run_folder, "jobs")
        os.makedirs(jobs_folder, exist_ok=True)
        
        # Save each job
        for i, job in enumerate(self.jobs, 1):
            job.to_file(jobs_folder, i)
        
        print(f"Saved {len(self.jobs)} job files to {jobs_folder}")
        return self.run_folder

    def to_csv(self, filename: str = None):
        """Export jobs to CSV file."""
        if not self.jobs:
            print("No jobs to export.")
            return

        # If run_folder exists, save there
        if self.run_folder and not filename:
            filename = os.path.join(self.run_folder, "all_jobs.csv")
        elif not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.jobs[0].to_dict().keys())
            writer.writeheader()
            for job in self.jobs:
                writer.writerow(job.to_dict())
        print(f"Exported {len(self.jobs)} jobs to {filename}")

    def to_json(self, filename: str = None):
        """Export jobs to JSON file."""
        if not self.jobs:
            print("No jobs to export.")
            return

        # If run_folder exists, save there
        if self.run_folder and not filename:
            filename = os.path.join(self.run_folder, "all_jobs.json")
        elif not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([job.to_dict() for job in self.jobs], f, indent=2)
        print(f"Exported {len(self.jobs)} jobs to {filename}")

    def to_compiled_text(self, filename: str = None) -> str:
        """Export all jobs to a single compiled text file for AI analysis."""
        if not self.jobs:
            print("No jobs to compile.")
            return ""

        # If run_folder exists, save there
        if self.run_folder and not filename:
            filename = os.path.join(self.run_folder, "compiled_jobs.txt")
        elif not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"compiled_jobs_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("COMPILED JOB LISTINGS FOR AI ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Search Keywords: {self.search_keywords or 'Not specified'}\n")
            f.write(f"Search Location: {self.search_location or 'Not specified'}\n")
            f.write(f"Total Jobs: {len(self.jobs)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, job in enumerate(self.jobs, 1):
                f.write(f"\n{'='*80}\n")
                f.write(f"JOB #{i}\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"TITLE: {job.title}\n")
                f.write(f"COMPANY: {job.company}\n")
                f.write(f"LOCATION: {job.location}\n")
                f.write(f"SALARY: {job.salary or 'Not specified'}\n")
                f.write(f"SOURCE: {job.source}\n")
                f.write(f"URL: {job.url}\n")
                f.write(f"\n{'-'*40}\n")
                f.write("DESCRIPTION:\n")
                f.write(f"{'-'*40}\n\n")
                
                # Use full description if available, otherwise use snippet
                description = job.full_description if job.full_description else job.description
                f.write(description or "No description available.")
                f.write("\n\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF COMPILED JOB LISTINGS\n")
            f.write("=" * 80 + "\n")
        
        print(f"Compiled {len(self.jobs)} jobs to {filename}")
        return filename

    def to_markdown(self, filename: str = None, bundle_metadata: dict = None) -> str:
        """Export all jobs to a Markdown file for easy reading and AI analysis.
        
        Args:
            filename: Output filename (optional, defaults to run_folder/compiled_jobs.md)
            bundle_metadata: Optional dict with 'keywords_list' and 'bundle_ids' for bundle mode
        """
        if not self.jobs:
            print("No jobs to compile.")
            return ""

        # If run_folder exists, save there
        if self.run_folder and not filename:
            filename = os.path.join(self.run_folder, "compiled_jobs.md")
        elif not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"compiled_jobs_{timestamp}.md"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Compiled Job Listings\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Search Keywords:** {self.search_keywords or 'Not specified'}  \n")
            f.write(f"**Search Location:** {self.search_location or 'Not specified'}  \n")
            f.write(f"**Total Jobs:** {len(self.jobs)}\n\n")
            
            # Bundle metadata (if provided)
            if bundle_metadata:
                keywords_list = bundle_metadata.get("keywords_list") or []
                bundle_ids = bundle_metadata.get("bundle_ids") or []
                if keywords_list:
                    f.write(f"**Search Mode:** Bundle ({len(keywords_list)} phrases)  \n")
                    f.write(f"**Keyword Phrases:**  \n")
                    for kw in keywords_list:
                        f.write(f"- {kw}  \n")
                if bundle_ids:
                    f.write(f"**Bundle IDs:** {', '.join(bundle_ids)}  \n")
                f.write("\n")
            
            f.write("---\n\n")
            
            # Table of contents
            f.write("## Table of Contents\n\n")
            for i, job in enumerate(self.jobs, 1):
                safe_title = job.title.replace('[', '\\[').replace(']', '\\]')
                anchor = f"job-{i}-{job.title.lower().replace(' ', '-')[:30]}"
                f.write(f"{i}. [{safe_title}](#{anchor}) - {job.company}\n")
            f.write("\n---\n\n")
            
            for i, job in enumerate(self.jobs, 1):
                anchor = f"job-{i}-{job.title.lower().replace(' ', '-')[:30]}"
                f.write(f"## Job #{i}: {job.title}\n\n")
                f.write(f"| Field | Value |\n")
                f.write(f"|-------|-------|\n")
                f.write(f"| **Company** | {job.company} |\n")
                f.write(f"| **Location** | {job.location} |\n")
                f.write(f"| **Salary** | {job.salary or 'Not specified'} |\n")
                f.write(f"| **Source** | {job.source} |\n")
                f.write(f"| **URL** | [{job.url[:50]}...]({job.url}) |\n")
                
                # Include scoring if available
                if hasattr(job, 'classification') and job.classification:
                    f.write(f"| **Score** | {job.score} ({job.classification}) |\n")
                    if job.matched_signals:
                        f.write(f"| **Signals** | {job.matched_signals} |\n")
                
                f.write("\n")
                
                f.write("### Description\n\n")
                description = job.full_description if job.full_description else job.description
                f.write(description or "No description available.")
                f.write("\n\n---\n\n")
        
        print(f"Compiled {len(self.jobs)} jobs to {filename}")
        return filename

    def __len__(self):
        return len(self.jobs)

    def __iter__(self):
        return iter(self.jobs)
