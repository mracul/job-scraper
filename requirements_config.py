
# Certification patterns - specific named certifications
CERTIFICATION_PATTERNS = {
    # Microsoft Certifications (modern role-based codes)
    # Note: Keep these specific buckets FIRST so they win in reporting.
    # --- Microsoft role-based cert codes (most useful) ---
    'Microsoft 365 Certification (MS-xxx)': r'\bMS-\d{3}\b',
    'Azure Certification (AZ-xxx)': r'\bAZ-\d{3}\b',
    'Modern Workplace / Endpoint (MD-xxx)': r'\bMD-\d{3}\b',
    'Security / Compliance (SC-xxx)': r'\bSC-\d{3}\b',
    'Power Platform (PL-xxx)': r'\bPL-\d{3}\b',
    'Data / AI (DP-xxx)': r'\bDP-\d{3}\b',
    'Dynamics 365 (MB-xxx)': r'\bMB-\d{3}\b',
    'Developer (MSFT misc: AI/Dev/Identity) (AI/AD/WS-xxx)': r'\b(AI|AD|WS)-\d{3}\b',

    # --- Generic Microsoft certification wording (legacy + vague HR phrasing) ---
    # Keep this, but remove AZ-/MS- matches from here so codes don't double-count.
    'Microsoft Certified (Generic/Legacy)': r'\b(Microsoft\s+Certified|MCP|MCSE|MCSA|MCSD)\b',
    
    # CompTIA Certifications - match both "CompTIA X+" and standalone "X+" in cert contexts
    'CompTIA A+': r'\bCompTIA\s*A\+|\bA\+(?=\s*[,.\)\]\s]|$)',
    'CompTIA Network+': r'\bCompTIA\s*Network\+|\bNetwork\+',
    'CompTIA Security+': r'\bCompTIA\s*Security\+|\bSecurity\+',
    'CompTIA Server+': r'\bCompTIA\s*Server\+|\bServer\+',
    'CompTIA Cloud+': r'\bCompTIA\s*Cloud\+|\bCloud\+',
    'CompTIA Linux+': r'\bCompTIA\s*Linux\+|\bLinux\+',
    'CompTIA CySA+': r'\bCompTIA\s*CySA\+|\bCySA\+',
    'CompTIA PenTest+': r'\bCompTIA\s*PenTest\+|\bPenTest\+',
    
    # ITIL - captures ITIL with optional version/foundation
    'ITIL': r'\bITIL\s*(\d|Foundation|v\d|Practitioner|Expert)?\b',
    
    # Cisco
    'CCNA': r'\bCCNA\b',
    'CCNP': r'\bCCNP\b',
    'CCIE': r'\bCCIE\b',
    'Cisco Certified': r'\bCisco\s+Certified\b',
    
    # Cloud
    'AWS Certified': r'\bAWS\s+(Certified|Solutions\s+Architect|Developer|SysOps)\b',
    'Google Cloud Certified': r'\b(Google\s+Cloud|GCP)\s+(Certified|Professional|Associate)\b',
    
    # Security
    'CISSP': r'\bCISSP\b',
    'CISM': r'\bCISM\b',
    
    # Vendor Specific
    'VMware Certified': r'\b(VMware|VCP|VCAP)\s*(Certified|Professional)?\b',
    
    # Additional certifications
    'Certified (Generic)': r'\b[Cc]ertified\s+(in|for|as)\b|\b[Cc]ertification\s+(in|for|required|preferred|desired)',
}

# Microsoft certification code to friendly name mapping
MICROSOFT_CERT_CODE_MAP = {
    "MS-900": "Microsoft 365 Fundamentals",
    "AZ-900": "Azure Fundamentals",
    "SC-900": "Security, Compliance, and Identity Fundamentals",
    "AI-900": "Azure AI Fundamentals",
    "DP-900": "Azure Data Fundamentals",
    "PL-900": "Power Platform Fundamentals",
    "MD-102": "Endpoint Administrator",
    "MS-102": "Microsoft 365 Administrator",
    "AZ-104": "Azure Administrator",
    "AZ-305": "Azure Solutions Architect Expert",
    "AZ-500": "Azure Security Engineer",
    "SC-300": "Identity and Access Administrator",
}

# Education/Qualification patterns
EDUCATION_PATTERNS = {
    'Bachelor Degree': r"\b(Bachelor'?s?\s*(Degree)?|BSc|B\.?Sc|BA|B\.?A)\b.*?(Computer\s+Science|IT|Information\s+Technology|Engineering)?",
    'Diploma': r'\b(Diploma|Dip\.?)\b.*?(IT|Information\s+Technology|Computing)?',
    'Certificate IV': r'\bCertificate\s*(IV|4)\b.*?(IT|Information\s+Technology)?',
    'Certificate III': r'\bCertificate\s*(III|3)\b.*?(IT|Information\s+Technology)?',
    'Tertiary Qualification': r'\b[Tt]ertiary\s+[Qq]ualification',
    'Degree in IT': r'\b[Dd]egree\b.*?(IT|Information\s+Technology|Computer\s+Science)',
    'TAFE': r'\bTAFE\b',
}

# Technical skills patterns
TECHNICAL_SKILLS = {
    # Operating Systems
    'Windows': r'\bWindows\b',  # Generic Windows (catches all)
    'Windows 10/11': r'\bWindows\s*(10|11|10\/11)\b',  # Specific desktop versions
    'Windows Server': r'\bWindows\s*Server\s*(\d{4})?\b',
    'macOS': r'\b(macOS|Mac\s*OS|Apple\s*(Mac|Desktop)|Mac\s*(computer|laptop)?)\b',
    'Linux': r'\b(Linux|Ubuntu|CentOS|RedHat|RHEL|Debian)\b',
    
    # Microsoft Stack
    'Microsoft 365': r'\b(Microsoft\s*365|M365|MS\s*365|Office\s*365|O365)\b',
    'Microsoft Office': r'\b(Microsoft\s*Office|MS\s*Office|Office\s*(Suite|applications?)?)\b',  # Non-365 Office
    'Active Directory': r'\b(Active\s*Directory|\bAD\b(?=\s*(admin|user|account|group|domain|forest|object|management|experience|knowledge)))\b',  # AD with context
    'Azure AD/Entra': r'\b(Azure\s*AD|Entra\s*ID|Azure\s*Active\s*Directory|EntraID|AAD)\b',
    'Exchange': r'\bExchange\s*(Online|Server)?\b',
    'SharePoint': r'\bSharePoint\b',
    'Teams': r'\b(Microsoft\s+)?Teams\b',
    'Intune': r'\b(Microsoft\s*)?Intune\b',
    'SCCM/Endpoint Manager': r'\b(SCCM|System\s*Center|Endpoint\s*Manager|ConfigMgr|MEM)\b',
    'PowerShell': r'\bPowerShell\b',
    'Group Policy': r'\b(Group\s*Policy|GPO)\b',
    'Azure': r'\bAzure\b(?!\s*(AD|Active\s*Directory))',
    'OneDrive': r'\bOneDrive\b',
    'Outlook': r'\bOutlook\b',
    
    # Networking
    'TCP/IP': r'\bTCP\/IP\b',
    'DNS': r'\bDNS\b',
    'DHCP': r'\bDHCP\b',
    'VPN': r'\bVPN\b',
    'Firewall': r'\b[Ff]irewall\b',
    'LAN/WAN': r'\b(LAN|WAN|LAN\/WAN)\b',
    'Networking': r'\b[Nn]etwork(ing|s)?\b',  # Simplified - catches more
    'VoIP/IP Telephony': r'\b(IP\s*[Tt]elephon|VOIP|VoIP|IP\s*[Pp]hone|telephony)\b',
    'Wi-Fi': r'\b(Wi-?Fi|WiFi|[Ww]ireless)\b',
    
    # Virtualization & Cloud
    'VMware': r'\bVMware\b',
    'Hyper-V': r'\bHyper-?V\b',
    'Citrix': r'\bCitrix\b',
    'Cloud Services': r'\b[Cc]loud\b',  # Simplified - catches cloud anything
    'AWS': r'\bAWS\b',
    
    # Remote & AV Support
    'Remote Support Tools': r'\b(TeamViewer|RDP|Remote\s*Desktop|AnyDesk|LogMeIn|ConnectWise)\b',
    'Video Conferencing': r'\b(Video\s*[Cc]onferenc|Zoom|WebEx|Polycom|Surface\s*Hub|Google\s*Meet)\b',
    'AV Support': r'\b(AV\s*support|[Aa]udio[\s-]*[Vv]isual)\b',
    
    # Ticketing/ITSM
    'ServiceNow': r'\bServiceNow\b',
    'Zendesk': r'\bZendesk\b',
    'Freshdesk': r'\bFresh[Dd]esk\b',
    'JIRA': r'\bJIRA\b',
    'Ticketing System': r'\b[Tt]icketing\s*[Ss]ystem\b',
    'ITSM Tools': r'\b(ITSM|ManageEngine|FreshService|Autotask|ConnectWise\s*Manage|Halo\s*PSA)\b',
    
    # Mobile Device Management
    'MDM': r'\bMDM\b|Mobile\s*Device\s*Management',
    'JAMF': r'\bJAMF\b',
    'Mobile Devices': r'\b(mobile\s*device|iOS|Android|iPhone|iPad|smartphone|tablet)\b',
    
    # Hardware & Deployment
    'Hardware': r'\b[Hh]ardware\b',  # Generic hardware
    'Printers': r'\b[Pp]rinter\b',  # Simplified
    'System Imaging': r'\b[Ii]maging\b',
    'Software Deployment': r'\b(software\s*)?[Dd]eployment\b',
    'Patching': r'\b[Pp]atch(ing|es)?\b',
    'Laptop/Desktop': r'\b(laptop|desktop|PC|workstation)\b',
    
    # Database & Scripting
    'SQL/Database': r'\b(SQL|MSSQL|[Dd]atabase)\b',
    'Scripting': r'\b[Ss]cripting\b',
    'Programming': r'\b(Python|PowerShell|Go|React|JavaScript|TypeScript|C#|\.NET|programming|coding)\b',
    
    # Security
    'Security': r'\b[Ss]ecurity\b',
    'Mimecast': r'\bMimecast\b',
    'Backup': r'\b[Bb]ackup\b',
    'Antivirus/EDR': r'\b(antivirus|anti-virus|EDR|endpoint\s*detection|CrowdStrike|Defender|Sophos|Sentinel\s*One)\b',
    'MFA/2FA': r'\b(MFA|2FA|multi[\s-]*factor|two[\s-]*factor)\b',
    
    # Vendor Specific
    'Cisco': r'\bCisco\b',
    'Fortinet': r'\bFortinet\b',
    'Meraki': r'\bMeraki\b',
    'UniFi': r'\bUniFi\b',
    'HP/HPE': r'\b(HP|HPE|Hewlett[\s-]*Packard)\b',
    'Dell': r'\bDell\b',
    'Lenovo': r'\bLenovo\b',
    
    # New additions
    'Phone Support': r'\b(phone\s*support|answering\s*calls|taking\s*calls)\b',
    'Monitoring': r'\b(monitoring|alerts|RMM|SolarWinds|N-able|Datto)\b',
    'Infrastructure': r'\b[Ii]nfrastructure\b',
}

# Soft skills patterns
SOFT_SKILLS = {
    'Customer Service': r'\b[Cc]ustomer\s*[Ss]ervice\b',
    'Communication Skills': r'\b[Cc]ommunication\s*[Ss]kills?\b',
    'Problem Solving': r'\b[Pp]roblem[\s-]*[Ss]olving\b',
    'Troubleshooting': r'\b[Tt]roubleshoot(ing)?\b',
    'Team Player': r'\b[Tt]eam\s*[Pp]layer\b',
    'Time Management': r'\b[Tt]ime\s*[Mm]anagement\b',
    'Attention to Detail': r'\b[Aa]ttention\s*to\s*[Dd]etail\b',
    'Work Independently': r'\b[Ww]ork\s*[Ii]ndependently\b',
    'Proactive': r'\b[Pp]roactive\b',
}

# Experience patterns
EXPERIENCE_PATTERNS = {
    '1+ years': r'\b(1|one)\+?\s*years?\b.*?experience',
    '2+ years': r'\b(2|two)\+?\s*years?\b.*?experience',
    '3+ years': r'\b(3|three)\+?\s*years?\b.*?experience',
    '5+ years': r'\b(5|five)\+?\s*years?\b.*?experience',
    '1-2 years': r'\b1[\s-]*(to|-)?\s*2\s*years?\b',
    '2-3 years': r'\b2[\s-]*(to|-)?\s*3\s*years?\b',
    '3-5 years': r'\b3[\s-]*(to|-)?\s*5\s*years?\b',
    'MSP': r'\bMSP\b|\bmanaged\s+service\s+providers?\b',
    'MSP Experience': r'\bMSP\b.*?experience|experience.*?\bMSP\b',
    'Service Desk Experience': r'\b[Ss]ervice\s*[Dd]esk\b.*?experience',
    'Help Desk Experience': r'\b[Hh]elp\s*[Dd]esk\b.*?experience',
}

# Support levels and ITSM processes
SUPPORT_LEVELS = {
    'Level 1/Tier 1 Support': r'\b(Level\s*1|L1|Tier\s*1|first[\s-]*line)\b',
    'Level 2/Tier 2 Support': r'\b(Level\s*2|L2|Tier\s*2|second[\s-]*line)\b',
    'Level 3/Tier 3 Support': r'\b(Level\s*3|L3|Tier\s*3|third[\s-]*line)\b',
    'Desktop Support': r'\b[Dd]esktop\s*[Ss]upport\b',
    'Remote Support': r'\b[Rr]emote\s*[Ss]upport\b',
    'Field Service/On-site': r'\b([Ff]ield\s*[Ss]ervice|[Oo]n[\s-]*[Ss]ite\s*[Ss]upport)\b',
    'Deskside Support': r'\b[Dd]eskside\s*[Ss]upport\b',
    'Incident Management': r'\b[Ii]ncident\s*(management|handling|resolution)?\b',
    'Problem Management': r'\b[Pp]roblem\s*[Mm]anagement\b',
    'Escalation': r'\b[Ee]scalat(e|ion|ing)\b',
    'SLA Management': r'\b(SLA|[Ss]ervice\s*[Ll]evel)\b',
    'Knowledge Base': r'\b[Kk]nowledge\s*[Bb]ase\b',
    'Triage': r'\b[Tt]riage\b',
}

# Work arrangements
WORK_ARRANGEMENTS = {
    'Full-time': r'\b[Ff]ull[\s-]*[Tt]ime\b',
    'Part-time': r'\b[Pp]art[\s-]*[Tt]ime\b',
    'Casual': r'\b[Cc]asual\b',
    'Contract/Fixed-term': r'\b([Cc]ontract|[Ff]ixed[\s-]*[Tt]erm)\b',
    'Permanent': r'\b[Pp]ermanent\b',
    'On-site Work': r'\b[Oo]n[\s-]*[Ss]ite\b(?!\s*support)',
    'Hybrid Working': r'\b[Hh]ybrid\s*([Ww]ork|[Mm]odel)?\b',
    'Work from Home/Remote': r'\b([Ww]ork\s*[Ff]rom\s*[Hh]ome|WFH|[Rr]emote\s*[Ww]ork)\b',
    'Flexible Work': r'\b[Ff]lexible\s*([Ww]ork|[Hh]ours)\b',
    'Traineeship': r'\b[Tt]raineeship\b',
    'Junior Level': r'\b[Jj]unior\b',
    'Mid-level': r'\b[Mm]id[\s-]*[Ll]evel\b',
    'Senior Level': r'\b[Ss]enior\b',
}

# Benefits/Perks
BENEFITS = {
    'NFP/Salary Packaging': r'\b(NFP|[Nn]ot[\s-]*[Ff]or[\s-]*[Pp]rofit|[Ss]alary\s*[Pp]ackaging)\b',
    'Career Development': r'\b[Cc]areer\s*([Dd]evelopment|[Pp]rogression|[Gg]rowth)\b',
    # Training-related benefits (explicit signals that training is provided/supported)
    'Training Provided': r'\b(full\s+training|comprehensive\s+training|paid\s+training|training\s+(provided|included|available)|on[\s-]*the[\s-]*job\s+training|we\s+will\s+train\s+you)\b',
    'Mentoring/Coaching': r'\b(mentor(ing|ship)?|coaching|buddy\s+system)\b',
    'Professional Development': r'\b(professional\s+development|learning\s*(and|&)\s*development|L\s*&\s*D|upskilling|training\s*(and|&)\s*development)\b',
    'Certification Support': r'\b(certification\s*(support|assistance|reimburs(e|ed|ement)|fund(ed|ing)|paid)|paid\s+certifications?)\b',
    # Backwards-compatible umbrella tag (kept, but tightened to benefit-like phrasing)
    'Training/Certification': r'\b(training|certification)\s*(opportunit(y|ies)|support|provided|available|fund(ed|ing)|reimburs(e|ed|ement)|assistance)\b',
    'Gym/Fitness Benefits': r'\b([Gg]ym|[Ff]itness\s*[Pp]assport|[Ff]itness\s*[Bb]enefit)\b',
    'Free Parking': r'\b([Ff]ree\s*[Pp]arking|[Pp]arking\s*[Oo]n[\s-]*[Ss]ite)\b',
    'Company Vehicle': r'\b[Cc]ompany\s*([Vv]ehicle|[Cc]ar)\b',
    'Bonus': r'\b([Pp]erformance\s*)?[Bb]onus\b',
    'EAP': r'\b(EAP|[Ee]mployee\s*[Aa]ssistance)\b',
}

# Other requirements
OTHER_REQUIREMENTS = {
    'Driver License': r"\b([Dd]river'?s?\s*[Ll]icen[cs]e|[Cc]lass\s*C\s*[Ll]icen[cs]e)\b",
    'Working with Children Check': r'\b(WWCC|Working\s*[Ww]ith\s*[Cc]hildren)\b',
    'Police Check': r'\b[Pp]olice\s*[Cc]heck\b',
    'Australian Citizen/PR': r'\b(Australian\s*(Citizen|PR|Permanent\s*Resident)|work\s*rights)\b',
    'On-call/After Hours': r'\b([Oo]n[\s-]*[Cc]all|[Aa]fter[\s-]*[Hh]ours)\b',
    'Travel Required': r'\b[Tt]ravel\s*(required|between|to\s*sites?)\b',
    'First Aid Certificate': r'\b[Ff]irst\s*[Aa]id\b',
    'HSC/Year 12': r'\b(HSC|[Yy]ear\s*12)\b',
    'Onboarding/Offboarding': r'\b([Oo]nboarding|[Oo]ffboarding)\b',
    'IT Asset Management': r'\b([Ii]t\s*)?[Aa]sset\s*[Mm]anagement\b',
    'Documentation': r'\b[Dd]ocument(ation|ing)\b',
    'User Provisioning': r'\b[Uu]ser\s*[Pp]rovisioning\b',
    'Compliance': r'\b[Cc]ompliance\b',
}
