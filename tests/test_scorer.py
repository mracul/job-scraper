"""Tests for job_scorer module."""

import pytest
from job_scorer import score_job, ScoringResult


class TestScoreJob:
    """Test deterministic job scoring."""

    def test_entry_level_job_scores_high(self):
        """Entry-level indicators should result in APPLY classification."""
        result = score_job(
            title="Junior IT Support Technician",
            description="Entry level position. Help desk support. No experience required."
        )
        assert result.classification == "APPLY"
        assert result.score >= 6
        assert result.exclude_reason is None

    def test_senior_role_hard_excluded(self):
        """Senior roles should be hard excluded (IGNORE)."""
        result = score_job(
            title="Senior IT Support Engineer",
            description="5+ years experience required. Lead a team of support staff."
        )
        assert result.classification == "IGNORE"
        assert result.score == 0
        assert result.exclude_reason is not None
        assert "Senior" in result.exclude_reason or "5+ years" in result.exclude_reason

    def test_manager_role_hard_excluded(self):
        """Manager roles should be hard excluded."""
        result = score_job(
            title="IT Support Manager",
            description="Manage the help desk team."
        )
        assert result.classification == "IGNORE"
        assert result.exclude_reason is not None

    def test_l1_support_scores_well(self):
        """L1/Level 1 support should score well."""
        result = score_job(
            title="L1 Support Analyst",
            description="Level 1 service desk support. Windows and Microsoft 365."
        )
        assert result.classification in ("APPLY", "STRETCH")
        assert result.score >= 4

    def test_neutral_job_is_stretch(self):
        """Job with no strong signals should be STRETCH."""
        result = score_job(
            title="IT Technician",
            description="General IT duties."
        )
        assert result.classification in ("STRETCH", "IGNORE")
        assert 3 <= result.score <= 6

    def test_l3_job_scores_lower(self):
        """L3/Level 3 roles should score lower."""
        result = score_job(
            title="Level 3 Support Engineer",
            description="Advanced troubleshooting. 4+ years experience."
        )
        # May be excluded or just low score
        assert result.score <= 5 or result.exclude_reason is not None

    def test_training_provided_boosts_score(self):
        """Training provided signal should boost score."""
        result = score_job(
            title="IT Support",
            description="Training provided. Will train the right candidate."
        )
        assert any("Training" in s or "train" in s.lower() for s in result.matched_signals)

    def test_matched_signals_populated(self):
        """Matched signals list should be populated."""
        result = score_job(
            title="Graduate Help Desk Analyst",
            description="Service desk role. ServiceNow ticketing."
        )
        assert len(result.matched_signals) > 0
        assert any("Graduate" in s for s in result.matched_signals)

    def test_empty_description_still_works(self):
        """Scoring should work with empty description."""
        result = score_job(title="Junior IT Support", description=None)
        assert isinstance(result.score, int)
        assert result.classification in ("APPLY", "STRETCH", "IGNORE")

    def test_msp_negative_signal(self):
        """MSP roles should have negative signal."""
        result = score_job(
            title="IT Support",
            description="Join our MSP team. Managed service provider."
        )
        assert any("MSP" in s for s in result.matched_signals)
