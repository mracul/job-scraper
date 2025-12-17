"""
Job Storage Service
Handles loading, saving, and exporting job data.
"""

import os
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

from models import Job

class JobStorage:
    """Service for handling job data persistence and export."""
    
    @staticmethod
    def create_run_folder(base_folder: str, keywords: Optional[str] = None, location: Optional[str] = None) -> str:
        """Create a folder for a scraping run named after search params."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create folder name from search params if available
        if keywords and location:
            # Sanitize for filesystem
            safe_keywords = re.sub(r'[<>:"/\\|?*]', '', keywords)[:30].strip().replace(' ', '_')
            safe_location = re.sub(r'[<>:"/\\|?*]', '', location)[:20].strip().replace(' ', '_')
            folder_name = f"{safe_keywords}_{safe_location}_{timestamp}"
        else:
            folder_name = f"run_{timestamp}"
        
        run_folder = os.path.join(base_folder, folder_name)
        os.makedirs(run_folder, exist_ok=True)
        return run_folder

    @staticmethod
    def save_job_to_file(job: Job, folder: str, index: int) -> str:
        """Save job details to a text file."""
        # Create safe filename
        safe_title = re.sub(r'[<>:"/\\|?*]', '', job.title)[:50]
        safe_company = re.sub(r'[<>:"/\\|?*]', '', job.company)[:30]
        filename = f"{index:03d}_{safe_title}_{safe_company}.txt"
        filepath = os.path.join(folder, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{ '='*60}\n")
            f.write(f"JOB DETAILS\n")
            f.write(f"{ '='*60}\n\n")
            f.write(f"Title: {job.title}\n")
            f.write(f"Company: {job.company}\n")
            f.write(f"Location: {job.location}\n")
            f.write(f"Salary: {job.salary or 'Not specified'}\n")
            f.write(f"Posted: {job.date_posted or 'Not specified'}\n")
            f.write(f"Source: {job.source}\n")
            f.write(f"URL: {job.url}\n")
            f.write(f"\n{ '='*60}\n")
            f.write(f"DESCRIPTION\n")
            f.write(f"{ '='*60}\n\n")
            if job.full_description:
                f.write(job.full_description)
            else:
                f.write(job.description or "No description available.")
            f.write("\n")
        
        return filepath

    @staticmethod
    def save_all_jobs(jobs: List[Job], run_folder: str) -> None:
        """Save all jobs to individual files in the run folder."""
        if not jobs:
            return
        
        # Create jobs subfolder
        jobs_folder = os.path.join(run_folder, "jobs")
        os.makedirs(jobs_folder, exist_ok=True)
        
        # Save each job
        for i, job in enumerate(jobs, 1):
            JobStorage.save_job_to_file(job, jobs_folder, i)

    @staticmethod
    def to_csv(jobs: List[Job], filename: str) -> None:
        """Export jobs to CSV file."""
        if not jobs:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            # Get fields from first job
            fieldnames = jobs[0].to_dict().keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for job in jobs:
                writer.writerow(job.to_dict())

    @staticmethod
    def to_json(jobs: List[Job], filename: str) -> None:
        """Export jobs to JSON file."""
        if not jobs:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([job.to_dict() for job in jobs], f, indent=2)

    @staticmethod
    def to_jsonl(jobs: List[Job], filename: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Export jobs to JSONL (one JSON object per line)."""
        if not jobs:
            return

        def _extract_source_id(source: str, url: str) -> Union[str, None]:
            raw = (url or "").strip()
            if not raw:
                return None
            if (source or "").strip().lower() == "seek":
                m = re.search(r"jobid=(\d+)", raw, re.IGNORECASE)
                if m:
                    return m.group(1)
                url2 = raw.split("#", 1)[0].split("?", 1)[0]
                m = re.search(r"/job/(\d+)", url2)
                if m:
                    return m.group(1)
            return None

        scraped_at = datetime.now().isoformat(timespec="seconds")
        
        with open(filename, "w", encoding="utf-8") as f:
            if metadata:
                # Add generated timestamp if not present
                if "generated" not in metadata:
                    metadata["generated"] = scraped_at
                f.write(json.dumps({"_meta": metadata}, ensure_ascii=False) + "\n")
            
            for job in jobs:
                obj = job.to_dict()
                obj["description"] = job.full_description or job.description or ""
                obj["scraped_at"] = scraped_at
                obj["source_id"] = obj.get("source_id") or _extract_source_id(obj.get("source"), obj.get("url"))
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    @staticmethod
    def to_compiled_text(jobs: List[Job], filename: str, keywords: str, location: str) -> None:
        """Export all jobs to a single compiled text file for AI analysis."""
        if not jobs:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("COMPILED JOB LISTINGS FOR AI ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Search Keywords: {keywords or 'Not specified'}\n")
            f.write(f"Search Location: {location or 'Not specified'}\n")
            f.write(f"Total Jobs: {len(jobs)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, job in enumerate(jobs, 1):
                f.write(f"\n{ '='*80}\n")
                f.write(f"JOB #{i}\n")
                f.write(f"{ '='*80}\n\n")
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

    @staticmethod
    def to_markdown(jobs: List[Job], filename: str, keywords: str, location: str, bundle_metadata: Optional[Dict] = None) -> None:
        """Export all jobs to a Markdown file."""
        if not jobs:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Compiled Job Listings\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + "  \n")
            f.write(f"**Search Keywords:** {keywords or 'Not specified'}  \n")
            f.write(f"**Search Location:** {location or 'Not specified'}  \n")
            f.write(f"**Total Jobs:** {len(jobs)}\n\n")
            
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
            for i, job in enumerate(jobs, 1):
                safe_title = job.title.replace('[', '\\[').replace(']', '\]')
                anchor = f"job-{i}-{job.title.lower().replace(' ', '-')[:30]}"
                f.write(f"{i}. [{safe_title}](#{anchor}) - {job.company}\n")
            f.write("\n---\n\n")
            
            for i, job in enumerate(jobs, 1):
                anchor = f"job-{i}-{job.title.lower().replace(' ', '-')[:30]}"
                f.write(f"## Job #{i}: {job.title}\n\n")
                f.write(f"| Field | Value |\n")
                f.write(f"|-------|-------|\n")
                f.write(f"| **Company** | {job.company} |\n")
                f.write(f"| **Location** | {job.location} |\n")
                f.write(f"| **Salary** | {job.salary or 'Not specified'} |\n")
                f.write(f"| **Source** | {job.source} |\n")
                f.write(f"| **URL** | [{job.url[:50]}]({job.url}) |\n")
                
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
