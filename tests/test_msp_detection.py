from analyze_requirements import JobRequirementsAnalyzer


def test_msp_tag_detected_from_abbreviation_or_phrase():
    analyzer = JobRequirementsAnalyzer()

    text_1 = "This role is with an MSP supporting multiple clients."
    result_1 = analyzer.analyze_job(text_1)
    assert "MSP" in set(result_1.get("experience", []))

    text_2 = "Join our managed service provider team and work across diverse environments."
    result_2 = analyzer.analyze_job(text_2)
    assert "MSP" in set(result_2.get("experience", []))
