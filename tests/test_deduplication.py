"""Tests for job deduplication logic."""
import pytest
from deduplication import Deduplicator
from models import Job

@pytest.fixture
def sample_jobs():
    return [
        Job(
            title="IT Support",
            company="Tech Corp",
            location="Sydney",
            salary=None,
            description="Fix computers",
            url="http://example.com/job1",
            source="seek"
        ),
        Job(
            title="IT Support",
            company="Tech Corp",
            location="Sydney NSW",
            salary=None,
            description="Fix computers",
            url="http://example.com/job2", # Different URL
            source="jora"
        ),
        Job(
            title="Help Desk",
            company="Other Corp",
            location="Melbourne",
            salary=None,
            description="Answer phones",
            url="http://example.com/job3",
            source="seek"
        ),
    ]

def test_deduplicate_exact_url(sample_jobs):
    """Test deduplication by exact URL match."""
    # Duplicate job 1
    jobs = sample_jobs + [sample_jobs[0]] 
    assert len(jobs) == 4
    
    unique, url_dupes, fuzzy_dupes = Deduplicator.deduplicate_jobs(jobs)
    
    # Job 1: Kept
    # Job 2: Fuzzy duplicate of Job 1 -> Removed
    # Job 3: Kept
    # Job 1 (copy): Exact URL duplicate of Job 1 -> Removed
    
    assert len(unique) == 2
    assert url_dupes == 1
    assert fuzzy_dupes == 1

def test_deduplicate_cross_site_fuzzy(sample_jobs):
    """Test deduplication by fuzzy match (Title/Company/Location)."""
    # Job 1 and Job 2 are fuzzy duplicates (same title, company, similar location)
    # job 2 location "Sydney NSW" normalizes to "sydney" if logic works
    
    # Check normalization explicitly first
    key1 = Deduplicator._get_fuzzy_match_key(sample_jobs[0])
    key2 = Deduplicator._get_fuzzy_match_key(sample_jobs[1])
    assert key1 == key2
    
    unique, url_dupes, fuzzy_dupes = Deduplicator.deduplicate_jobs(sample_jobs)
    
    assert len(unique) == 2 # Job 1 kept, Job 2 removed, Job 3 kept
    assert url_dupes == 0
    assert fuzzy_dupes == 1
    assert unique[0].source == "seek" # First one kept
    assert unique[1].title == "Help Desk"

def test_seen_urls_filtering(sample_jobs):
    """Test filtering against previously seen URLs."""
    seen = {"http://example.com/job1"}
    
    unique, url_dupes, fuzzy_dupes = Deduplicator.deduplicate_jobs(sample_jobs, seen_urls=seen)
    
    # Job 1 should be removed as it's in seen_urls
    # Job 2 is fuzzy duplicate of Job 1... but Job 1 was removed and its key was NOT recorded.
    # So Job 2 should be KEPT (treated as new because we ignored the previous instance).
    
    assert len(unique) == 2
    assert unique[0].url == "http://example.com/job2"
    assert unique[1].url == "http://example.com/job3"
    assert url_dupes == 1
    assert fuzzy_dupes == 0

def test_normalize_text():
    """Test text normalization."""
    assert Deduplicator.normalize_text("  IT   Support  ") == "it support"
    assert Deduplicator.normalize_text("Senior IT Support - Level 2") == "senior it support level 2" # punctuation removal test
    # Actually current regex removes non-word chars: r'[^\w\s]'
    assert Deduplicator.normalize_text("Sydney, NSW") == "sydney nsw"
    assert Deduplicator.normalize_text("Café") == "café" # unicode preserved? NFKC normalizes.