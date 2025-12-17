from pipeline.requirements_analyzer import JobRequirementsAnalyzer


def test_training_provided_detection_in_benefits():
    analyzer = JobRequirementsAnalyzer()

    text = """
    We offer full training provided for the right candidate.
    This is an entry-level role and we will train you on the job.
    You'll have mentoring and coaching as part of our buddy system.
    We also support professional development and paid certifications.
    """

    result = analyzer.analyze_job(text)
    benefits = set(result['presence'].get("benefits", []))

    assert "Training Provided" in benefits
    assert "Mentoring/Coaching" in benefits
    assert "Professional Development" in benefits
    assert "Certification Support" in benefits
