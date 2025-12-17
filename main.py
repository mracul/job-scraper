"""
Job Scraper - Scrape job listings from Seek and Jora (browser mode).

Usage:
    python main.py --pages 3 --output jobs.csv
    python main.py  # Interactive mode with browser scraping (default)
"""
import argparse
from datetime import datetime
from seek_scraper import SeekScraper
from models import JobCollection
from job_storage import JobStorage
from deduplication import Deduplicator
from url_skip_store import load_seen_urls, add_urls
from pathlib import Path
import os

# Default search values
DEFAULT_KEYWORDS = "help desk it"
DEFAULT_LOCATION = "Auburn NSW"
DEFAULT_PAGES = 3

# Fuzzy search variants - maps common terms to related keywords for broader coverage
SEARCH_VARIANTS = {
    "help desk": ["helpdesk", "service desk", "it support", "desktop support", "technical support"],
    "helpdesk": ["help desk", "service desk", "it support", "desktop support", "technical support"],
    "service desk": ["help desk", "helpdesk", "it support", "desktop support", "support analyst"],
    "it support": ["help desk", "helpdesk", "service desk", "desktop support", "technical support", "it technician"],
    "desktop support": ["help desk", "it support", "deskside support", "end user support", "desktop technician"],
    "support analyst": ["service desk analyst", "help desk analyst", "it support analyst", "support specialist"],
    "system admin": ["sysadmin", "systems administrator", "it administrator", "infrastructure"],
    "network": ["network engineer", "network administrator", "network technician", "infrastructure"],
    "junior": ["entry level", "graduate", "trainee", "traineeship"],
    "trainee": ["traineeship", "junior", "entry level", "graduate"],
}


def expand_search_terms(keywords: str) -> list[str]:
    """Expand search keywords with fuzzy variants for broader coverage."""
    keywords_lower = keywords.lower()
    expanded = [keywords]  # Always include original
    
    for term, variants in SEARCH_VARIANTS.items():
        if term in keywords_lower:
            for variant in variants:
                # Replace the term with variant
                new_search = keywords_lower.replace(term, variant)
                if new_search not in [k.lower() for k in expanded]:
                    expanded.append(new_search)
    
    return expanded


def get_search_parameters() -> tuple[str, str, int, bool]:
    """Prompt user for search parameters with defaults."""
    print("\n" + "=" * 60)
    print("Job Scraper - Search Configuration")
    print("=" * 60)
    
    keywords = input(f"\nEnter job title/keywords [{DEFAULT_KEYWORDS}]: ").strip()
    if not keywords:
        keywords = DEFAULT_KEYWORDS
    
    location = input(f"Enter location [{DEFAULT_LOCATION}]: ").strip()
    if not location:
        location = DEFAULT_LOCATION
    
    pages_input = input(f"Enter max pages to scrape [{DEFAULT_PAGES}]: ").strip()
    if pages_input:
        try:
            pages = int(pages_input)
        except ValueError:
            pages = DEFAULT_PAGES
    else:
        pages = DEFAULT_PAGES
    
    # Ask about fuzzy search
    fuzzy_input = input("Expand search with related terms? (y/N): ").strip().lower()
    use_fuzzy = fuzzy_input in ('y', 'yes')
    
    if use_fuzzy:
        expanded = expand_search_terms(keywords)
        if len(expanded) > 1:
            print(f"\nWill search for: {', '.join(expanded)}")
    
    return keywords, location, pages, use_fuzzy


def choose_main_action() -> str:
    """Simple text menu: choose to scrape or analyze requirements."""
    print("\n" + "=" * 60)
    print("Job Scraper - Main Menu")
    print("=" * 60)
    print("1. Scrape jobs")
    print("2. Analyze requirements from previous runs")
    print("3. Exit")
    
    while True:
        choice = input("\nSelect an option [1-3]: ").strip()
        if choice in {"1", "2", "3"}:
            return choice
        print("Please enter 1, 2, or 3.")


def list_runs_for_analysis(base_dir: str = "scraped_data") -> list[Path]:
    """Return sorted list of run folders for analysis (newest first)."""
    root = Path(base_dir)
    if not root.exists():
        return []
    # Include both old run_ format and new keyword-based folders
    runs = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    return runs


def read_run_metadata(run_path: Path) -> dict:
    """Read search metadata from a run's compiled_jobs.md file."""
    compiled = run_path / "compiled_jobs.md"
    metadata = {"keywords": None, "location": None, "job_count": 0}
    
    if not compiled.exists():
        return metadata
    
    try:
        with open(compiled, 'r', encoding='utf-8') as f:
            # Read first 10 lines for header info
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                if line.startswith("**Search Keywords:**"):
                    metadata["keywords"] = line.replace("**Search Keywords:**", "").strip().rstrip("  ")
                elif line.startswith("**Search Location:**"):
                    metadata["location"] = line.replace("**Search Location:**", "").strip().rstrip("  ")
                elif line.startswith("**Total Jobs:**"):
                    try:
                        metadata["job_count"] = int(line.replace("**Total Jobs:**", "").strip())
                    except ValueError:
                        pass
    except Exception:
        pass
    
    return metadata


def analyze_ui():
    """Interactive UI to select one or more runs and analyze requirements."""
    from analyze_requirements import JobRequirementsAnalyzer
    from browse_report import browse_requirements_index
    runs = list_runs_for_analysis()
    if not runs:
        print("\nNo scraped_data runs found yet. Run a scrape first.")
        return
    
    print("\nAvailable runs:")
    for idx, run in enumerate(runs, start=1):
        meta = read_run_metadata(run)
        compiled = run / "compiled_jobs.md"
        
        # Build label with search context
        if meta["keywords"] and meta["keywords"] != "Not specified":
            label = f"{meta['keywords']}"
            if meta["location"] and meta["location"] != "Not specified":
                label += f" - {meta['location']}"
            if meta["job_count"]:
                label += f" ({meta['job_count']} jobs)"
        else:
            label = run.name
            if compiled.exists():
                label += " (compiled_jobs.md)"
        
        print(f"  {idx}. {label}")
    
    print("\nEnter run numbers to analyze (e.g. 1,3,4) or 'a' for all, or press Enter to cancel.")
    sel = input("Selection: ").strip()
    if not sel:
        return
    
    selected_runs: list[Path]
    if sel.lower() == "a":
        selected_runs = runs
    else:
        try:
            indices = {int(s) for s in sel.split(",") if s.strip()}
            selected_runs = [runs[i-1] for i in sorted(indices) if 1 <= i <= len(runs)]
        except ValueError:
            print("Invalid selection.")
            return
    
    if not selected_runs:
        print("No valid runs selected.")
        return
    
    # Ask whether to browse an existing report index or (re)generate analysis
    mode = input("\nChoose: [1] Browse report (Category→Term→Jobs)  [2] (Re)generate analysis  (default: 1): ").strip()
    if mode not in {"", "1", "2"}:
        mode = "1"

    # If browsing, require exactly one run so we know which index to open.
    if mode in {"", "1"}:
        if len(selected_runs) != 1:
            print("\nBrowsing requires selecting exactly one run.")
            return

        run = selected_runs[0]
        index_path = run / "requirements_index.json"
        if not index_path.exists():
            print("\nNo requirements_index.json found in this run.")
            gen = input("Generate it now from compiled_jobs.md? (Y/n): ").strip().lower()
            if gen in {"n", "no"}:
                return

            compiled = run / "compiled_jobs.md"
            if not compiled.exists():
                print("This run doesn't have compiled_jobs.md.")
                return
            analyzer = JobRequirementsAnalyzer()
            jobs, search_meta = analyzer.extract_jobs_from_markdown(str(compiled))
            if not jobs:
                print("No jobs found in compiled_jobs.md.")
                return
            analysis = analyzer.analyze_all_jobs(jobs, dedupe=True)
            analyzer.generate_report(analysis, str(run), search_metadata=search_meta)

        print(f"\nOpening report index: {index_path}")
        browse_requirements_index(str(index_path))
        return

    # Otherwise, aggregate jobs from all selected compiled files
    analyzer = JobRequirementsAnalyzer()
    all_jobs = []
    combined_keywords = []
    combined_locations = []
    for run in selected_runs:
        compiled = run / "compiled_jobs.md"
        if not compiled.exists():
            continue
        jobs, meta = analyzer.extract_jobs_from_markdown(str(compiled))
        all_jobs.extend(jobs)
        if meta.get('keywords'):
            combined_keywords.append(meta['keywords'])
        if meta.get('location'):
            combined_locations.append(meta['location'])
    
    if not all_jobs:
        print("No compiled job data found in selected runs.")
        return
    
    # Build combined metadata
    combined_meta = {
        'keywords': ', '.join(dict.fromkeys(combined_keywords)) or None,
        'location': ', '.join(dict.fromkeys(combined_locations)) or None,
    }
    
    print(f"\nAnalyzing {len(all_jobs)} jobs from {len(selected_runs)} run(s)...")
    analysis = analyzer.analyze_all_jobs(all_jobs, dedupe=True)
    # Save a combined report under outputs/ (keep repo root clean)
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = analyzer.generate_report(analysis, str(output_dir), search_metadata=combined_meta)
    print(report)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape job listings from Seek and Jora (Browser mode by default)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                           # Interactive menu (scrape/analyze)
    python main.py --pages 5                 # More pages when scraping
    python main.py --output results.csv      # Save to file
    python main.py --http                    # Use HTTP mode instead
    python main.py --source seek --format json
    python main.py --keywords-list '["IT Support", "Help Desk"]' --location "Sydney"
        """
    )

    parser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="Search keywords/job title (non-interactive). If omitted, prompts interactively."
    )

    parser.add_argument(
        "--keywords-list",
        type=str,
        default=None,
        help="JSON array of keyword phrases for bundle mode (e.g., '[\"IT Support\", \"Help Desk\"]'). Mutually exclusive with --keywords."
    )

    parser.add_argument(
        "--bundle-ids",
        type=str,
        default=None,
        help="Comma-separated bundle identifiers for metadata (used with --keywords-list)."
    )

    parser.add_argument(
        "--location",
        type=str,
        default=None,
        help="Search location (non-interactive). If omitted, prompts interactively."
    )

    fuzzy_group = parser.add_mutually_exclusive_group()
    fuzzy_group.add_argument(
        "--fuzzy",
        action="store_true",
        help="Expand search with related terms (non-interactive)."
    )
    fuzzy_group.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Disable fuzzy search expansion (non-interactive)."
    )
    
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=3,
        help="Maximum number of pages to scrape per site (default: 3)"
    )
    
    parser.add_argument(
        "--source", "-s",
        choices=["all", "seek", "jora"],
        default="all",
        help="Which job site(s) to scrape (default: all)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output filename (default: jobs_YYYYMMDD_HHMMSS.csv)"
    )
    
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)"
    )
    
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.5,
        help="Delay between requests in seconds (default: 1.5 fast mode, use 3.0+ if getting blocked)"
    )
    
    parser.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP requests instead of browser mode (browser mode is default)"
    )
    
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window when using browser mode"
    )

    # Indeed has been deprecated and removed.
    
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help="Fetch full job descriptions from each job page (slower but more complete)"
    )
    
    parser.add_argument(
        "--max-details",
        type=int,
        default=None,
        help="Maximum number of job details to fetch. Use 0 to skip detail fetching entirely. (default: all jobs)"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=10,
        help="Number of parallel browser workers for fetching job details (default: 10, optimal for 6-core/12-thread CPU)"
    )
    
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Fetch job details sequentially instead of in parallel (slower but uses less resources)"
    )

    parser.add_argument(
        "--dedupe-before-details",
        action="store_true",
        help="Deduplicate jobs before fetching details (prevents redundant browser requests)."
    )

    parser.add_argument(
        "--enable-scoring",
        action="store_true",
        help="Add deterministic APPLY/STRETCH/IGNORE scoring to jobs based on title/description signals."
    )
    
    args = parser.parse_args()

    # Normalize fuzzy flag into a tri-state: None=interactive prompt, True/False=forced
    forced_fuzzy: bool | None
    if args.fuzzy:
        forced_fuzzy = True
    elif args.no_fuzzy:
        forced_fuzzy = False
    else:
        forced_fuzzy = None

    # Parse keywords-list (bundle mode) if provided
    keywords_list: list[str] | None = None
    bundle_ids: list[str] | None = None
    if args.keywords_list:
        import json as _json
        try:
            keywords_list = _json.loads(args.keywords_list)
            if not isinstance(keywords_list, list) or not all(isinstance(k, str) for k in keywords_list):
                raise ValueError("--keywords-list must be a JSON array of strings")
        except Exception as e:
            print(f"Error parsing --keywords-list: {e}")
            return
        if args.bundle_ids:
            bundle_ids = [b.strip() for b in args.bundle_ids.split(",") if b.strip()]

    # Validate mutually exclusive keywords options
    if args.keywords and keywords_list:
        print("Error: --keywords and --keywords-list are mutually exclusive.")
        return

    # If any scrape-specific flags are provided, skip menu and go straight to scrape
    has_non_default_scrape_flags = any([
        args.http,
        args.output is not None,
        args.pages != 3,
        args.source != "all",
        args.format != "csv",
        args.keywords is not None,
        args.location is not None,
        keywords_list is not None,
        forced_fuzzy is not None,
        args.enable_scoring,
        args.dedupe_before_details,
    ])

    if not has_non_default_scrape_flags:
        choice = choose_main_action()
        if choice == "2":
            analyze_ui()
            return
        elif choice == "3":
            return
        # else: "1" -> continue into scrape flow below

    # Load URL skip-store so we don't re-process jobs across runs
    seen_urls = load_seen_urls()

    # Get search parameters (non-interactive when provided)
    if args.keywords is not None or args.location is not None or keywords_list is not None or forced_fuzzy is not None:
        # Bundle mode: use keywords_list directly
        if keywords_list:
            keywords = ", ".join(keywords_list[:3]) + ("..." if len(keywords_list) > 3 else "")  # Display label
            location = (args.location or "").strip() or DEFAULT_LOCATION
            pages = int(args.pages)
            use_fuzzy = False  # Fuzzy not used in bundle mode
            search_terms = keywords_list  # Already expanded
        else:
            keywords = (args.keywords or "").strip() or DEFAULT_KEYWORDS
            location = (args.location or "").strip() or DEFAULT_LOCATION
            pages = int(args.pages)
            use_fuzzy = bool(forced_fuzzy) if forced_fuzzy is not None else False
            # Expand search terms if fuzzy search enabled
            if use_fuzzy:
                search_terms = expand_search_terms(keywords)
            else:
                search_terms = [keywords]
    else:
        keywords, location, pages, use_fuzzy = get_search_parameters()
        # Expand search terms if fuzzy search enabled
        if use_fuzzy:
            search_terms = expand_search_terms(keywords)
        else:
            search_terms = [keywords]

    # Create job collection with search context
    collection = JobCollection()
    # For bundle mode, use first keyword as primary (or join all for metadata)
    primary_keywords = keywords_list[0] if keywords_list else keywords
    collection.set_search_params(primary_keywords, location)
    
    # Set bundle information for folder naming
    if bundle_ids:
        collection.set_bundle_params(bundle_ids)
    
    # Store bundle metadata for compiled_jobs.md
    bundle_metadata = None
    if keywords_list:
        bundle_metadata = {
            "keywords_list": keywords_list,
            "bundle_ids": bundle_ids,
        }
    
    print(f"\n{'='*60}")
    if keywords_list:
        print(f"Job Scraper - Bundle Mode: {len(keywords_list)} keyword phrases in '{location}'")
        for i, kw in enumerate(keywords_list, 1):
            print(f"  [{i}] {kw}")
    else:
        print(f"Job Scraper - Searching for '{keywords}' in '{location}'")
        if use_fuzzy and len(search_terms) > 1:
            print(f"Fuzzy search enabled: {len(search_terms)} search variants")
    print(f"Max pages per search: {pages}")
    if args.http:
        print("Mode: HTTP requests")
    else:
        print("Mode: Browser-based (Selenium)")
    if args.enable_scoring:
        print("Scoring: Enabled (APPLY/STRETCH/IGNORE)")
    print(f"{ '='*60}\n")
    
    # Use browser-based scraping by default, HTTP only when --http is specified
    scraper = None

    if not args.http:
        try:
            from browser_scraper import BrowserScraper
            scraper = BrowserScraper(
                headless=not args.visible,
                delay=args.delay,
                browser="chrome",
            )
            
            # Run searches for all search terms
            for i, search_term in enumerate(search_terms, 1):
                if len(search_terms) > 1:
                    print(f"\n[{i}/{len(search_terms)}] Searching: '{search_term}'")
                
                if args.source == "all":
                    jobs = scraper.scrape_all(search_term, location, pages)
                    collection.add_all(jobs)
                elif args.source == "seek":
                    jobs = scraper.scrape_seek(search_term, location, pages)
                    collection.add_all(jobs)
                else:
                    jobs = scraper.scrape_jora(search_term, location, pages)
                    collection.add_all(jobs)
            
            # Deduplicate jobs (URL and Cross-Site)
            if len(collection) > 0:
                print("\nDeduplicating jobs...")
                unique_jobs, url_dupes, fuzzy_dupes = Deduplicator.deduplicate_jobs(
                    collection.jobs, seen_urls=seen_urls
                )
                
                print(f"  - Removed {url_dupes} duplicate jobs based on URL")
                print(f"  - Removed {fuzzy_dupes} duplicate jobs based on Title/Company/Location (Cross-Site)")
                
                collection.jobs = unique_jobs
            
            # Fetch full job descriptions in browser mode (unless max_details == 0)
            skip_details = args.max_details == 0
            if len(collection) > 0 and not skip_details:
                if args.sequential:
                    scraper.fetch_job_details_sequential(collection.jobs, max_jobs=args.max_details)
                else:
                    scraper.fetch_job_details(collection.jobs, max_jobs=args.max_details, workers=args.workers)
            elif skip_details:
                print("Skipping job detail fetching (--max-details 0)")
            
            scraper.close()
            scraper = None
            
        except ImportError:
            print("Error: Browser scraping requires selenium and webdriver-manager")
            print("Install with: pip install selenium webdriver-manager")
            print("Falling back to HTTP mode...")
            args.http = True  # Force HTTP mode
        except Exception as e:
            print(f"Error during browser scraping: {e}")
            print("Falling back to HTTP mode...")
            args.http = True  # Force HTTP mode
            if scraper:
                scraper.close()
    
    # Use HTTP-based scraping if --http flag or browser mode failed
    if args.http:
        for i, search_term in enumerate(search_terms, 1):
            if len(search_terms) > 1:
                print(f"\n[{i}/{len(search_terms)}] Searching: '{search_term}'")
            
            # Scrape Seek
            if args.source in ["all", "seek"]:
                try:
                    seek_scraper = SeekScraper(delay=args.delay)
                    seek_jobs = seek_scraper.scrape(search_term, location, max_pages=pages)
                    collection.add_all(seek_jobs)
                except Exception as e:
                    print(f"Error scraping Seek: {e}")

            if args.source in ["jora"]:
                print("\nNote: Jora scraping is supported only in browser mode. Re-run without --http.")

        # Deduplicate jobs (URL and Cross-Site)
        if len(collection) > 0:
            print("\nDeduplicating jobs...")
            unique_jobs, url_dupes, fuzzy_dupes = Deduplicator.deduplicate_jobs(
                collection.jobs, seen_urls=seen_urls
            )
            
            print(f"  - Removed {url_dupes} duplicate jobs based on URL")
            print(f"  - Removed {fuzzy_dupes} duplicate jobs based on Title/Company/Location (Cross-Site)")
            
            collection.jobs = unique_jobs
    
    print(f"\n{'='*60}")
    print(f"Total jobs found: {len(collection)}")
    print(f"{ '='*60}\n")
    
    # Export results
    if len(collection) > 0:
        # Apply scoring if enabled (after details fetch, before export)
        if args.enable_scoring:
            print("\n" + "=" * 60)
            print("Scoring jobs (APPLY/STRETCH/IGNORE)...")
            print("=" * 60)
            try:
                from job_scorer import score_jobs
                score_jobs(collection.jobs)
                # Count classifications
                apply_count = sum(1 for j in collection.jobs if getattr(j, "classification", None) == "APPLY")
                stretch_count = sum(1 for j in collection.jobs if getattr(j, "classification", None) == "STRETCH")
                ignore_count = sum(1 for j in collection.jobs if getattr(j, "classification", None) == "IGNORE")
                print(f"  APPLY: {apply_count} | STRETCH: {stretch_count} | IGNORE: {ignore_count}")
            except Exception as e:
                print(f"Warning: Could not apply scoring: {e}")
        
        # Persist URLs so future runs can skip already-seen jobs
        try:
            add_urls(job.url for job in collection.jobs if job.url)
        except Exception:
            # Fail soft: scraping results should still be saved even if skip-store write fails
            pass

        # Create run folder and save individual job files
        run_folder = JobStorage.create_run_folder(
            "scraped_data", 
            keywords=primary_keywords, 
            location=location
        )
        # Update collection so it knows the run folder (if used elsewhere)
        collection.run_folder = run_folder
        
        JobStorage.save_all_jobs(collection.jobs, run_folder)
        
        # Save combined CSV/JSON in the run folder
        if args.format == "csv":
            JobStorage.to_csv(
                collection.jobs, 
                os.path.join(run_folder, "all_jobs.csv")
            )
        else:
            JobStorage.to_json(
                collection.jobs, 
                os.path.join(run_folder, "all_jobs.json")
            )
        
        # Always create compiled text file for AI analysis
        # Pass bundle metadata for enhanced header
        JobStorage.to_compiled_text(
            collection.jobs,
            os.path.join(run_folder, "compiled_jobs.txt"),
            keywords=primary_keywords,
            location=location
        )
        JobStorage.to_markdown(
            collection.jobs,
            os.path.join(run_folder, "compiled_jobs.md"),
            keywords=primary_keywords,
            location=location,
            bundle_metadata=bundle_metadata
        )
        JobStorage.to_jsonl(
            collection.jobs,
            os.path.join(run_folder, "jobs.jsonl"),
            metadata=bundle_metadata
        )

        print(f"\n📁 All data saved to: {run_folder}")
        print(f"   📄 compiled_jobs.txt - Plain text for AI analysis")
        print(f"   📄 compiled_jobs.md  - Markdown format")
        print(f"   📄 jobs.jsonl        - Machine-readable (recommended for analysis)")
        print(f"   📄 all_jobs.{args.format}   - Structured data")
        print(f"   📂 jobs/            - Individual job files")
        
        # Run requirements analysis
        print("\n" + "=" * 60)
        print("Analyzing job requirements...")
        print("=" * 60)
        
        try:
            from analyze_requirements import JobRequirementsAnalyzer

            jsonl_file = os.path.join(run_folder, "jobs.jsonl")
            md_file = os.path.join(run_folder, "compiled_jobs.md")
            input_file = jsonl_file if os.path.exists(jsonl_file) else md_file
            if os.path.exists(input_file):
                analyzer = JobRequirementsAnalyzer()
                jobs_data, search_meta = analyzer.extract_jobs(input_file)
                analysis = analyzer.analyze_all_jobs(jobs_data, dedupe=True)
                report = analyzer.generate_report(analysis, run_folder, search_metadata=search_meta)
                print(report)
        except Exception as e:
            print(f"Note: Could not run requirements analysis: {e}")
        
        # Print summary
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
        print("No jobs found. Try different search terms or check your internet connection.")
        print("\nIf you're getting 403 Forbidden errors, try:")
        print("  - Increasing the delay: python main.py --delay 8.0")
        print("  - Using a VPN")
        print("  - Using HTTP mode: python main.py --http")


if __name__ == "__main__":
    main()