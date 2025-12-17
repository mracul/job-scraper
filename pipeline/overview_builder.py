"""
Overview pipeline builder.
Creates overview data structures used by both UI and AI components.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from ui.constants import CATEGORY_LABELS


class OverviewBuilder:
    """
    Builds overview data structures from run data.

    Processes job data to create category rankings, market context,
    and other overview metrics used by both UI components and AI analysis.
    """

    def __init__(self):
        pass

    def build_overview_from_runs(
        self,
        runs: List[Dict[str, Any]],
        cutoff_days: int = 180,
        half_life_days: int = 30,
        top_n: int = 10
    ) -> Dict[str, Any]:
        """
        Build overview payload from multiple runs with weighted merging.

        Args:
            runs: List of run dictionaries
            cutoff_days: Age cutoff for recent jobs
            half_life_days: Half-life for recency weighting
            top_n: Number of top items to show

        Returns:
            Overview payload dictionary
        """
        return self._build_overview_payload(
            runs=runs,
            cutoff_days=cutoff_days,
            half_life_days=half_life_days,
            top_n=top_n
        )

    def _build_overview_payload(self, *, runs: list[dict], cutoff_days: int, half_life_days: int, top_n: int) -> dict:
        """Build overview payload with weighted merge using half-life decay model.
        
        Weight formula: w_i = 2^(-delta_i / H)
        where delta_i = age in days from t_ref, H = half_life_days
        """
        from storage.job_store import load_analysis  # Import here to avoid circular imports
        
        usable_runs: list[dict] = []
        analyses: list[dict] = []
        run_timestamps: list[float] = []

        for r in runs:
            run_path = Path(r.get("path"))
            analysis = load_analysis(run_path)
            if not analysis:
                continue
            total_jobs = int(analysis.get("total_jobs", 0) or 0)
            summary = analysis.get("summary", {}) or analysis.get("presence", {}) or {}
            if not isinstance(summary, dict) or (not summary):
                continue
            run_ts = r.get("timestamp")
            if not isinstance(run_ts, datetime):
                continue
            run_timestamps.append(run_ts.timestamp())
            usable_runs.append(
                {
                    "name": str(r.get("name") or run_path.name),
                    "path": str(run_path),
                    "timestamp": run_ts.isoformat(),
                    "job_count": int(r.get("job_count", total_jobs) or total_jobs),
                    "total_jobs": total_jobs,
                }
            )
            analyses.append({"total_jobs": total_jobs, "summary": summary, "timestamp": run_ts})

        if not usable_runs:
            return {
                "generated_at": datetime.now().isoformat(),
                "runs": [],
                "meta": {
                    "cutoff_days": cutoff_days,
                    "half_life_days": half_life_days,
                    "raw_jobs": 0,
                    "effective_jobs": 0.0,
                    "min_ts": None,
                    "max_ts": None,
                },
                "weighted_summary": {},
                "top_terms": {},
                "series": [],
            }

        # t_ref = max timestamp among usable runs
        t_ref = max(run_timestamps)
        t_ref_dt = datetime.fromtimestamp(t_ref)
        min_ts = min(run_timestamps)
        min_ts_dt = datetime.fromtimestamp(min_ts)

        # Compute weights and weighted merge
        raw_jobs = 0
        effective_jobs = 0.0
        weighted_counts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for analysis in analyses:
            run_ts = analysis["timestamp"]
            total_jobs = analysis["total_jobs"]
            summary = analysis["summary"]
            weight = self._compute_run_weight(run_ts, t_ref, half_life_days)

            raw_jobs += total_jobs
            effective_jobs += weight * total_jobs

            for cat_key in CATEGORY_LABELS.keys():
                cat_map = summary.get(cat_key, {}) or {}
                if not isinstance(cat_map, dict):
                    continue
                for term, count in cat_map.items():
                    if isinstance(count, (int, float)):
                        weighted_counts[cat_key][term] += weight * count

        # Build top_terms and weighted_summary
        top_terms = {}
        weighted_summary = {}

        for cat_key, term_weights in weighted_counts.items():
            # Sort by weighted count descending
            sorted_terms = sorted(term_weights.items(), key=lambda x: x[1], reverse=True)
            top_terms[cat_key] = [
                {"term": term, "weighted_count": count, "rank": i+1}
                for i, (term, count) in enumerate(sorted_terms[:top_n])
            ]
            
            # Build weighted_summary (term -> {weighted_count, ...})
            weighted_summary[cat_key] = {
                term: {"weighted_count": count}
                for term, count in sorted_terms
            }

        # Build series data for visualization
        series = []
        for cat_key, terms in top_terms.items():
            for term_data in terms:
                series.append({
                    "category": cat_key,
                    "term": term_data["term"],
                    "weighted_count": term_data["weighted_count"],
                    "rank": term_data["rank"]
                })

        return {
            "generated_at": datetime.now().isoformat(),
            "runs": usable_runs,
            "meta": {
                "cutoff_days": cutoff_days,
                "half_life_days": half_life_days,
                "raw_jobs": raw_jobs,
                "effective_jobs": effective_jobs,
                "min_ts": min_ts_dt.isoformat(),
                "max_ts": t_ref_dt.isoformat(),
            },
            "weighted_summary": weighted_summary,
            "top_terms": top_terms,
            "series": series,
        }

    def _compute_run_weight(self, run_ts: datetime, t_ref: float, half_life_days: float) -> float:
        """Compute weight for a run using half-life decay."""
        delta_days = (t_ref - run_ts.timestamp()) / (24 * 3600)
        return 2 ** (-delta_days / half_life_days)

    def _filter_recent_jobs(self, jobs: List[Dict[str, Any]], cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Filter jobs to only include those posted after cutoff date."""
        recent_jobs = []

        for job in jobs:
            posted_date = self._parse_job_date(job)
            if posted_date and posted_date >= cutoff_date:
                recent_jobs.append(job)

        return recent_jobs

    def _parse_job_date(self, job: Dict[str, Any]) -> Optional[datetime]:
        """Parse job posting date from various formats."""
        date_str = job.get('posted_date') or job.get('date_posted')

        if not date_str:
            return None

        try:
            # Try ISO format first
            if isinstance(date_str, str):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                return date_str
        except:
            return None

    def _build_category_rankings(
        self,
        jobs: List[Dict[str, Any]],
        half_life_days: int,
        top_n: int
    ) -> Dict[str, Any]:
        """Build category rankings with recency weighting."""

        categories = {}

        for job in jobs:
            # Calculate recency weight
            posted_date = self._parse_job_date(job)
            if posted_date:
                days_old = (datetime.now() - posted_date).days
                weight = 0.5 ** (days_old / half_life_days)  # Exponential decay
            else:
                weight = 1.0

            # Process job categories (skills, requirements, etc.)
            job_categories = job.get('categories', {})

            for category_name, terms in job_categories.items():
                if category_name not in categories:
                    categories[category_name] = {}

                if isinstance(terms, list):
                    for term in terms:
                        term_key = str(term).lower().strip()
                        if term_key not in categories[category_name]:
                            categories[category_name][term_key] = {
                                'count': 0,
                                'weighted_count': 0,
                                'term': term
                            }

                        categories[category_name][term_key]['count'] += 1
                        categories[category_name][term_key]['weighted_count'] += weight

        # Convert to sorted lists
        result = {}
        for category_name, terms_dict in categories.items():
            sorted_terms = sorted(
                terms_dict.values(),
                key=lambda x: x['weighted_count'],
                reverse=True
            )[:top_n]

            result[category_name] = {
                'terms': sorted_terms,
                'total_unique': len(terms_dict),
                'truncated': len(terms_dict) > top_n
            }

        return result

    def _build_market_context(self, jobs: List[Dict[str, Any]], top_n: int) -> Dict[str, Any]:
        """Build market context data."""

        context = {
            'work_types': {},
            'locations': {},
            'salary_ranges': {},
            'company_sizes': {}
        }

        for job in jobs:
            # Work type
            work_type = job.get('work_type', 'unknown')
            context['work_types'][work_type] = context['work_types'].get(work_type, 0) + 1

            # Location type
            location_type = job.get('location_type', 'unknown')
            context['locations'][location_type] = context['locations'].get(location_type, 0) + 1

            # Salary range (simplified)
            salary = job.get('salary')
            if salary:
                range_key = self._categorize_salary(salary)
                context['salary_ranges'][range_key] = context['salary_ranges'].get(range_key, 0) + 1

        # Convert to sorted lists
        for key, data in context.items():
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
            context[key] = {
                'distribution': sorted_items[:top_n],
                'other_count': sum(count for _, count in sorted_items[top_n:])
            }

        return context

    def _categorize_salary(self, salary: Any) -> str:
        """Categorize salary into ranges."""
        if isinstance(salary, str):
            # Try to extract numbers
            import re
            numbers = re.findall(r'\d+', salary)
            if numbers:
                try:
                    amount = int(numbers[0])
                    if amount < 50000:
                        return '<$50K'
                    elif amount < 80000:
                        return '$50K-$80K'
                    elif amount < 120000:
                        return '$80K-$120K'
                    else:
                        return '$120K+'
                except:
                    pass

        return 'Not specified'

    def _extract_top_companies(self, jobs: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        """Extract top companies by job count."""
        companies = {}

        for job in jobs:
            company = job.get('company', 'Unknown')
            companies[company] = companies.get(company, 0) + 1

        sorted_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)
        return [
            {'company': company, 'count': count}
            for company, count in sorted_companies[:top_n]
        ]

    def _extract_top_titles(self, jobs: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        """Extract top job titles by frequency."""
        titles = {}

        for job in jobs:
            title = job.get('title', 'Unknown')
            # Normalize title
            title_key = title.lower().strip()
            titles[title_key] = titles.get(title_key, {'title': title, 'count': 0})
            titles[title_key]['count'] += 1

        sorted_titles = sorted(titles.values(), key=lambda x: x['count'], reverse=True)
        return sorted_titles[:top_n]

    def _analyze_salary_distribution(self, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze salary distribution."""
        salaries = []

        for job in jobs:
            salary = job.get('salary')
            if salary:
                # Try to extract numeric salary
                try:
                    if isinstance(salary, str):
                        import re
                        numbers = re.findall(r'\d+', salary)
                        if numbers:
                            salaries.append(int(numbers[0]))
                    elif isinstance(salary, (int, float)):
                        salaries.append(int(salary))
                except:
                    pass

        if not salaries:
            return {'available': 0, 'ranges': {}}

        # Calculate statistics
        salaries.sort()
        return {
            'available': len(salaries),
            'min': min(salaries),
            'max': max(salaries),
            'median': salaries[len(salaries) // 2],
            'ranges': self._group_salaries(salaries)
        }

    def _group_salaries(self, salaries: List[int]) -> Dict[str, int]:
        """Group salaries into ranges."""
        ranges = {
            '<$50K': 0,
            '$50K-$80K': 0,
            '$80K-$120K': 0,
            '$120K+': 0
        }

        for salary in salaries:
            if salary < 50000:
                ranges['<$50K'] += 1
            elif salary < 80000:
                ranges['$50K-$80K'] += 1
            elif salary < 120000:
                ranges['$80K-$120K'] += 1
            else:
                ranges['$120K+'] += 1

        return ranges