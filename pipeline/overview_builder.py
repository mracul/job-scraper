"""
Overview pipeline builder.
Creates overview data structures used by both UI and AI components.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime, timedelta


class OverviewBuilder:
    """
    Builds overview data structures from run data.

    Processes job data to create category rankings, market context,
    and other overview metrics used by both UI components and AI analysis.
    """

    def __init__(self):
        pass

    def build_overview(
        self,
        run_data: Dict[str, Any],
        cutoff_days: int = 30,
        half_life_days: int = 14,
        top_n: int = 10
    ) -> Dict[str, Any]:
        """
        Build overview payload from run data.

        Args:
            run_data: Dictionary containing run information and jobs
            cutoff_days: Age cutoff for recent jobs
            half_life_days: Half-life for recency weighting
            top_n: Number of top items to show

        Returns:
            Overview payload dictionary
        """

        jobs = run_data.get('jobs', [])
        run_info = run_data.get('run_info', {})

        # Calculate time-based filtering
        cutoff_date = datetime.now() - timedelta(days=cutoff_days)

        # Filter recent jobs
        recent_jobs = self._filter_recent_jobs(jobs, cutoff_date)

        # Build category rankings with recency weighting
        category_data = self._build_category_rankings(
            recent_jobs,
            half_life_days,
            top_n
        )

        # Build market context
        market_context = self._build_market_context(recent_jobs, top_n)

        # Build overview payload
        overview = {
            'run_info': run_info,
            'summary_stats': {
                'total_jobs': len(jobs),
                'recent_jobs': len(recent_jobs),
                'cutoff_days': cutoff_days,
                'half_life_days': half_life_days,
                'top_n': top_n,
                'generated_at': datetime.now().isoformat()
            },
            'categories': category_data,
            'market_context': market_context,
            'top_companies': self._extract_top_companies(recent_jobs, top_n),
            'top_titles': self._extract_top_titles(recent_jobs, top_n),
            'salary_distribution': self._analyze_salary_distribution(recent_jobs)
        }

        return overview

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