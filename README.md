# Job Scraper

A Python web scraper that collects job listings from **Seek.com.au** and **Jora.com**.

## Features

- 🌐 **Browser-based scraping** - Uses Selenium to bypass anti-bot measures
- 🔍 **Search by keywords and location** - Interactive prompts with sensible defaults
- ⚡ **Parallel job detail fetching** - Multiple browser workers fetch full descriptions simultaneously
- 📁 **Organized output** - Each run creates a timestamped folder with individual and compiled job files
- 📊 **Multiple export formats** - CSV, JSON, TXT, and Markdown
- 🤖 **AI-ready compiled output** - Combined job descriptions ready for analysis

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

### Command Line Examples

```bash
# Scrape (fast mode defaults)
python main.py --pages 3

# Override workers (default is optimized for 6c/12t CPUs)
python main.py --workers 6

# Scrape only Seek
python main.py --source seek

# Scrape only Jora (browser mode)
python main.py --source jora

# Use sequential mode (less resource-intensive)
python main.py --sequential

# Show browser windows (useful for debugging)
python main.py --visible

# Limit number of job details to fetch
python main.py --max-details 10

```

### Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--pages` | `-p` | Max pages per site | 3 |
| `--source` | `-s` | Site(s) to scrape: all, seek, jora | all |
| `--output` | `-o` | Output filename | jobs_TIMESTAMP.csv |
| `--format` | `-f` | Output format: csv, json | csv |
| `--delay` | `-d` | Delay between requests (seconds) | 1.5 |
| `--workers` | `-w` | Parallel browser workers for fetching details | 10 |
| `--sequential` | - | Fetch job details one at a time | Parallel |
| `--max-details` | - | Max number of job details to fetch | All |
| `--http` | - | Use HTTP mode (often blocked) | Browser mode |
| `--visible` | - | Show browser windows | Hidden |

## Output Structure

Each scraping run creates a timestamped folder:

```
scraped_data/
└── run_20251201_093304/
    ├── jobs/                        # Individual job files
    │   ├── 001_IT Support_Company A.txt
    │   ├── 002_Developer_Company B.txt
    │   └── ...
    ├── all_jobs.csv                 # Structured data (CSV)
    ├── compiled_jobs.txt            # All jobs in plain text (for AI analysis)
    ├── compiled_jobs.md             # All jobs in Markdown format
    ├── requirements_analysis.txt    # Requirements analysis report
    └── requirements_analysis.json   # Requirements data (JSON)
```

## Requirements Analysis

After each scrape, the tool automatically analyzes job listings to extract commonly requested:

- **Certifications** - ITIL, CompTIA A+/Network+/Security+, Microsoft Certified, CCNA, AWS, Azure
- **Education** - Bachelor's Degree, Diploma, Certificate IV/III, TAFE qualifications
- **Technical Skills** - Windows, Microsoft 365, Active Directory, Networking, Azure, Intune, etc.
- **Soft Skills** - Customer Service, Communication, Problem Solving, Troubleshooting
- **Experience** - Years of experience, MSP experience, Service Desk experience
- **Other Requirements** - Driver's license, Police check, Working with Children Check

### Standalone Analysis

You can also run the analyzer separately on any compiled jobs file:

```bash
# Analyze the latest scrape
python analyze_requirements.py

# Analyze a specific file
python analyze_requirements.py --input "scraped_data/run_20251201_172707/compiled_jobs.md"
```

### Output Fields

Each job includes:
- `title` - Job title
- `company` - Company name
- `location` - Job location
- `salary` - Salary information (if available)
- `description` - Brief description from search results
- `full_description` - Complete job description from the job page
- `url` - Link to the full job posting
- `source` - Which site the job came from (seek/jora)

## Important Notes

- **Browser Required**: Chrome or Microsoft Edge must be installed
- **Rate Limiting**: Built-in delays between requests to avoid detection
- **Parallel Fetching**: Uses multiple browser instances to speed up full description fetching
- **Anti-Bot Measures**: Some sites may still block requests - try increasing delay or using fewer workers
- **Website Changes**: Scrapers may break when websites update their structure
- **Terms of Service**: Review and comply with each website's terms of service
- **Personal Use**: This tool is intended for personal job search purposes only

## Project Structure

```
job-scraper/
├── main.py                  # CLI entry point with interactive prompts
├── browser_scraper.py       # Selenium-based scraper (parallel support)
├── analyze_requirements.py  # Job requirements analyzer
├── seek_scraper.py          # HTTP-based Seek scraper (fallback)
├── models.py                # Job dataclass and JobCollection
├── requirements.txt         # Python dependencies
├── scraped_data/            # Output folder (created on first run)
└── README.md                # This file
```

## Streamlit UI

If you prefer a visual interface, use the helper script that runs the dashboard where you can start new runs, review reports, and adjust settings.

```bash
run_streamlit.bat
```

This simply executes `streamlit run streamlit_app.py` with the right working directory.

## License

MIT License - Use at your own risk.
