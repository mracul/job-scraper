from __future__ import annotations

import json

from pipeline.requirements_analyzer import JobRequirementsAnalyzer


def test_analyze_job_counts_non_cert_categories():
    analyzer = JobRequirementsAnalyzer()
    job_text = "Requirements: Active Directory, PowerShell, and basic DNS troubleshooting."
    result = analyzer.analyze_job(job_text)

    assert "Active Directory" in result["presence"]["technical_skills"]
    assert any(w["term"] == "Active Directory" for w in result["weighted"]["technical_skills"])


def test_extract_jobs_jsonl_and_dedupe_by_source_id(tmp_path):
    path = tmp_path / "jobs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"_meta": {"keywords": "it support", "location": "Sydney"}}),
                json.dumps(
                    {
                        "source": "seek",
                        "source_id": "88896480",
                        "url": "https://www.seek.com.au/job/88896480",
                        "title": "IT Support Officer",
                        "company": "Example Co",
                        "description": "Active Directory and MS-900 required.",
                    }
                ),
                json.dumps(
                    {
                        "source": "seek",
                        "source_id": "88896480",
                        "url": "https://www.seek.com.au/job/88896480?tracking=foo",
                        "title": "IT Support Officer",
                        "company": "Example Co",
                        "description": "Duplicate of same job id.",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    analyzer = JobRequirementsAnalyzer()
    jobs, meta = analyzer.extract_jobs(str(path))
    assert meta["keywords"] == "it support"
    assert meta["location"] == "Sydney"

    analysis = analyzer.analyze_all_jobs(jobs, dedupe=True)
    assert analysis["total_jobs"] == 1


def test_extract_source_id_from_jobid_query_param(tmp_path):
    path = tmp_path / "jobs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"source": "seek", "url": "https://www.seek.com.au/role?jobid=123456"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    analyzer = JobRequirementsAnalyzer()
    jobs, _ = analyzer.extract_jobs(str(path))
    assert jobs[0]["source_id"] == "123456"
