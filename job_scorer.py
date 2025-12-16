"""Deterministic job scoring for entry-level IT support roles.

Scoring is rule-based (no ML) and produces:
- score: integer 0-10
- classification: APPLY (>=6), STRETCH (4-5), IGNORE (<=3)
- matched_signals: list of matched positive/negative signals
- exclude_reason: reason for hard exclusion (if any)
"""

import re
from dataclasses import dataclass
from typing import Optional
from scoring_config import HARD_EXCLUDE_PATTERNS, POSITIVE_SIGNALS, NEGATIVE_SIGNALS


@dataclass
class ScoringResult:
    """Result of scoring a job listing."""
    score: int
    classification: str  # APPLY, STRETCH, IGNORE
    matched_signals: list[str]
    exclude_reason: Optional[str] = None


def score_job(title: str, description: str | None = None) -> ScoringResult:
    """Score a job listing based on title and description.
    
    Args:
        title: Job title
        description: Full job description (optional but improves accuracy)
    
    Returns:
        ScoringResult with score, classification, matched signals, and exclude reason
    """
    text = f"{title} {description or ''}".lower()
    matched_signals: list[str] = []
    
    # Check hard excludes first
    for pattern, reason in HARD_EXCLUDE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return ScoringResult(
                score=0,
                classification="IGNORE",
                matched_signals=[f"❌ {reason}"],
                exclude_reason=reason,
            )
    
    # Calculate base score (start at 5 = neutral)
    score = 5
    
    # Apply positive signals
    for pattern, points, label in POSITIVE_SIGNALS:
        if re.search(pattern, text, re.IGNORECASE):
            score += points
            matched_signals.append(f"+{points} {label}")
    
    # Apply negative signals
    for pattern, points, label in NEGATIVE_SIGNALS:
        if re.search(pattern, text, re.IGNORECASE):
            score += points  # points are already negative
            matched_signals.append(f"{points} {label}")
    
    # Clamp score to 0-10
    score = max(0, min(10, score))
    
    # Determine classification
    if score >= 6:
        classification = "APPLY"
    elif score >= 4:
        classification = "STRETCH"
    else:
        classification = "IGNORE"
    
    return ScoringResult(
        score=score,
        classification=classification,
        matched_signals=matched_signals,
        exclude_reason=None,
    )


def score_jobs(jobs: list) -> list:
    """Score a list of Job objects, adding scoring fields.
    
    Modifies jobs in place by adding:
    - job.score
    - job.classification
    - job.matched_signals
    - job.exclude_reason
    
    Args:
        jobs: List of Job objects
    
    Returns:
        The same list with scoring fields added
    """
    for job in jobs:
        description = getattr(job, "full_description", None) or getattr(job, "description", None)
        result = score_job(job.title, description)
        
        # Add scoring attributes to the job object
        job.score = result.score
        job.classification = result.classification
        job.matched_signals = ", ".join(result.matched_signals) if result.matched_signals else ""
        job.exclude_reason = result.exclude_reason or ""
    
    return jobs