"""
Job Requirements Analyzer
Extracts and analyzes certifications, qualifications, skills, and experience 
requirements from compiled job listings.
"""

import re
import os
from collections import Counter
from pathlib import Path
import json
import hashlib
from datetime import datetime
import math
from bisect import bisect_right
import unicodedata
from requirements_config import (
    CERTIFICATION_PATTERNS,
    MICROSOFT_CERT_CODE_MAP,
    EDUCATION_PATTERNS,
    TECHNICAL_SKILLS,
    SOFT_SKILLS,
    EXPERIENCE_PATTERNS,
    SUPPORT_LEVELS,
    WORK_ARRANGEMENTS,
    BENEFITS,
    OTHER_REQUIREMENTS
)


def norm(s: str) -> str:
    """Normalize string for better deduplication."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def canonicalize_url(url: str) -> str:
    """Normalize URL for stable deduplication."""
    url = (url or "").strip()
    if not url:
        return ""
    url = url.split("#", 1)[0].split("?", 1)[0]
    return url.strip()


def _maybe_extract_source_id(source: str, url: str) -> str | None:
    """Best-effort source_id extractor for common job URL formats."""
    raw = (url or "").strip()
    if not raw:
        return None
    src = norm(source)
    if src == "seek":
        # First try query-based IDs before stripping query params.
        m = re.search(r"\bjobid=(\d+)\b", raw, re.IGNORECASE)
        if m:
            return m.group(1)

        # Then try canonical path-based IDs.
        url2 = canonicalize_url(raw)
        m = re.search(r"/job/(\d+)\b", url2)
        if m:
            return m.group(1)
    return None


# Context keywords
REQUIRED_WORDS = [
    'required',
    'must have',
    'must',
    'need',
    'need to',
    'minimum requirements',
    'mandatory',
    'essential',
    'key criteria',
    'selection criteria',
    'you will have',
    "you'll have",
    'to succeed in this role',
]
PREFERRED_WORDS = [
    'preferred',
    'desirable',
    'nice to have',
    'advantage',
    'beneficial',
    'highly regarded',
    'highly desirable',
    'an advantage',
    'would be advantageous',
]
BONUS_WORDS = [
    'bonus',
    'plus',
    'a plus',
    'would be great',
    'great if',
    'helpful if',
]
SECTION_REQUIRED = [
    'requirements',
    'minimum requirements',
    'essential',
    'mandatory',
    'key requirements',
    'skills required',
    'skills and experience',
    'what you will bring',
    "what you'll bring",
    'to succeed in this role',
    'selection criteria',
]
SECTION_PREFERRED = [
    'desirable',
    'nice to have',
    'preferred',
    'highly regarded',
    'highly desirable',
    'advantageous',
]
class JobRequirementsAnalyzer:
    """Analyzes job listings to extract commonly requested requirements."""

    def __init__(self):
        # Certification patterns - specific named certifications
        self.certification_patterns = CERTIFICATION_PATTERNS
        
        # Microsoft certification code to friendly name mapping
        self.microsoft_cert_code_map = MICROSOFT_CERT_CODE_MAP
        
        # Education/Qualification patterns
        self.education_patterns = EDUCATION_PATTERNS
        
        # Technical skills patterns
        self.technical_skills = TECHNICAL_SKILLS
        
        # Soft skills patterns
        self.soft_skills = SOFT_SKILLS
        
        # Experience patterns
        self.experience_patterns = EXPERIENCE_PATTERNS
        
        # Support levels and ITSM processes
        self.support_levels = SUPPORT_LEVELS
        
        # Work arrangements
        self.work_arrangements = WORK_ARRANGEMENTS
        
        # Benefits/Perks
        self.benefits = BENEFITS
        
        # Other requirements
        self.other_requirements = OTHER_REQUIREMENTS


        # Pre-compile regex patterns once (major speed-up on large runs).
        self._compiled_patterns = {
            'certifications': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.certification_patterns.items()],
            'education': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.education_patterns.items()],
            'technical_skills': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.technical_skills.items()],
            'soft_skills': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.soft_skills.items()],
            'experience': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.experience_patterns.items()],
            'support_levels': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.support_levels.items()],
            'work_arrangements': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.work_arrangements.items()],
            'benefits': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.benefits.items()],
            'other_requirements': [(n, re.compile(p, re.IGNORECASE)) for n, p in self.other_requirements.items()],
        }
    def _context_label_and_weight(self, match_start: int, match_end: int, job_text: str, lower_job_text: str) -> tuple[str, float]:
        """Determine context label and weight for a match based on its position and surrounding text. 
        
        Returns:
            (label, weight) where label is 'required', 'preferred', 'bonus', 'context'
            and weight is a multiplier (1.0 = required, 0.8 = preferred, 0.5 = bonus, 0.2 = context)
        """
        # Get window around match (100 chars before and after)
        # Use lower_job_text which is already lowercased
        window_start = max(0, match_start - 100)
        window_end = min(len(job_text), match_end + 100)
        window = lower_job_text[window_start:window_end]
        
        # Look back to start of the current line for bullet detection
        # Use original job_text for finding newlines
        line_start = job_text.rfind('\n', 0, match_start) + 1
        line = job_text[line_start:match_start]
        has_bullet = bool(re.match(r'^\s*([-•*·]|\d+[\.\)])\s+', line))
        
        # If a nearby section header suggests intent, boost confidence.
        # (Section headers are often phrased without explicit "required/preferred" keywords.)
        if any(s in window for s in SECTION_REQUIRED):
            # If the same window strongly signals "preferred", respect that.
            if any(w in window for w in PREFERRED_WORDS) and not any(w in window for w in REQUIRED_WORDS):
                return ('preferred', 0.8)
            return ('required', 1.0)
        if any(s in window for s in SECTION_PREFERRED):
            return ('preferred', 0.8)
        # Otherwise fall back to keyword-only (more conservative)
        if any(w in window for w in REQUIRED_WORDS):
            return ('required', 1.0)
        if any(w in window for w in PREFERRED_WORDS):
            return ('preferred', 0.8)
        if any(w in window for w in BONUS_WORDS):
            return ('bonus', 0.5)
        
        # If in bullet point, assume required unless contradicted
        if has_bullet:
            return ('required', 1.0)
        
        # Default to context (weakest)
        return ('context', 0.2)

    def _passes_term_gate(
        self,
        term: str,
        matched: str,
        lower_job_text: str,
        category: str,
        match_start: int,
        match_end: int,
    ) -> bool:
        """Apply term-specific gating logic to filter out false positives. 
        
        Uses a local window around the match instead of the entire job text.
        
        Returns True if the term should be counted, False if it's likely a false positive.
        """
        # Get local window around match (200 chars before and after for gating)
        window_start = max(0, match_start - 200)
        window_end = min(len(lower_job_text), match_end + 200)
        window = lower_job_text[window_start:window_end]
        term_lower = term.lower()
        
        # Education gating - avoid false positives in non-education contexts
        if category == 'education':
            # Skip if term appears in unrelated contexts
            if term_lower in ['diploma', 'certificate'] and any(word in window for word in ['driver', 'license', 'driving']):
                return False
            if term_lower == 'tafe' and 'tafe' in window and not any(edu_word in window for edu_word in ['education', 'qualification', 'study', 'degree']):
                return False
        
        # Technical skills gating - more permissive now
        elif category == 'technical_skills':
            # For vendor names, only gate if clearly company boilerplate (not requirements)
            if term_lower in ['cisco', 'fortinet', 'meraki', 'unifi', 'vmware', 'citrix', 'hp/hpe', 'dell', 'lenovo']:
                # Skip only if explicitly in "about us" / company description context
                company_context_phrases = ['we are', 'our company', 'about us', 'we use', 'our partner', 'partner with']
                if any(phrase in window for phrase in company_context_phrases):
                    # But still count if there's also a requirement signal
                    req_signals = ['experience', 'knowledge', 'skills', 'required', 'preferred', 'familiar', 'understanding', 'proficien']
                    if not any(sig in window for sig in req_signals):
                        return False
        
        # Experience gating
        elif category == 'experience':
            # Skip MSP mentions when it's clearly company context (not a candidate requirement)
            if term in ['MSP', 'MSP Experience']:
                has_company_context = any(
                    p in window
                    for p in [
                        'our msp',
                        'we are an msp',
                        'msp company',
                        'msp firm',
                        'msp provider',
                        'managed service provider',
                        'managed services provider',
                        'we are a managed service provider',
                        'join our managed services',
                    ]
                )
                has_requirement = any(
                    w in window
                    for w in [
                        'experience',
                        'background',
                        'required',
                        'preferred',
                        'looking for',
                        'candidate',
                    ]
                )
                if has_company_context and not has_requirement:
                    return False
            return True
        
        # Support levels gating
        elif category == 'support_levels':
            # Skip generic mentions that aren't about support levels
            if term_lower in ['level 1', 'level 2', 'level 3'] and not any(support_word in window for support_word in ['support', 'tier', 'line', 'help desk', 'service desk']):
                return False
        
        return True

    def extract_jobs_from_markdown(self, filepath: str) -> tuple[list, dict]:
        """Extract individual job descriptions and search metadata from compiled markdown file.

        Returns:
            (jobs, metadata) where metadata contains 'keywords', 'location', 'generated', etc.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract search metadata from header (before first job)
        metadata = {
            'keywords': None,
            'location': None,
            'generated': None,
            'search_mode': None,
        }
        header_match = re.search(r'^(.*?)(?=---\s*\n\s*## Job #)', content, re.DOTALL)
        if header_match:
            header = header_match.group(1)
            kw_match = re.search(r'\*\*Search Keywords:\*\*\s*(.+)', header)
            if kw_match:
                metadata['keywords'] = kw_match.group(1).strip()
            loc_match = re.search(r'\*\*Search Location:\*\*\s*(.+)', header)
            if loc_match:
                metadata['location'] = loc_match.group(1).strip()
            gen_match = re.search(r'\*\*Generated:\*\*\s*(.+)', header)
            if gen_match:
                metadata['generated'] = gen_match.group(1).strip()
            mode_match = re.search(r'\*\*Search Mode:\*\*\s*(.+)', header)
            if mode_match:
                metadata['search_mode'] = mode_match.group(1).strip()
        
        # Split by job headers (primary method)
        job_sections = re.split(r'---\s*\n\s*## Job #\d+:', content)
        
        # Fallback: if markdown splitting didn't work, try plaintext "JOB #" blocks
        if len(job_sections) <= 1:
            job_sections = re.split(r'={10,}\s*\nJOB\s*#\d+\s*\n={10,}', content)
        
        jobs = []
        for i, section in enumerate(job_sections[1:], 1):  # Skip header
            # Extract title - try multiple formats
            title = f"Job {i}"
            lines = section.strip().split('\n')
            
            # Try markdown format first
            if lines and not lines[0].startswith('**'):
                title = lines[0].strip()
            
            # Try plaintext format
            title_match = re.search(r'TITLE:\s*(.+)', section, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract company - try multiple formats
            company = "Unknown"
            
            # Try markdown table format
            company_match = re.search(r'\*\*Company\*\*\s*\|\s*([^\|]+)', section)
            if company_match:
                company = company_match.group(1).strip()
            else:
                # Try plaintext format
                company_match = re.search(r'COMPANY:\s*(.+)', section, re.IGNORECASE)
                if company_match:
                    company = company_match.group(1).strip()

            # Extract URL/source when present (enables stronger dedupe + reporting)
            url = None
            source = None

            url_match = re.search(r'\*\*URL\*\*\s*\|\s*\[[^\]]*\]\(([^)]+)\)', section)
            if url_match:
                url = url_match.group(1).strip()
            else:
                url_match = re.search(r'URL:\s*(.+)', section, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1).strip()

            src_match = re.search(r'\*\*Source\*\*\s*\|\s*([^\|]+)', section)
            if src_match:
                source = src_match.group(1).strip()
            else:
                src_match = re.search(r'SOURCE:\s*(.+)', section, re.IGNORECASE)
                if src_match:
                    source = src_match.group(1).strip()

            source_id = _maybe_extract_source_id(source or "", url or "")

            jobs.append({
                'id': i,
                'title': title,
                'company': company,
                'description': section,
                'url': url,
                'source': source,
                'source_id': source_id,
            })

        return jobs, metadata

    def extract_jobs_from_jsonl(self, filepath: str) -> tuple[list, dict]:
        """Load jobs from JSONL (one job object per line, optional _meta line)."""
        jobs: list[dict] = []
        metadata: dict = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("_meta"):
                    metadata = obj["_meta"] or {}
                    continue
                if not isinstance(obj, dict):
                    continue

                description = obj.get("description")
                if not description:
                    description = obj.get("full_description") or obj.get("text") or ""

                url = obj.get("url")
                source = obj.get("source")
                source_id = obj.get("source_id") or _maybe_extract_source_id(source or "", url or "")

                jobs.append(
                    {
                        "id": len(jobs) + 1,
                        "title": obj.get("title") or f"Job {len(jobs) + 1}",
                        "company": obj.get("company") or "Unknown",
                        "description": description,
                        "url": url,
                        "source": source,
                        "source_id": source_id,
                    }
                )
        return jobs, metadata

    def extract_jobs(self, filepath: str) -> tuple[list, dict]:
        """Extract jobs from a supported input format (.md or .jsonl)."""
        suffix = Path(filepath).suffix.lower()
        if suffix == ".jsonl":
            return self.extract_jobs_from_jsonl(filepath)
        return self.extract_jobs_from_markdown(filepath)

    def analyze_job(self, job_text: str) -> dict:
        """Analyze a single job description for all requirement types. 
        
        Returns dict with 'presence' (simple counts) and 'weighted' (context-aware scores)."""
        results = {
            'presence': {
                'certifications': [],
                'education': [],
                'technical_skills': [],
                'soft_skills': [],
                'experience': [],
                'support_levels': [],
                'work_arrangements': [],
                'benefits': [],
                'other_requirements': []
            },
            'weighted': {
                'certifications': [],
                'education': [],
                'technical_skills': [],
                'soft_skills': [],
                'experience': [],
                'support_levels': [],
                'work_arrangements': [],
                'benefits': [],
                'other_requirements': []
            }
        }
        
        # Pre-compute lowercase text for efficient window slicing
        lower_job_text = job_text.lower()
        

        # Track best per-term weighting per job to avoid multi-mention inflation
        best_weighted = {k: {} for k in results['weighted'].keys()}
        # Helper to process a category
        def process_category(category_name: str, patterns_dict: dict):
            # Prefer pre-compiled regex for speed; fall back to compiling on the fly.
            compiled = getattr(self, "_compiled_patterns", {}).get(category_name)
            if compiled is None:
                compiled = [(n, re.compile(p, re.IGNORECASE)) for n, p in patterns_dict.items()]

            def upsert_weighted(term: str, label: str, weight: float) -> None:
                # Keep the strongest signal for this term within this job.
                score = 1.0 * weight
                prev = best_weighted[category_name].get(term)
                if (prev is None) or (score > prev.get("score", 0)):
                    best_weighted[category_name][term] = {
                        "term": term,
                        "weight": weight,
                        "label": label,
                        "score": score,
                    }

            for name, cre in compiled:
                for match in cre.finditer(job_text):
                    # Apply term gating using lower_job_text
                    if not self._passes_term_gate(
                        name,
                        match.group(0),
                        lower_job_text,
                        category_name,
                        match.start(),
                        match.end(),
                    ):
                        continue

                    # Get context and weight using lower_job_text
                    label, weight = self._context_label_and_weight(
                        match.start(),
                        match.end(),
                        job_text,
                        lower_job_text,
                    )

                    # For certifications, track family bucket and optionally specific Microsoft codes
                    if category_name == "certifications":
                        family = name
                        if family not in results["presence"][category_name]:
                            results["presence"][category_name].append(family)
                        upsert_weighted(family, label, weight)

                        # If it's a Microsoft code, record the specific code too (without blowing up families)
                        raw = match.group(0).strip()
                        code = raw.upper()
                        if code in self.microsoft_cert_code_map:
                            specific = f"{code} ({self.microsoft_cert_code_map[code]})"
                            if specific not in results["presence"][category_name]:
                                results["presence"][category_name].append(specific)
                            upsert_weighted(specific, label, weight)

                    else:
                        if name not in results["presence"][category_name]:
                            results["presence"][category_name].append(name)
                        upsert_weighted(name, label, weight)

        process_category('certifications', self.certification_patterns)
        process_category('education', self.education_patterns)
        process_category('technical_skills', self.technical_skills)
        process_category('soft_skills', self.soft_skills)
        process_category('experience', self.experience_patterns)
        process_category('support_levels', self.support_levels)
        process_category('work_arrangements', self.work_arrangements)
        process_category('benefits', self.benefits)
        process_category('other_requirements', self.other_requirements)

        # Collapse best-weighted picks into the output (one entry per term per job).
        for cat, best in best_weighted.items():
            results['weighted'][cat] = list(best.values())

        return results

    def analyze_all_jobs(self, jobs: list, *, dedupe: bool = True) -> dict:
        """Analyze all jobs and aggregate results with presence counts and weighted scores.
        
        Args:
            jobs: List of job dicts with 'id', 'title', 'company', 'description'.
            dedupe: If True, deduplicate jobs by (title, company) before analysis.
        """
        # Deduplicate by strongest available key - keeps first occurrence
        if dedupe:
            seen: set[tuple] = set()
            unique_jobs = []
            for job in jobs:
                src = norm(job.get("source") or "")
                sid = norm(job.get("source_id") or "")
                url = canonicalize_url(job.get("url") or "")

                if src and sid:
                    key = ("src_id", src, sid)
                elif url:
                    key = ("url", norm(url))
                else:
                    desc = job.get("description") or ""
                    if desc:
                        fp = hashlib.sha1(norm(desc)[:3000].encode("utf-8")).hexdigest()
                        key = ("desc_fp", fp)
                    else:
                        key = (
                            "title_company",
                            norm(job.get("title") or ""),
                            norm(job.get("company") or ""),
                        )

                if key not in seen:
                    seen.add(key)
                    unique_jobs.append(job)
            jobs = unique_jobs
        
        # Initialize counters for presence (simple counts)
        presence_results = {
            'certifications': Counter(),
            'education': Counter(),
            'technical_skills': Counter(),
            'soft_skills': Counter(),
            'experience': Counter(),
            'support_levels': Counter(),
            'work_arrangements': Counter(),
            'benefits': Counter(),
            'other_requirements': Counter()
        }
        
        # Initialize for weighted scores (sum of individual term scores)
        weighted_results = {
            'certifications': Counter(),
            'education': Counter(),
            'technical_skills': Counter(),
            'soft_skills': Counter(),
            'experience': Counter(),
            'support_levels': Counter(),
            'work_arrangements': Counter(),
            'benefits': Counter(),
            'other_requirements': Counter()
        }
        
        job_details = []
        # Inverted index for fast drill-down: category -> term -> [job_id]
        term_index: dict[str, dict[str, list[int]]] = {
            'certifications': {},
            'education': {},
            'technical_skills': {},
            'soft_skills': {},
            'experience': {},
            'support_levels': {},
            'work_arrangements': {},
            'benefits': {},
            'other_requirements': {},
        }
        
        for job in jobs:
            job_analysis = self.analyze_job(job['description'])
            job_details.append({
                'id': job['id'],
                'title': job['title'],
                'company': job['company'],
                'requirements': job_analysis
            })

            # Build inverted index from presence data
            for category, items in job_analysis['presence'].items():
                for item in items:
                    bucket = term_index.setdefault(category, {}).setdefault(item, [])
                    bucket.append(job['id'])
            
            # Aggregate presence counts
            for category, items in job_analysis['presence'].items():
                for item in items:
                    presence_results[category][item] += 1
            
            # Aggregate weighted scores
            for category, weighted_items in job_analysis['weighted'].items():
                for item_data in weighted_items:
                    term = item_data['term']
                    score = item_data['score']
                    weighted_results[category][term] += score
        
        return {
            'presence': {k: dict(v.most_common()) for k, v in presence_results.items()},
            'weighted': {k: dict(v.most_common()) for k, v in weighted_results.items()},
            'job_details': job_details,
            'term_index': term_index,
            'total_jobs': len(jobs)
        }

    def generate_report(
        self,
        analysis: dict,
        output_dir: str = None,
        *, 
        search_metadata: dict | None = None,
    ) -> str:
        """Generate a comprehensive requirements report. 
        
        Args:
            analysis: Output from analyze_all_jobs().
            output_dir: Directory to save report files (optional).
            search_metadata: Dict with 'keywords', 'location', etc. from extract_jobs_from_markdown().
        """
        total_jobs = analysis['total_jobs']
        presence_summary = analysis['presence']
        weighted_summary = analysis['weighted']
        meta = search_metadata or {}
        
        report_lines = [
            "=" * 70,
            "JOB REQUIREMENTS ANALYSIS REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Jobs Analyzed: {total_jobs}",
            f"Search Keywords: {meta.get('keywords') or 'Not specified'}",
            f"Search Location: {meta.get('location') or 'Not specified'}",
            "=" * 70,
            ""
        ]
        
        # Helper to format section with both presence and weighted metrics
        def format_section(title: str, presence_data: dict, weighted_data: dict, min_count: int = 1, max_items: int = 40):
            lines = [f"\n{'=' * 50}", f"{title}", "=" * 50]
            if not presence_data and not weighted_data:
                lines.append("  No items found")
                return lines

            # Combine and sort by weighted score (primary), then presence count (secondary)
            combined_items = {}
            for item in set(presence_data.keys()) | set(weighted_data.keys()):
                combined_items[item] = {
                    "presence": float(presence_data.get(item, 0)),
                    "weighted": float(weighted_data.get(item, 0)),
                }

            sorted_items = sorted(
                combined_items.items(),
                key=lambda x: (x[1]["weighted"], x[1]["presence"]),
                reverse=True,
            )

            shown = 0
            eligible = 0
            for item, metrics in sorted_items:
                presence_count = int(metrics["presence"])
                weighted_score = float(metrics["weighted"])
                if presence_count < min_count:
                    continue
                eligible += 1

                if shown >= max_items:
                    break
                shown += 1

                presence_pct = (presence_count / total_jobs) * 100 if total_jobs else 0.0
                avg_weight = weighted_score / presence_count if presence_count else 0.0

                # Keep lines compact to reduce report size and UI overflow.
                item_disp = item if len(item) <= 32 else (item[:29] + "…")

                bar_len = min(20, int(presence_pct / 5))
                bar = "█" * bar_len

                lines.append(
                    f"  {item_disp:32} {presence_count:3} jobs ({presence_pct:5.1f}%) | "
                    f"Score: {weighted_score:6.1f} (avg: {avg_weight:.2f}) {bar}"
                )

            if eligible > shown:
                lines.append(f"  … showing top {shown} of {eligible} items")

            return lines


        
        # Add each section
        report_lines.extend(format_section("CERTIFICATIONS", 
                                         presence_summary['certifications'], 
                                         weighted_summary['certifications'], max_items=35))
        report_lines.extend(format_section("EDUCATION / QUALIFICATIONS", 
                                         presence_summary['education'], 
                                         weighted_summary['education'], max_items=20))
        report_lines.extend(format_section("TECHNICAL SKILLS (Top 25)", 
                                         dict(Counter(presence_summary['technical_skills']).most_common(25)),
                                         dict(Counter(weighted_summary['technical_skills']).most_common(25))))
        report_lines.extend(format_section("SOFT SKILLS", 
                                         presence_summary['soft_skills'], 
                                         weighted_summary['soft_skills'], max_items=25))
        report_lines.extend(format_section("EXPERIENCE REQUIREMENTS", 
                                         presence_summary['experience'], 
                                         weighted_summary['experience'], max_items=20))
        report_lines.extend(format_section("SUPPORT LEVELS & ITSM", 
                                         presence_summary.get('support_levels', {}), 
                                         weighted_summary.get('support_levels', {}), max_items=15))
        report_lines.extend(format_section("WORK ARRANGEMENTS", 
                                         presence_summary.get('work_arrangements', {}), 
                                         weighted_summary.get('work_arrangements', {}), max_items=12))
        report_lines.extend(format_section("BENEFITS & PERKS", 
                                         presence_summary.get('benefits', {}), 
                                         weighted_summary.get('benefits', {}), max_items=15))
        report_lines.extend(format_section("OTHER REQUIREMENTS", 
                                         presence_summary['other_requirements'], 
                                         weighted_summary['other_requirements'], max_items=20))
        
        # Key insights
        report_lines.extend([
            "",
            "=" * 50,
            "KEY INSIGHTS",
            "=" * 50,
        ])
        
        # Most requested items (Presence-based)
        all_tech = presence_summary.get('technical_skills', {})
        if all_tech:
            top_3_tech = Counter(all_tech).most_common(3)
            report_lines.append(f"\n  Top 3 Technical Skills (presence):")
            for skill, count in top_3_tech:
                report_lines.append(f"    - {skill}: {count} jobs ({(count/total_jobs)*100:.1f}%)")

        all_certs = presence_summary.get('certifications', {})
        if all_certs:
            cert_counts = Counter(all_certs)

            code_re = re.compile(r'^(?:MS|AZ|SC|MD|PL|DP|MB|AI|AD|WS)-\d{3}\b', re.IGNORECASE)
            top_3_codes = [(k, v) for (k, v) in cert_counts.most_common() if code_re.match(k)][:3]
            top_3_families = [(k, v) for (k, v) in cert_counts.most_common() if not code_re.match(k)][:3]

            if top_3_codes:
                report_lines.append(f"\n  Top 3 Certification Codes (presence):")
                for cert, count in top_3_codes:
                    report_lines.append(f"    - {cert}: {count} jobs ({(count/total_jobs)*100:.1f}%)")

            if top_3_families:
                report_lines.append(f"\n  Top 3 Certification Buckets (presence):")
                for cert, count in top_3_families:
                    report_lines.append(f"    - {cert}: {count} jobs ({(count/total_jobs)*100:.1f}%)")
        
        report = "\n".join(report_lines)
        
        # Save report if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            # Save text report
            report_path = os.path.join(output_dir, "requirements_analysis.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Save JSON data
            json_path = os.path.join(output_dir, "requirements_analysis.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2)

            # Save drill-down index (smaller + optimized for UI)
            index = {
                'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_jobs': analysis.get('total_jobs', 0),
                'jobs': {
                    str(j['id']): {
                        'id': j['id'],
                        'title': j.get('title'),
                        'company': j.get('company'),
                        'requirements': j.get('requirements', {}),
                    }
                    for j in analysis.get('job_details', [])
                },
                'term_index': analysis.get('term_index', {}),
            }
            index_path = os.path.join(output_dir, "requirements_index.json")
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)
            
            print(f"\nReports saved to:")
            print(f"  - {report_path}")
            print(f"  - {json_path}")
            print(f"  - {index_path}")
        
        return report


def find_latest_run() -> str:
    """Find the most recent scraper run folder."""
    scraped_data_dir = Path(__file__).parent / "scraped_data"
    if not scraped_data_dir.exists():
        return None

    # Support both legacy run_YYYYMMDD_* folders and newer keyword_location_timestamp folders.
    candidates: list[Path] = [p for p in scraped_data_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


def main():
    """Main entry point."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Analyze job requirements from compiled listings")
    parser.add_argument('--input', '-i', help="Path to compiled_jobs.md or jobs.jsonl")
    parser.add_argument('--output', '-o', help="Output directory for reports")
    args = parser.parse_args()

    # Best-effort: avoid UnicodeEncodeError on Windows consoles (cp1252, etc.)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        # Try to find latest run
        latest_run = find_latest_run()
        if latest_run:
            jsonl = os.path.join(latest_run, "jobs.jsonl")
            md = os.path.join(latest_run, "compiled_jobs.md")
            if os.path.exists(jsonl):
                input_file = jsonl
            else:
                input_file = md
        else:
            input_file = None
    
    if not input_file or not os.path.exists(input_file):
        print("Error: Could not find an input file (compiled_jobs.md or jobs.jsonl)")
        print("Please specify the path with --input or run the scraper first.")
        return
    
    print(f"Analyzing: {input_file}")
    
    # Determine output directory
    output_dir = args.output or os.path.dirname(input_file)
    
    # Run analysis
    analyzer = JobRequirementsAnalyzer()
    jobs, search_metadata = analyzer.extract_jobs(input_file)
    
    print(f"Found {len(jobs)} job listings")
    if search_metadata.get('keywords'):
        print(f"  Keywords: {search_metadata['keywords']}")
    if search_metadata.get('location'):
        print(f"  Location: {search_metadata['location']}")
    
    analysis = analyzer.analyze_all_jobs(jobs, dedupe=True)
    dedupe_count = len(jobs) - analysis['total_jobs']
    if dedupe_count > 0:
        print(f"  Deduplicated: {dedupe_count} duplicates removed")
    
    report = analyzer.generate_report(analysis, output_dir, search_metadata=search_metadata)
    
    try:
        print(report)
    except UnicodeEncodeError:
        # If the console can't render some characters, print a safe version
        safe = str(report).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        print(safe)


if __name__ == "__main__":
    main()