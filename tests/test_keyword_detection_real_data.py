import pytest
from job_scorer import score_job
from models import Job # Still needed to create the Job object for score_job

def test_keyword_detection_on_real_job_description_scorer():
    # Real job description scraped from Jora (Stoic-IT, Helpdesk Consultant)
    description = """
Stoic IT is a leading provider of IT consulting and managed services, with a 100% focus on helping healthcare businesses across Australia and New Zealand.

Due to continued growth in our customer base, we are seeking a motivated and enthusiastic individual to join our dynamic support team

This role offers the opportunity to work in a collaborative setting that promotes continuous learning and career advancement in IT.

Previous IT experience (whether vocational, educational or recreational) is a requirement, but we are really looking for people who are genuinely interested in IT and want to learn.

As a Helpdesk Consultant, you'll be the first point of contact for our customers, helping them resolve technical issues and ensuring their systems run smoothly.

You will gain hands-on experience in a wide range of technologies while developing your skills in troubleshooting, communication and customer service.

Your daily responsibilities include:

·         Responding to client support requests via phone or ticketing system.

·         Monitoring alerts and notifications

·         Diagnosing and resolving hardware, software and networking issues

·         Escalating complex problems to senior team members as required

·         Documenting solutions and contributing to our knowledge base

·         Carry out scheduled and unscheduled onsite visits at client sites

·         Project work deploying and upgrading client infrastructure

What we are looking for:

·         Ability to implement troubleshooting strategies

·         Ability to communicate clearly and professionally with clients

·         Ability to work efficiently and prioritise tasks

·         A proactive attitude and eagerness to learn

·         Some exposure to IT systems

·         Immediate start available

What we offer:

·         Supportive team culture with mentorship and training

·         Opportunities for career growth

·         Exposure to a wide variety of technologies
    """
    
    # Create a dummy job with this description and title
    job = Job(
        title="Helpdesk Consultant",
        company="Stoic-IT",
        location="Marrickville NSW",
        salary=None, # Added missing salary field
        description="", # Not using this, using full_description
        full_description=description,
        url="http://example.com",
        source="jora"
    )
    
    # Run scoring directly
    result = score_job(job.title, job.full_description)
    
    # matched_signals are already descriptive strings like "+1 Help desk"
    matched_signals = result.matched_signals
    
    print(f"Matched signals: {matched_signals}")
    print(f"Classification: {result.classification}")
    print(f"Score: {result.score}")
    print(f"Exclude Reason: {result.exclude_reason}")

    # The job contains "senior team members" which is a hard exclude pattern.
    # Therefore, we expect a hard exclude.
    assert "❌ Senior role" in matched_signals
    assert result.exclude_reason == "Senior role"
    assert result.score == 0
    assert result.classification == "IGNORE"

    # We do NOT assert for positive signals because a hard exclude prevents them from being added.
