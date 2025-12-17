"""
Pipeline orchestrator for analysis operations.
Handles deduplication and requirements analysis with proper coordination.
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import json
import os

from pipeline.deduplicator import Deduplicator
from pipeline.requirements_analyzer import JobRequirementsAnalyzer


class AnalysisRunner:
    """
    Orchestrates deduplication and requirements analysis pipeline.

    Ensures deduplication happens once and coordinates with requirements analysis
    to avoid double-dedupe while maintaining accurate counts.
    """

    def __init__(self):
        self.deduplicator = Deduplicator()
        self.analyzer = JobRequirementsAnalyzer()

    def run_analysis(
        self,
        run_folders: List[str],
        output_dir: str = "outputs"
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run the complete analysis pipeline.

        Args:
            run_folders: List of run folder paths to analyze
            output_dir: Directory to save analysis results

        Returns:
            Tuple of (analysis_json, dedup_stats, effective_jobs)
        """

        # Step 1: Load and deduplicate all jobs once
        print("Loading and deduplicating jobs...")
        all_jobs = []
        dedup_stats = {
            'total_jobs': 0,
            'unique_jobs': 0,
            'duplicates_removed': 0,
            'runs_processed': len(run_folders)
        }

        for run_folder in run_folders:
            run_jobs = self._load_jobs_from_run(run_folder)
            all_jobs.extend(run_jobs)
            dedup_stats['total_jobs'] += len(run_jobs)

        # Deduplicate across all runs
        effective_jobs = self.deduplicator.deduplicate_jobs(all_jobs)

        dedup_stats['unique_jobs'] = len(effective_jobs)
        dedup_stats['duplicates_removed'] = dedup_stats['total_jobs'] - dedup_stats['unique_jobs']

        print(f"Deduplication complete: {dedup_stats['total_jobs']} → {dedup_stats['unique_jobs']} jobs")

        # Step 2: Run requirements analysis on deduplicated jobs
        print("Running requirements analysis...")
        analysis_json = self.analyzer.analyze_jobs(effective_jobs)

        # Add dedup stats to analysis results
        analysis_json['deduplication_stats'] = dedup_stats
        analysis_json['effective_job_count'] = len(effective_jobs)

        # Step 3: Save results
        self._save_analysis_results(analysis_json, output_dir, run_folders)

        return analysis_json, dedup_stats, effective_jobs

    def _load_jobs_from_run(self, run_folder: str) -> List[Dict[str, Any]]:
        """Load jobs from a single run folder."""
        jobs = []

        # Try JSONL first
        jsonl_path = Path(run_folder) / "jobs.jsonl"
        if jsonl_path.exists():
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            jobs.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        # Fallback to markdown parsing if needed
        if not jobs:
            md_path = Path(run_folder) / "compiled_jobs.md"
            if md_path.exists():
                jobs = self._parse_jobs_from_markdown(md_path)

        return jobs

    def _parse_jobs_from_markdown(self, md_path: Path) -> List[Dict[str, Any]]:
        """Parse jobs from markdown file (fallback method)."""
        jobs = []
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Simple parsing - this would need to be more robust in practice
            # For now, return empty list as this is a fallback
            print(f"Warning: Markdown parsing not implemented for {md_path}")
        except Exception as e:
            print(f"Error parsing markdown {md_path}: {e}")

        return jobs

    def _save_analysis_results(
        self,
        analysis_json: Dict[str, Any],
        output_dir: str,
        run_folders: List[str]
    ) -> None:
        """Save analysis results to files."""
        os.makedirs(output_dir, exist_ok=True)

        # Generate output filename based on run folders
        if len(run_folders) == 1:
            run_name = Path(run_folders[0]).name
        else:
            run_name = f"combined_{len(run_folders)}_runs"

        timestamp = self._get_timestamp()
        base_name = f"requirements_analysis_{run_name}_{timestamp}"

        # Save JSON
        json_path = Path(output_dir) / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_json, f, indent=2, ensure_ascii=False)

        # Save text summary
        txt_path = Path(output_dir) / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(self._format_analysis_summary(analysis_json))

        print(f"Analysis results saved to {json_path} and {txt_path}")

    def _get_timestamp(self) -> str:
        """Get current timestamp for filenames."""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _format_analysis_summary(self, analysis_json: Dict[str, Any]) -> str:
        """Format analysis results as readable text."""
        lines = []

        lines.append("JOB REQUIREMENTS ANALYSIS")
        lines.append("=" * 50)

        # Dedup stats
        dedup = analysis_json.get('deduplication_stats', {})
        lines.append(f"Total Jobs Processed: {dedup.get('total_jobs', 0)}")
        lines.append(f"Unique Jobs: {dedup.get('unique_jobs', 0)}")
        lines.append(f"Duplicates Removed: {dedup.get('duplicates_removed', 0)}")
        lines.append("")

        # Requirements summary
        reqs = analysis_json.get('requirements', {})
        if reqs:
            lines.append("REQUIREMENTS SUMMARY")
            lines.append("-" * 30)

            for category, data in reqs.items():
                if isinstance(data, dict) and 'terms' in data:
                    terms = data['terms'][:5]  # Top 5 terms
                    lines.append(f"{category.title()}: {', '.join(terms)}")

        return "\n".join(lines)


def run_analysis_pipeline(run_folders: List[str], output_dir: str = "outputs") -> Dict[str, Any]:
    """
    Convenience function to run the analysis pipeline.

    Args:
        run_folders: List of run folder paths
        output_dir: Output directory

    Returns:
        Analysis results JSON
    """
    runner = AnalysisRunner()
    analysis_json, _, _ = runner.run_analysis(run_folders, output_dir)
    return analysis_json