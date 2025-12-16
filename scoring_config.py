
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
    
    # Soft skills / Core duties (+1 each)
    (r"\btroubleshoot(ing)?\b", 1, "Troubleshooting"),
    (r"\bcustomer\s*service\b", 1, "Customer Service"),
    (r"\bcommunication\s*skills?\b", 1, "Communication Skills"),
    
    # Technical basics (+1 each)
    (r"\bhardware\b", 1, "Hardware"),
    (r"\bnetworking\b", 1, "Networking"),
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
