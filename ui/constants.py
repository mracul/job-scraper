"""UI constants for the job scraper Streamlit app."""

from pathlib import Path

# Directory paths
SCRAPED_DATA_DIR = Path(__file__).parent.parent / "scraped_data"
RUN_STATE_FILE = Path(__file__).parent.parent / "state" / "active_run.json"
LOGS_DIR = Path(__file__).parent.parent / "logs"
OVERVIEW_DIR = Path(__file__).parent.parent / "state" / "overviews"
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"

# Category labels for job requirements
CATEGORY_LABELS = {
    "certifications": "🏆 Certifications",
    "education": "🎓 Education",
    "technical_skills": "💻 Technical Skills",
    "soft_skills": "🤝 Soft Skills",
    "experience": "📅 Experience",
    "support_levels": "🎯 Support Levels",
    "work_arrangements": "🏢 Work Arrangements",
    "benefits": "🎁 Benefits",
    "other_requirements": "📋 Other Requirements"
}

# Detail fetch options
DETAIL_FETCH_OPTIONS = [
    ("Fetch all job details", None),
    ("Skip job details (only job cards)", 0),
]
DETAIL_FETCH_LABELS = [label for label, _ in DETAIL_FETCH_OPTIONS]
DETAIL_FETCH_VALUES = {label: value for label, value in DETAIL_FETCH_OPTIONS}

# Filter widget keys derived from category labels
FILTER_WIDGET_KEYS = [f"filter_{cat_key}" for cat_key in CATEGORY_LABELS]

# AI summary constants
AI_SUMMARY_MAX_OUTPUT_TOKENS = 2000
AI_SUMMARY_TOP_N_SINGLE = 50  # SINGLE SCRAPE RUN
AI_SUMMARY_TOP_N_COMPILED = 75  # COMPILED SCRAPE RUNS

# Cutoff presets for time-based filtering
CUTOFF_PRESETS = [
    ("7d", 7),
    ("30d", 30),
    ("90d", 90),
    ("180d", 180),
    ("365d", 365),
]
CUTOFF_LABELS = [label for label, _ in CUTOFF_PRESETS]
CUTOFF_VALUES = {label: value for label, value in CUTOFF_PRESETS}

# Half-life presets for exponential decay weighting
HALFLIFE_PRESETS = [
    ("7d", 7),
    ("14d", 14),
    ("30d", 30),
    ("60d", 60),
    ("90d", 90),
]
HALFLIFE_LABELS = [label for label, _ in HALFLIFE_PRESETS]
HALFLIFE_VALUES = {label: value for label, value in HALFLIFE_PRESETS}