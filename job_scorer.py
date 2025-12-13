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


@dataclass
class ScoringResult:
    """Result of scoring a job listing."""
    score: int
    classification: str  # APPLY, STRETCH, IGNORE
    matched_signals: list[str]
    exclude_reason: Optional[str] = None


# Hard exclude patterns (force IGNORE regardless of score)
HARD_EXCLUDE_PATTERNS = [
    (r"\bsenior\b", "Senior role"),
    (r"\blead\b", "Lead role"),
    (r"\bmanager\b", "Manager role"),
    (r"\bdirector\b", "Director role"),
    (r"\bprincipal\b", "Principal role"),
    (r"\barchitect\b", "Architect role"),
    (r"\bhead of\b", "Head of role"),
    (r"\b5\+?\s*years?\b", "5+ years experience"),
    (r"\b6\+?\s*years?\b", "6+ years experience"),
    (r"\b7\+?\s*years?\b", "7+ years experience"),
    (r"\b8\+?\s*years?\b", "8+ years experience"),
    (r"\b10\+?\s*years?\b", "10+ years experience"),
]

# Positive signals (increase score)
POSITIVE_SIGNALS = [
    # Entry-level indicators (+2 each)
    (r"\bentry[- ]?level\b", 2, "Entry level"),
    (r"\bjunior\b", 2, "Junior"),
    (r"\bgraduate\b", 2, "Graduate"),
    (r"\btrainee\b", 2, "Trainee"),
    (r"\btraineeship\b", 2, "Traineeship"),
    (r"\bl1\b", 2, "L1"),
    (r"\blevel\s*1\b", 2, "Level 1"),
    (r"\btier\s*1\b", 2, "Tier 1"),
    
    # Support role titles (+1 each)
    (r"\bhelp\s*desk\b", 1, "Help desk"),
    (r"\bservice\s*desk\b", 1, "Service desk"),
    (r"\bit support\b", 1, "IT support"),
    (r"\bdesktop support\b", 1, "Desktop support"),
    (r"\btechnical support\b", 1, "Technical support"),
    (r"\bsupport technician\b", 1, "Support technician"),
    (r"\bsupport analyst\b", 1, "Support analyst"),
    (r"\bict support\b", 1, "ICT support"),
    (r"\bend user support\b", 1, "End user support"),
    
    # Beginner-friendly skills (+1 each)
    (r"\bwindows\s*(10|11)?\b", 1, "Windows"),
    (r"\bmicrosoft\s*365\b", 1, "Microsoft 365"),
    (r"\boffice\s*365\b", 1, "Office 365"),
    (r"\bactive\s*directory\b", 1, "Active Directory"),
    (r"\bticketing\b", 1, "Ticketing"),
    (r"\bservicenow\b", 1, "ServiceNow"),
    (r"\bjira\b", 1, "Jira"),
    (r"\bfreshdesk\b", 1, "Freshdesk"),
    (r"\bzendesk\b", 1, "Zendesk"),
    
    # Training/growth signals (+1 each)
    (r"\btraining provided\b", 1, "Training provided"),
    (r"\bwill train\b", 1, "Will train"),
    (r"\bno experience\s*(required|necessary|needed)?\b", 2, "No experience required"),
    (r"\bcareer\s*start\b", 1, "Career start"),
    (r"\bkick\s*start\b", 1, "Kick start"),
]

# Negative signals (decrease score)
NEGATIVE_SIGNALS = [
    # Seniority indicators (-2 each)
    (r"\b3\+?\s*years?\b", -1, "3+ years experience"),
    (r"\b4\+?\s*years?\b", -2, "4+ years experience"),
    (r"\blevel\s*2\b", -1, "Level 2"),
    (r"\bl2\b", -1, "L2"),
    (r"\btier\s*2\b", -1, "Tier 2"),
    (r"\blevel\s*3\b", -2, "Level 3"),
    (r"\bl3\b", -2, "L3"),
    
    # Complex/specialist roles (-1 each)
    (r"\bsysadmin\b", -1, "Sysadmin"),
    (r"\bsystem\s*admin", -1, "System admin"),
    (r"\bnetwork\s*engineer\b", -1, "Network engineer"),
    (r"\bdevops\b", -2, "DevOps"),
    (r"\bcloud\s*engineer\b", -1, "Cloud engineer"),
    (r"\bsecurity\s*engineer\b", -1, "Security engineer"),
    (r"\bcybersecurity\b", -1, "Cybersecurity"),
    
    # MSP/contractor signals (-1 each, often high churn)
    (r"\bmanaged\s*service\s*provider\b", -1, "MSP"),
    (r"\bmsp\b", -1, "MSP"),
]


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
