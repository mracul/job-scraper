# Job Scraper

A comprehensive Python web scraper that collects, analyzes, and reports on job listings from **Seek.com.au** and **Jora.com**, with advanced AI-ready analysis and intelligent requirement extraction.

## Features

- 🌐 **Browser-based scraping** - Uses Selenium to bypass anti-bot measures with parallel job detail fetching
- 🔍 **Smart search** - Interactive prompts with fuzzy matching and bundle mode for multiple keywords
- 📊 **Advanced requirements analysis** - Context-aware scoring with dual metrics (presence + weighted)
- 🎯 **Precise certification detection** - Microsoft cert codes (AZ-900, MS-900, etc.) with friendly names
- 🤖 **AI-ready output** - Combined job descriptions with search metadata for LLM analysis
- 📈 **Intelligent deduplication** - Unicode-normalized job matching to eliminate duplicates
- 🎨 **Streamlit dashboard** - Visual interface for scraping, analysis, and report browsing
- 📁 **Organized output** - Timestamped folders with multiple export formats (CSV, JSON, TXT, Markdown)
- ⚡ **Performance optimized** - Parallel processing with configurable worker counts

## Installation

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure you have Chrome or Edge browser installed (required for browser-based scraping)

## Usage

### Basic Usage
Run the scraper with interactive prompts:

```bash
python main.py
```

You'll be prompted for:
- Job title/keywords (default: "help desk it")
- Location (default: "Auburn NSW")

### Advanced Command Line Examples

```bash
# Bundle mode - scrape multiple keyword sets
python main.py --keywords-list '["IT Support", "Help Desk", "Service Desk"]' --bundle-ids '["support", "desk", "service"]'

# Fuzzy search expansion
python main.py --keywords "IT support" --fuzzy

# High-performance mode (more workers)
python main.py --workers 16 --pages 5

# Scrape only Seek with JSON output
python main.py --source seek --format json

# Deterministic job scoring
python main.py --enable-scoring

# Debug mode with visible browsers
python main.py --visible --workers 1 --sequential
```

### Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--keywords` | - | Job title/keywords | Interactive prompt |
| `--keywords-list` | - | JSON array for bundle mode | None |
| `--bundle-ids` | - | Bundle identifiers for metadata | None |
| `--location` | - | Search location | Interactive prompt |
| `--fuzzy` | - | Expand search with related terms | No |
| `--pages` | `-p` | Max pages per site | 3 |
| `--source` | `-s` | Site(s): all, seek, jora | all |
| `--output` | `-o` | Output filename | jobs_TIMESTAMP.csv |
| `--format` | `-f` | Output format: csv, json | csv |
| `--delay` | `-d` | Delay between requests (seconds) | 1.5 |
| `--workers` | `-w` | Parallel browser workers | 10 |
| `--sequential` | - | Fetch details sequentially | Parallel |
| `--max-details` | - | Max job details to fetch | All |
| `--dedupe-before-details` | - | Deduplicate before fetching | No |
| `--enable-scoring` | - | Add APPLY/STRETCH/IGNORE scoring | No |
| `--http` | - | Use HTTP mode (often blocked) | Browser mode |
| `--visible` | - | Show browser windows | Hidden |

## Output Structure

Each scraping run creates a timestamped folder:

```
scraped_data/
└── IT_Support_Auburn_NSW_20251214_022106/
    ├── jobs/                        # Individual job files
    │   ├── 001_IT Support_Company A.txt
    │   ├── 002_Developer_Company B.txt
    │   └── ...
    ├── all_jobs.csv                 # Structured data (CSV)
    ├── compiled_jobs.txt            # All jobs in plain text (AI-ready)
    ├── compiled_jobs.md             # All jobs in Markdown format
    ├── requirements_analysis.txt    # Advanced analysis report
    ├── requirements_analysis.json   # Analysis data (JSON)
    ├── requirements_index.json      # Drill-down index for UI
    └── ai_summary.json              # AI-generated insights
```

## Advanced Requirements Analysis

The analyzer uses sophisticated NLP techniques to extract and score job requirements:

### Core Features
- **Context-Aware Weighting** - Terms get different weights based on surrounding text (required=1.0, preferred=0.8, bonus=0.5, context=0.2)
- **Bullet Point Detection** - Recognizes structured requirement lists for accurate weighting
- **Term Gating** - Filters false positives using local context windows
- **Dual Metrics** - Reports both raw presence counts and context-weighted importance scores
- **Unicode Deduplication** - Eliminates duplicate jobs with normalized text matching

### Analyzed Categories

- **Certifications** - Microsoft (AZ-900, MS-900, SC-300, etc.), CompTIA, ITIL, Cisco, AWS, security certs
- **Education** - Degrees, diplomas, certificates, TAFE qualifications
- **Technical Skills** - Windows, Microsoft 365, Azure, networking, security, hardware, etc.
- **Soft Skills** - Communication, problem-solving, customer service, time management
- **Experience Levels** - Years required, MSP experience, support level experience
- **Work Arrangements** - Full-time, part-time, remote, hybrid, contract
- **Benefits & Perks** - Training provided, certifications paid, professional development
- **Other Requirements** - Licenses, checks, travel, on-call duties

### Standalone Analysis

Run analysis on existing scraped data:

```bash
# Interactive analysis menu
python main.py  # Choose option 2

# Analyze specific file
python analyze_requirements.py --input "scraped_data/IT_Support_Auburn_NSW_20251214_022106/compiled_jobs.md"
```

### Analysis Output

The report shows both presence counts and weighted scores:

```
CERTIFICATIONS
  Microsoft 365 Certification (MS-xxx): 5 jobs (8.3%) | Score: 6.0 (avg: 1.20)
  AZ-900 (Azure Fundamentals): 3 jobs (5.0%) | Score: 3.6 (avg: 1.20)
  CompTIA A+: 2 jobs (3.3%) | Score: 2.0 (avg: 1.00)
```

## Streamlit Dashboard

Visual interface for the complete workflow:

```bash
run_streamlit.bat
```

Features:
- **Scrape Management** - Start new scrapes with visual parameter selection
- **Report Browser** - Interactive drill-down into requirements by category/term/job
- **AI Summaries** - Generate and view AI-powered insights from job data
- **Settings Panel** - Adjust analysis parameters and view system status

## AI Integration

The scraper produces AI-ready outputs with search context:

- **Compiled job text** with metadata headers
- **Structured analysis data** for programmatic use
- **AI summary generation** with category-specific insights
- **Search metadata preservation** (keywords, location, date)

## Important Notes

- **Browser Required**: Chrome or Microsoft Edge must be installed
- **Rate Limiting**: Built-in delays and rotation to avoid detection
- **Parallel Processing**: Optimized for modern multi-core CPUs
- **Anti-Bot Measures**: May need delay increases or worker reduction if blocked
- **Website Changes**: Scrapers may need updates when sites change structure
- **Terms of Service**: Review and comply with each website's terms
- **Personal Use**: Intended for personal job search and research purposes

## Project Structure

```
job-scraper/
├── main.py                  # CLI entry point with interactive menus
├── browser_scraper.py       # Selenium-based parallel scraper
├── analyze_requirements.py  # Advanced requirements analyzer
├── seek_scraper.py          # HTTP-based Seek scraper (fallback)
├── jora_scraper.py          # HTTP-based Jora scraper
├── models.py                # Data models and collections
├── streamlit_app.py         # Visual dashboard
├── ui_core.py               # UI components and utilities
├── browse_report.py         # Report browsing utilities
├── compiled_report_store.py # Report storage and caching
├── cookie_store.py          # Session management
├── url_skip_store.py        # URL deduplication
├── job_scorer.py            # Job scoring algorithms
├── requirements.txt         # Python dependencies
├── pytest.ini              # Test configuration
├── tests/                  # Comprehensive test suite
├── scraped_data/           # Output directory (auto-created)
├── outputs/                # Analysis reports (auto-created)
└── logs/                   # Debug logs (auto-created)
```

## Development

Run tests:
```bash
python -m pytest tests/ -v
```

## License

MIT License - Use at your own risk.
