"""
Job Requirements Analyzer
Extracts and analyzes certifications, qualifications, skills, and experience 
requirements from compiled job listings.
"""

import re
import os
from collections import Counter
from pathlib import Path
import json
import hashlib
from datetime import datetime
import math
from bisect import bisect_right
import unicodedata


def norm(s: str) -> str:
    """Normalize string for better deduplication."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def canonicalize_url(url: str) -> str:
    """Normalize URL for stable deduplication."""
    url = (url or "").strip()
    if not url:
        return ""
    url = url.split("#", 1)[0].split("?", 1)[0]
    return url.strip()


def _maybe_extract_source_id(source: str, url: str) -> str | None:
    """Best-effort source_id extractor for common job URL formats."""
    raw = (url or "").strip()
    if not raw:
        return None
    src = norm(source)
    if src == "seek":
        # First try query-based IDs before stripping query params.
        m = re.search(r"\bjobid=(\d+)\b", raw, re.IGNORECASE)
        if m:
            return m.group(1)

        # Then try canonical path-based IDs.
        url2 = canonicalize_url(raw)
        m = re.search(r"/job/(\d+)\b", url2)
        if m:
            return m.group(1)
    return None


class JobRequirementsAnalyzer:
    """Analyzes job listings to extract commonly requested requirements."""

    def __init__(self):
        # Certification patterns - specific named certifications
        self.certification_patterns = {
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
        self.microsoft_cert_code_map = {
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
        self.education_patterns = {
            'Bachelor Degree': r"\b(Bachelor'?s?\s*(Degree)?|BSc|B\.?Sc|BA|B\.?A)\b.*?(Computer\s+Science|IT|Information\s+Technology|Engineering)?",
            'Diploma': r'\b(Diploma|Dip\.?)\b.*?(IT|Information\s+Technology|Computing)?',
            'Certificate IV': r'\bCertificate\s*(IV|4)\b.*?(IT|Information\s+Technology)?',
            'Certificate III': r'\bCertificate\s*(III|3)\b.*?(IT|Information\s+Technology)?',
            'Tertiary Qualification': r'\b[Tt]ertiary\s+[Qq]ualification',
            'Degree in IT': r'\b[Dd]egree\b.*?(IT|Information\s+Technology|Computer\s+Science)',
            'TAFE': r'\bTAFE\b',
        }
        
        # Technical skills patterns
        self.technical_skills = {
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
        }
        
        # Soft skills patterns
        self.soft_skills = {
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
        self.experience_patterns = {
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
        self.support_levels = {
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
        self.work_arrangements = {
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
        self.benefits = {
            'NFP/Salary Packaging': r'\b(NFP|[Nn]ot[\s-]*[Ff]or[\s-]*[Pp]rofit|[Ss]alary\s*[Pp]ackaging)\b',
            'Career Development': r'\b[Cc]areer\s*([Dd]evelopment|[Pp]rogression|[Gg]rowth)\b',
            # Training-related benefits (explicit signals that training is provided/supported)
            'Training Provided': r'\b(full\s+training|comprehensive\s+training|paid\s+training|training\s+(provided|included|available)|on[\s-]*the[\s-]*job\s+training|we\s+will\s+train\s+you)\b',
            'Mentoring/Coaching': r'\b(mentor(ing)?|coaching|buddy\s+system)\b',
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
        self.other_requirements = {
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

    def _context_label_and_weight(self, match_start: int, match_end: int, job_text: str) -> tuple[str, float]:
        """Determine context label and weight for a match based on its position and surrounding text.
        
        Returns:
            (label, weight) where label is 'required', 'preferred', 'bonus', 'context'
            and weight is a multiplier (1.0 = required, 0.8 = preferred, 0.5 = bonus, 0.2 = context)
        """
        # Get window around match (100 chars before and after)
        window_start = max(0, match_start - 100)
        window_end = min(len(job_text), match_end + 100)
        window = job_text[window_start:window_end].lower()
        
        # Look back to start of the current line for bullet detection
        line_start = job_text.rfind('\n', 0, match_start) + 1
        line = job_text[line_start:match_start]
        has_bullet = bool(re.match(r'^\s*([-•*·]|\d+[\.\)])\s+', line))
        
        # Define keywords and section hints
        required_words = ['required', 'must have', 'essential', 'mandatory']
        preferred_words = ['preferred', 'desirable', 'nice to have', 'advantage', 'beneficial']
        bonus_words = ['bonus', 'plus', 'would be great', 'great if', 'helpful if']
        
        # Add section hints (strong)
        section_required = ['requirements', 'what we are looking for', 'essential', 'key requirements', 'skills and experience']
        section_preferred = ['desirable', 'nice to have', 'preferred']
        
        # If window contains a requirement section header nearby, boost confidence
        if any(s in window for s in section_required) and any(w in window for w in required_words):
            return ('required', 1.0)
        if any(s in window for s in section_preferred) and any(w in window for w in preferred_words):
            return ('preferred', 0.8)
        
        # Otherwise fall back to keyword-only (more conservative)
        if any(w in window for w in required_words):
            return ('required', 1.0)
        if any(w in window for w in preferred_words):
            return ('preferred', 0.8)
        if any(w in window for w in bonus_words):
            return ('bonus', 0.5)
        
        # If in bullet point, assume required unless contradicted
        if has_bullet:
            return ('required', 1.0)
        
        # Default to context (weakest)
        return ('context', 0.2)

    def _passes_term_gate(
        self,
        term: str,
        matched: str,
        job_text: str,
        category: str,
        match_start: int,
        match_end: int,
    ) -> bool:
        """Apply term-specific gating logic to filter out false positives.
        
        Uses a local window around the match instead of the entire job text.
        
        Returns True if the term should be counted, False if it's likely a false positive.
        """
        # Get local window around match (200 chars before and after for gating)
        window_start = max(0, match_start - 200)
        window_end = min(len(job_text), match_end + 200)
        window = job_text[window_start:window_end].lower()
        term_lower = term.lower()
        matched_lower = (matched or "").lower()
        
        # Education gating - avoid false positives in non-education contexts
        if category == 'education':
            # Skip if term appears in unrelated contexts
            if term_lower in ['diploma', 'certificate'] and any(word in window for word in ['driver', 'license', 'driving']):
                return False
            if term_lower == 'tafe' and 'tafe' in window and not any(edu_word in window for edu_word in ['education', 'qualification', 'study', 'degree']):
                return False
        
        # Technical skills gating - more permissive now
        elif category == 'technical_skills':
            # For vendor names, only gate if clearly company boilerplate (not requirements)
            if term_lower in ['cisco', 'fortinet', 'meraki', 'unifi', 'vmware', 'citrix', 'hp/hpe', 'dell', 'lenovo']:
                # Skip only if explicitly in "about us" / company description context
                company_context_phrases = ['we are', 'our company', 'about us', 'we use', 'our partner', 'partner with']
                if any(phrase in window for phrase in company_context_phrases):
                    # But still count if there's also a requirement signal
                    req_signals = ['experience', 'knowledge', 'skills', 'required', 'preferred', 'familiar', 'understanding', 'proficien']
                    if not any(sig in window for sig in req_signals):
                        return False
        
        # Experience gating
        elif category == 'experience':
            # Skip MSP mentions when it's clearly company context (not a candidate requirement)
            if term in ['MSP', 'MSP Experience']:
                has_company_context = any(
                    p in window
                    for p in [
                        'our msp',
                        'we are an msp',
                        'msp company',
                        'msp firm',
                        'msp provider',
                        'managed service provider',
                        'managed services provider',
                        'we are a managed service provider',
                        'join our managed services',
                    ]
                )
                has_requirement = any(
                    w in window
                    for w in [
                        'experience',
                        'background',
                        'required',
                        'preferred',
                        'looking for',
                        'candidate',
                    ]
                )
                if has_company_context and not has_requirement:
                    return False
            return True
        
        # Support levels gating
        elif category == 'support_levels':
            # Skip generic mentions that aren't about support levels
            if term_lower in ['level 1', 'level 2', 'level 3'] and not any(support_word in window for support_word in ['support', 'tier', 'line', 'help desk', 'service desk']):
                return False
        
        return True

    def extract_jobs_from_markdown(self, filepath: str) -> tuple[list, dict]:
        """Extract individual job descriptions and search metadata from compiled markdown file.

        Returns:
            (jobs, metadata) where metadata contains 'keywords', 'location', 'generated', etc.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract search metadata from header (before first job)
        metadata = {
            'keywords': None,
            'location': None,
            'generated': None,
            'search_mode': None,
        }
        header_match = re.search(r'^(.*?)(?=---\s*\n\s*## Job #)', content, re.DOTALL)
        if header_match:
            header = header_match.group(1)
            kw_match = re.search(r'\*\*Search Keywords:\*\*\s*(.+)', header)
            if kw_match:
                metadata['keywords'] = kw_match.group(1).strip()
            loc_match = re.search(r'\*\*Search Location:\*\*\s*(.+)', header)
            if loc_match:
                metadata['location'] = loc_match.group(1).strip()
            gen_match = re.search(r'\*\*Generated:\*\*\s*(.+)', header)
            if gen_match:
                metadata['generated'] = gen_match.group(1).strip()
            mode_match = re.search(r'\*\*Search Mode:\*\*\s*(.+)', header)
            if mode_match:
                metadata['search_mode'] = mode_match.group(1).strip()
        
        # Split by job headers (primary method)
        job_sections = re.split(r'---\s*\n\s*## Job #\d+:', content)
        
        # Fallback: if markdown splitting didn't work, try plaintext "JOB #" blocks
        if len(job_sections) <= 1:
            job_sections = re.split(r'={10,}\s*\nJOB\s*#\d+\s*\n={10,}', content)
        
        jobs = []
        for i, section in enumerate(job_sections[1:], 1):  # Skip header
            # Extract title - try multiple formats
            title = f"Job {i}"
            lines = section.strip().split('\n')
            
            # Try markdown format first
            if lines and not lines[0].startswith('**'):
                title = lines[0].strip()
            
            # Try plaintext format
            title_match = re.search(r'TITLE:\s*(.+)', section, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            
            # Extract company - try multiple formats
            company = "Unknown"
            
            # Try markdown table format
            company_match = re.search(r'\*\*Company\*\*\s*\|\s*([^\|]+)', section)
            if company_match:
                company = company_match.group(1).strip()
            else:
                # Try plaintext format
                company_match = re.search(r'COMPANY:\s*(.+)', section, re.IGNORECASE)
                if company_match:
                    company = company_match.group(1).strip()

            # Extract URL/source when present (enables stronger dedupe + reporting)
            url = None
            source = None

            url_match = re.search(r'\*\*URL\*\*\s*\|\s*\[[^\]]*\]\(([^)]+)\)', section)
            if url_match:
                url = url_match.group(1).strip()
            else:
                url_match = re.search(r'URL:\s*(.+)', section, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1).strip()

            src_match = re.search(r'\*\*Source\*\*\s*\|\s*([^\|]+)', section)
            if src_match:
                source = src_match.group(1).strip()
            else:
                src_match = re.search(r'SOURCE:\s*(.+)', section, re.IGNORECASE)
                if src_match:
                    source = src_match.group(1).strip()

            source_id = _maybe_extract_source_id(source or "", url or "")

            jobs.append({
                'id': i,
                'title': title,
                'company': company,
                'description': section,
                'url': url,
                'source': source,
                'source_id': source_id,
            })

        return jobs, metadata

    def extract_jobs_from_jsonl(self, filepath: str) -> tuple[list, dict]:
        """Load jobs from JSONL (one job object per line, optional _meta line)."""
        jobs: list[dict] = []
        metadata: dict = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("_meta"):
                    metadata = obj["_meta"] or {}
                    continue
                if not isinstance(obj, dict):
                    continue

                description = obj.get("description")
                if not description:
                    description = obj.get("full_description") or obj.get("text") or ""

                url = obj.get("url")
                source = obj.get("source")
                source_id = obj.get("source_id") or _maybe_extract_source_id(source or "", url or "")

                jobs.append(
                    {
                        "id": len(jobs) + 1,
                        "title": obj.get("title") or f"Job {len(jobs) + 1}",
                        "company": obj.get("company") or "Unknown",
                        "description": description,
                        "url": url,
                        "source": source,
                        "source_id": source_id,
                    }
                )
        return jobs, metadata

    def extract_jobs(self, filepath: str) -> tuple[list, dict]:
        """Extract jobs from a supported input format (.md or .jsonl)."""
        suffix = Path(filepath).suffix.lower()
        if suffix == ".jsonl":
            return self.extract_jobs_from_jsonl(filepath)
        return self.extract_jobs_from_markdown(filepath)

    def analyze_job(self, job_text: str) -> dict:
        """Analyze a single job description for all requirement types.
        
        Returns dict with 'presence' (simple counts) and 'weighted' (context-aware scores).
        """
        results = {
            'presence': {
                'certifications': [],
                'education': [],
                'technical_skills': [],
                'soft_skills': [],
                'experience': [],
                'support_levels': [],
                'work_arrangements': [],
                'benefits': [],
                'other_requirements': []
            },
            'weighted': {
                'certifications': [],
                'education': [],
                'technical_skills': [],
                'soft_skills': [],
                'experience': [],
                'support_levels': [],
                'work_arrangements': [],
                'benefits': [],
                'other_requirements': []
            }
        }
        
        # Helper to process a category
        def process_category(category_name: str, patterns_dict: dict):
            for name, pattern in patterns_dict.items():
                matches = list(re.finditer(pattern, job_text, re.IGNORECASE))
                for match in matches:
                    # Apply term gating
                    if not self._passes_term_gate(
                        name,
                        match.group(0),
                        job_text,
                        category_name,
                        match.start(),
                        match.end(),
                    ):
                        continue
                    
                    # Get context and weight
                    label, weight = self._context_label_and_weight(match.start(), match.end(), job_text)
                    
                    # For certifications, track family bucket and optionally specific Microsoft codes
                    if category_name == 'certifications':
                        # Add family bucket always
                        family = name
                        if family not in results['presence'][category_name]:
                            results['presence'][category_name].append(family)
                        results['weighted'][category_name].append({
                            'term': family,
                            'weight': weight,
                            'label': label,
                            'score': 1.0 * weight,
                        })

                        # For Microsoft cert codes only, add specific code with friendly name
                        matched_text = match.group(0).upper().strip()
                        # Check if this is a Microsoft cert code (AZ-xxx, MS-xxx, etc.)
                        if re.match(r'^(AZ|MS|MD|SC|PL|DP|MB|AI|AD|WS)-\d{3}$', matched_text):
                            friendly = self.microsoft_cert_code_map.get(matched_text)
                            if friendly:
                                specific = f"{matched_text} ({friendly})"
                            else:
                                specific = matched_text

                            if specific and specific not in results['presence'][category_name]:
                                results['presence'][category_name].append(specific)
                            results['weighted'][category_name].append({
                                'term': specific,
                                'weight': weight,
                                'label': label,
                                'score': 1.0 * weight,
                            })
                        continue
                    
                    # For non-certifications, use the pattern name as display name
                    display_name = name
                    
                    # Add to presence (simple list)
                    if display_name not in results['presence'][category_name]:
                        results['presence'][category_name].append(display_name)
                    
                    # Add to weighted (with score)
                    results['weighted'][category_name].append({
                        'term': display_name,
                        'weight': weight,
                        'label': label,
                        'score': 1.0 * weight  # Base score of 1.0, multiplied by weight
                    })
        
        # Process all categories
        process_category('certifications', self.certification_patterns)
        process_category('education', self.education_patterns)
        process_category('technical_skills', self.technical_skills)
        process_category('soft_skills', self.soft_skills)
        process_category('experience', self.experience_patterns)
        process_category('support_levels', self.support_levels)
        process_category('work_arrangements', self.work_arrangements)
        process_category('benefits', self.benefits)
        process_category('other_requirements', self.other_requirements)
        
        return results

    def analyze_all_jobs(self, jobs: list, *, dedupe: bool = True) -> dict:
        """Analyze all jobs and aggregate results with presence counts and weighted scores.
        
        Args:
            jobs: List of job dicts with 'id', 'title', 'company', 'description'.
            dedupe: If True, deduplicate jobs by (title, company) before analysis.
        """
        # Deduplicate by strongest available key - keeps first occurrence
        if dedupe:
            seen: set[tuple] = set()
            unique_jobs = []
            for job in jobs:
                src = norm(job.get("source") or "")
                sid = norm(job.get("source_id") or "")
                url = canonicalize_url(job.get("url") or "")

                if src and sid:
                    key = ("src_id", src, sid)
                elif url:
                    key = ("url", norm(url))
                else:
                    desc = job.get("description") or ""
                    if desc:
                        fp = hashlib.sha1(norm(desc)[:3000].encode("utf-8")).hexdigest()
                        key = ("desc_fp", fp)
                    else:
                        key = (
                            "title_company",
                            norm(job.get("title") or ""),
                            norm(job.get("company") or ""),
                        )

                if key not in seen:
                    seen.add(key)
                    unique_jobs.append(job)
            jobs = unique_jobs
        
        # Initialize counters for presence (simple counts)
        presence_results = {
            'certifications': Counter(),
            'education': Counter(),
            'technical_skills': Counter(),
            'soft_skills': Counter(),
            'experience': Counter(),
            'support_levels': Counter(),
            'work_arrangements': Counter(),
            'benefits': Counter(),
            'other_requirements': Counter()
        }
        
        # Initialize for weighted scores (sum of individual term scores)
        weighted_results = {
            'certifications': Counter(),
            'education': Counter(),
            'technical_skills': Counter(),
            'soft_skills': Counter(),
            'experience': Counter(),
            'support_levels': Counter(),
            'work_arrangements': Counter(),
            'benefits': Counter(),
            'other_requirements': Counter()
        }
        
        job_details = []
        # Inverted index for fast drill-down: category -> term -> [job_id]
        term_index: dict[str, dict[str, list[int]]] = {
            'certifications': {},
            'education': {},
            'technical_skills': {},
            'soft_skills': {},
            'experience': {},
            'support_levels': {},
            'work_arrangements': {},
            'benefits': {},
            'other_requirements': {},
        }
        
        for job in jobs:
            job_analysis = self.analyze_job(job['description'])
            job_details.append({
                'id': job['id'],
                'title': job['title'],
                'company': job['company'],
                'requirements': job_analysis
            })

            # Build inverted index from presence data
            for category, items in job_analysis['presence'].items():
                for item in items:
                    bucket = term_index.setdefault(category, {}).setdefault(item, [])
                    bucket.append(job['id'])
            
            # Aggregate presence counts
            for category, items in job_analysis['presence'].items():
                for item in items:
                    presence_results[category][item] += 1
            
            # Aggregate weighted scores
            for category, weighted_items in job_analysis['weighted'].items():
                for item_data in weighted_items:
                    term = item_data['term']
                    score = item_data['score']
                    weighted_results[category][term] += score
        
        return {
            'presence': {k: dict(v.most_common()) for k, v in presence_results.items()},
            'weighted': {k: dict(v.most_common()) for k, v in weighted_results.items()},
            'job_details': job_details,
            'term_index': term_index,
            'total_jobs': len(jobs)
        }

    def generate_report(
        self,
        analysis: dict,
        output_dir: str = None,
        *,
        search_metadata: dict | None = None,
    ) -> str:
        """Generate a comprehensive requirements report.
        
        Args:
            analysis: Output from analyze_all_jobs().
            output_dir: Directory to save report files (optional).
            search_metadata: Dict with 'keywords', 'location', etc. from extract_jobs_from_markdown().
        """
        total_jobs = analysis['total_jobs']
        presence_summary = analysis['presence']
        weighted_summary = analysis['weighted']
        meta = search_metadata or {}
        
        report_lines = [
            "=" * 70,
            "JOB REQUIREMENTS ANALYSIS REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Jobs Analyzed: {total_jobs}",
            f"Search Keywords: {meta.get('keywords') or 'Not specified'}",
            f"Search Location: {meta.get('location') or 'Not specified'}",
            "=" * 70,
            ""
        ]
        
        # Helper to format section with both presence and weighted metrics
        def format_section(title: str, presence_data: dict, weighted_data: dict, min_count: int = 1):
            lines = [f"\n{'=' * 50}", f"{title}", "=" * 50]
            if not presence_data and not weighted_data:
                lines.append("  No items found")
                return lines
            
            # Combine and sort by weighted score (primary), then presence count (secondary)
            combined_items = {}
            for item in set(presence_data.keys()) | set(weighted_data.keys()):
                combined_items[item] = {
                    'presence': presence_data.get(item, 0),
                    'weighted': weighted_data.get(item, 0)
                }
            
            sorted_items = sorted(combined_items.items(), 
                                key=lambda x: (x[1]['weighted'], x[1]['presence']), 
                                reverse=True)
            
            for item, metrics in sorted_items:
                presence_count = metrics['presence']
                weighted_score = metrics['weighted']
                if presence_count >= min_count:
                    presence_pct = (presence_count / total_jobs) * 100
                    avg_weight = weighted_score / presence_count if presence_count > 0 else 0
                    bar = "█" * int(presence_pct / 5)
                    lines.append(f"  {item:35} {presence_count:3} jobs ({presence_pct:5.1f}%) | Score: {weighted_score:6.1f} (avg: {avg_weight:.2f}) {bar}")
            return lines
        
        # Add each section
        report_lines.extend(format_section("CERTIFICATIONS", 
                                         presence_summary['certifications'], 
                                         weighted_summary['certifications']))
        report_lines.extend(format_section("EDUCATION / QUALIFICATIONS", 
                                         presence_summary['education'], 
                                         weighted_summary['education']))
        report_lines.extend(format_section("TECHNICAL SKILLS (Top 25)", 
                                         dict(Counter(presence_summary['technical_skills']).most_common(25)),
                                         dict(Counter(weighted_summary['technical_skills']).most_common(25))))
        report_lines.extend(format_section("SOFT SKILLS", 
                                         presence_summary['soft_skills'], 
                                         weighted_summary['soft_skills']))
        report_lines.extend(format_section("EXPERIENCE REQUIREMENTS", 
                                         presence_summary['experience'], 
                                         weighted_summary['experience']))
        report_lines.extend(format_section("SUPPORT LEVELS & ITSM", 
                                         presence_summary.get('support_levels', {}), 
                                         weighted_summary.get('support_levels', {})))
        report_lines.extend(format_section("WORK ARRANGEMENTS", 
                                         presence_summary.get('work_arrangements', {}), 
                                         weighted_summary.get('work_arrangements', {})))
        report_lines.extend(format_section("BENEFITS & PERKS", 
                                         presence_summary.get('benefits', {}), 
                                         weighted_summary.get('benefits', {})))
        report_lines.extend(format_section("OTHER REQUIREMENTS", 
                                         presence_summary['other_requirements'], 
                                         weighted_summary['other_requirements']))
        
        # Key insights
        report_lines.extend([
            "",
            "=" * 50,
            "KEY INSIGHTS",
            "=" * 50,
        ])
        
        # Most requested items (Presence-based)
        all_tech = presence_summary.get('technical_skills', {})
        if all_tech:
            top_3_tech = Counter(all_tech).most_common(3)
            report_lines.append(f"\n  Top 3 Technical Skills (presence):")
            for skill, count in top_3_tech:
                report_lines.append(f"    - {skill}: {count} jobs ({(count/total_jobs)*100:.1f}%)")

        all_certs = presence_summary.get('certifications', {})
        if all_certs:
            cert_counts = Counter(all_certs)

            code_re = re.compile(r'^(?:MS|AZ|SC|MD|PL|DP|MB|AI|AD|WS)-\d{3}\b', re.IGNORECASE)
            top_3_codes = [(k, v) for (k, v) in cert_counts.most_common() if code_re.match(k)][:3]
            top_3_families = [(k, v) for (k, v) in cert_counts.most_common() if not code_re.match(k)][:3]

            if top_3_codes:
                report_lines.append(f"\n  Top 3 Certification Codes (presence):")
                for cert, count in top_3_codes:
                    report_lines.append(f"    - {cert}: {count} jobs ({(count/total_jobs)*100:.1f}%)")

            if top_3_families:
                report_lines.append(f"\n  Top 3 Certification Buckets (presence):")
                for cert, count in top_3_families:
                    report_lines.append(f"    - {cert}: {count} jobs ({(count/total_jobs)*100:.1f}%)")
        
        report = "\n".join(report_lines)
        
        # Save report if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            # Save text report
            report_path = os.path.join(output_dir, "requirements_analysis.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Save JSON data
            json_path = os.path.join(output_dir, "requirements_analysis.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2)

            # Save drill-down index (smaller + optimized for UI)
            index = {
                'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_jobs': analysis.get('total_jobs', 0),
                'jobs': {
                    str(j['id']): {
                        'id': j['id'],
                        'title': j.get('title'),
                        'company': j.get('company'),
                        'requirements': j.get('requirements', {}),
                    }
                    for j in analysis.get('job_details', [])
                },
                'term_index': analysis.get('term_index', {}),
            }
            index_path = os.path.join(output_dir, "requirements_index.json")
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)
            
            print(f"\nReports saved to:")
            print(f"  - {report_path}")
            print(f"  - {json_path}")
            print(f"  - {index_path}")
        
        return report


def find_latest_run() -> str:
    """Find the most recent scraper run folder."""
    scraped_data_dir = Path(__file__).parent / "scraped_data"
    if not scraped_data_dir.exists():
        return None

    # Support both legacy run_YYYYMMDD_* folders and newer keyword_location_timestamp folders.
    candidates: list[Path] = [p for p in scraped_data_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


def main():
    """Main entry point."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Analyze job requirements from compiled listings")
    parser.add_argument('--input', '-i', help="Path to compiled_jobs.md or jobs.jsonl")
    parser.add_argument('--output', '-o', help="Output directory for reports")
    args = parser.parse_args()

    # Best-effort: avoid UnicodeEncodeError on Windows consoles (cp1252, etc.)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        # Try to find latest run
        latest_run = find_latest_run()
        if latest_run:
            jsonl = os.path.join(latest_run, "jobs.jsonl")
            md = os.path.join(latest_run, "compiled_jobs.md")
            if os.path.exists(jsonl):
                input_file = jsonl
            else:
                input_file = md
        else:
            input_file = None
    
    if not input_file or not os.path.exists(input_file):
        print("Error: Could not find an input file (compiled_jobs.md or jobs.jsonl)")
        print("Please specify the path with --input or run the scraper first.")
        return
    
    print(f"Analyzing: {input_file}")
    
    # Determine output directory
    output_dir = args.output or os.path.dirname(input_file)
    
    # Run analysis
    analyzer = JobRequirementsAnalyzer()
    jobs, search_metadata = analyzer.extract_jobs(input_file)
    
    print(f"Found {len(jobs)} job listings")
    if search_metadata.get('keywords'):
        print(f"  Keywords: {search_metadata['keywords']}")
    if search_metadata.get('location'):
        print(f"  Location: {search_metadata['location']}")
    
    analysis = analyzer.analyze_all_jobs(jobs, dedupe=True)
    dedupe_count = len(jobs) - analysis['total_jobs']
    if dedupe_count > 0:
        print(f"  Deduplicated: {dedupe_count} duplicates removed")
    
    report = analyzer.generate_report(analysis, output_dir, search_metadata=search_metadata)
    
    try:
        print(report)
    except UnicodeEncodeError:
        # If the console can't render some characters, print a safe version
        safe = str(report).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        print(safe)


if __name__ == "__main__":
    main()
