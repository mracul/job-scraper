# Job Scraper Project

## Project Overview

This is a comprehensive Python-based web scraper designed to collect, analyze, and report on job listings from **Seek.com.au** and **Jora.com**. It utilizes **Selenium** for robust browser-based scraping to bypass anti-bot measures and features a modern **Streamlit** dashboard for interaction.

Key capabilities include:
*   **Multi-Site Scraping:** Supports Seek and Jora.
*   **Browser Automation:** Uses Selenium (Chrome/Edge) with parallel worker support for efficient data fetching.
*   **Intelligent Analysis:**  Extracts and weights job requirements (certifications, skills, experience) using context-aware NLP techniques.
*   **User Interfaces:**  Offers both a rich Streamlit web dashboard and a flexible Command Line Interface (CLI).
*   **Data Management:**  Handles deduplication, URL tracking, and structured export (CSV, JSON, Markdown).

## Building and Running

### Prerequisites
*   Python 3.8+
*   Google Chrome or Microsoft Edge browser installed.

### Setup
1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

**1. Streamlit Dashboard (Recommended)**
The visual interface allows for easy scraping, report browsing, and configuration.
```bash
# Windows
run_streamlit.bat

# Or manually
streamlit run streamlit_app.py
```

**2. Command Line Interface (CLI)**
For automated or headless operations.
```bash
# Interactive mode
python main.py

# specific search examples
python main.py --keywords "IT Support" --location "Sydney" --pages 3
python main.py --source seek --format json
```

## Key Files and Structure

*   **`main.py`**: The entry point for the CLI. Handles argument parsing and orchestrates the scraping process.
*   **`streamlit_app.py`**: The main entry point for the Streamlit web interface.
*   **`browser_scraper.py`**: Contains the `BrowserScraper` class, implementing the Selenium-based logic for interacting with Seek and Jora, including parallel worker management.
*   **`analyze_requirements.py`**: Core logic for analyzing job descriptions. It extracts requirements, applies weighting (required vs. preferred), and generates reports.
*   **`models.py`**: Defines the data models (e.g., `Job`, `JobCollection`) used throughout the application.
*   **`compiled_report_store.py`**: Manages the storage and retrieval of compiled analysis reports.
*   **`scraped_data/`**: The default output directory. Each run creates a timestamped subdirectory containing raw job files, CSVs, and analysis reports.

## Development Conventions

*   **Scraping Strategy:** The project prioritizes browser-based scraping (Selenium) to handle dynamic content and anti-bot protections. It includes logic for "human-like" delays and page scrolling.
*   **Data Persistence:** Scraped data is saved structurally in `scraped_data/` with timestamped folders. `compiled_jobs.md` is generated as an "AI-ready" summary for each run.
*   **Configuration:** The project uses `argparse` for CLI arguments and likely stores UI settings in local JSON files (implied by `ui_settings.json` references in code/logs).
*   **Testing:** `pytest` is used for testing, with configuration in `pytest.ini` and tests located in `tests/`.
