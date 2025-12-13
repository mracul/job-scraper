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
from datetime import datetime


class JobRequirementsAnalyzer:
    """Analyzes job listings to extract commonly requested requirements."""
    
    def __init__(self):
        # Certification patterns - specific named certifications
        self.certification_patterns = {
            # Microsoft Certifications
            'Microsoft Certified': r'\b(Microsoft\s+Certified|MCP|MCSE|MCSA|MCSD)\b',
            'Azure Certification': r'\b(Azure\s+(Certified|Administrator|Developer|Architect)|AZ-\d+)\b',
            'Microsoft 365 Certified': r'\b(Microsoft\s+365\s+Certified|MS-\d+)\b',
            
            # CompTIA Certifications
            'CompTIA A+': r'\bCompTIA\s*A\+|\bA\+\s*[Cc]ertif',
            'CompTIA Network+': r'\bCompTIA\s*Network\+|\bNetwork\+',
            'CompTIA Security+': r'\bCompTIA\s*Security\+|\bSecurity\+',
            'CompTIA Server+': r'\bCompTIA\s*Server\+|\bServer\+',
            
            # ITIL
            'ITIL': r'\bITIL\b',
            
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
            'Windows 10/11': r'\bWindows\s*(10|11|10\/11|Desktop)\b',
            'Windows Server': r'\bWindows\s*Server\s*(\d{4})?\b',
            'macOS': r'\b(macOS|Mac\s*OS|Apple\s*(Mac|Desktop))\b',
            'Linux': r'\b(Linux|Ubuntu)\b',
            
            # Microsoft Stack
            'Microsoft 365': r'\b(Microsoft\s*365|M365|MS\s*365|Office\s*365|O365)\b',
            'Active Directory': r'\bActive\s*Directory\b',
            'Azure AD/Entra': r'\b(Azure\s*AD|Entra\s*ID|Azure\s*Active\s*Directory|EntraID)\b',
            'Exchange': r'\bExchange\s*(Online|Server)?\b',
            'SharePoint': r'\bSharePoint\b',
            'Teams': r'\b(Microsoft\s+)?Teams\b',
            'Intune': r'\b(Microsoft\s*)?Intune\b',
            'SCCM/Endpoint Manager': r'\b(SCCM|System\s*Center|Endpoint\s*Manager|ConfigMgr)\b',
            'PowerShell': r'\bPowerShell\b',
            'Group Policy': r'\b(Group\s*Policy|GPO)\b',
            'Azure': r'\bAzure\b(?!\s*(AD|Active\s*Directory))',
            
            # Networking
            'TCP/IP': r'\bTCP\/IP\b',
            'DNS': r'\bDNS\b',
            'DHCP': r'\bDHCP\b',
            'VPN': r'\bVPN\b',
            'Firewall': r'\b[Ff]irewall\b',
            'LAN/WAN': r'\b(LAN|WAN|LAN\/WAN)\b',
            'Networking': r'\b[Nn]etwork(ing)?\s*(fundamentals|knowledge|experience)?\b',
            'VoIP/IP Telephony': r'\b(IP\s*[Tt]elephon|VOIP|VoIP|IP\s*[Pp]hone)\b',
            
            # Virtualization & Cloud
            'VMware': r'\bVMware\b',
            'Hyper-V': r'\bHyper-?V\b',
            'Citrix': r'\bCitrix\b',
            'Cloud Services': r'\b[Cc]loud[\s-]*(based|services?|computing)?\b',
            
            # Remote & AV Support
            'Remote Support Tools': r'\b(TeamViewer|RDP|Remote\s*Desktop|AnyDesk)\b',
            'Video Conferencing': r'\b(Video\s*[Cc]onferenc|Zoom|WebEx|Polycom|Surface\s*Hub)\b',
            'AV Support': r'\b(AV\s*support|[Aa]udio[\s-]*[Vv]isual)\b',
            
            # Ticketing/ITSM
            'ServiceNow': r'\bServiceNow\b',
            'Zendesk': r'\bZendesk\b',
            'Freshdesk': r'\bFresh[Dd]esk\b',
            'JIRA': r'\bJIRA\b',
            'Ticketing System': r'\b[Tt]icketing\s*[Ss]ystem\b',
            'ITSM Tools': r'\b(ITSM|ManageEngine|FreshService)\b',
            
            # Mobile Device Management
            'MDM': r'\bMDM\b|Mobile\s*Device\s*Management',
            'JAMF': r'\bJAMF\b',
            
            # Hardware & Deployment
            'Hardware Troubleshooting': r'\b[Hh]ardware\s*(troubleshoot|support|repair)',
            'Printers': r'\b[Pp]rinter\s*(support|troubleshoot|management)?',
            'System Imaging': r'\b[Ii]maging\b',
            'Software Deployment': r'\b(software\s*)?[Dd]eployment\b',
            'Patching': r'\b[Pp]atch(ing|es)?\b',
            
            # Database & Scripting
            'SQL/Database': r'\b(SQL|MSSQL|[Dd]atabase)\b',
            'Scripting': r'\b[Ss]cripting\b',
            'Programming': r'\b(Python|PowerShell|Go|React|JavaScript|programming)\b',
            
            # Security
            'Security': r'\b[Ss]ecurity\b',
            'Mimecast': r'\bMimecast\b',
            'Backup': r'\b[Bb]ackup\b',
            
            # Vendor Specific
            'Cisco': r'\bCisco\b',
            'Fortinet': r'\bFortinet\b',
            'Meraki': r'\bMeraki\b',
            'UniFi': r'\bUniFi\b',
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
            'Training/Certification': r'\b([Tt]raining|[Cc]ertification)\s*([Oo]pportunit|[Ss]upport|[Pp]rovided)?\b',
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

    def extract_jobs_from_markdown(self, filepath: str) -> list:
        """Extract individual job descriptions from compiled markdown file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by job headers
        job_sections = re.split(r'---\s*\n\s*## Job #\d+:', content)
        
        jobs = []
        for i, section in enumerate(job_sections[1:], 1):  # Skip header
            # Extract title from first line
            lines = section.strip().split('\n')
            title = lines[0].strip() if lines else f"Job {i}"
            
            # Extract company from table
            company_match = re.search(r'\*\*Company\*\*\s*\|\s*([^\|]+)', section)
            company = company_match.group(1).strip() if company_match else "Unknown"
            
            jobs.append({
                'id': i,
                'title': title,
                'company': company,
                'description': section
            })
        
        return jobs

    def analyze_job(self, job_text: str) -> dict:
        """Analyze a single job description for all requirement types."""
        results = {
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
        
        # Check certifications
        for name, pattern in self.certification_patterns.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['certifications'].append(name)
        
        # Check education
        for name, pattern in self.education_patterns.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['education'].append(name)
        
        # Check technical skills
        for name, pattern in self.technical_skills.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['technical_skills'].append(name)
        
        # Check soft skills
        for name, pattern in self.soft_skills.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['soft_skills'].append(name)
        
        # Check experience
        for name, pattern in self.experience_patterns.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['experience'].append(name)
        
        # Check support levels
        for name, pattern in self.support_levels.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['support_levels'].append(name)
        
        # Check work arrangements
        for name, pattern in self.work_arrangements.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['work_arrangements'].append(name)
        
        # Check benefits
        for name, pattern in self.benefits.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['benefits'].append(name)
        
        # Check other requirements
        for name, pattern in self.other_requirements.items():
            if re.search(pattern, job_text, re.IGNORECASE):
                results['other_requirements'].append(name)
        
        return results

    def analyze_all_jobs(self, jobs: list) -> dict:
        """Analyze all jobs and aggregate results."""
        all_results = {
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

            # Build inverted index
            for category, items in job_analysis.items():
                for item in items:
                    bucket = term_index.setdefault(category, {}).setdefault(item, [])
                    bucket.append(job['id'])
            
            # Aggregate counts
            for category, items in job_analysis.items():
                for item in items:
                    all_results[category][item] += 1
        
        return {
            'summary': {k: dict(v.most_common()) for k, v in all_results.items()},
            'job_details': job_details,
            'term_index': term_index,
            'total_jobs': len(jobs)
        }

    def generate_report(self, analysis: dict, output_dir: str = None) -> str:
        """Generate a comprehensive requirements report."""
        total_jobs = analysis['total_jobs']
        summary = analysis['summary']
        
        report_lines = [
            "=" * 70,
            "JOB REQUIREMENTS ANALYSIS REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Jobs Analyzed: {total_jobs}",
            "=" * 70,
            ""
        ]
        
        # Helper to format section
        def format_section(title: str, data: dict, min_count: int = 1):
            lines = [f"\n{'=' * 50}", f"{title}", "=" * 50]
            if not data:
                lines.append("  No items found")
                return lines
            
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
            for item, count in sorted_items:
                if count >= min_count:
                    percentage = (count / total_jobs) * 100
                    bar = "█" * int(percentage / 5)
                    lines.append(f"  {item:40} {count:3} jobs ({percentage:5.1f}%) {bar}")
            return lines
        
        # Add each section
        report_lines.extend(format_section("CERTIFICATIONS", summary['certifications']))
        report_lines.extend(format_section("EDUCATION / QUALIFICATIONS", summary['education']))
        report_lines.extend(format_section("TECHNICAL SKILLS (Top 25)", 
                                          dict(Counter(summary['technical_skills']).most_common(25))))
        report_lines.extend(format_section("SOFT SKILLS", summary['soft_skills']))
        report_lines.extend(format_section("EXPERIENCE REQUIREMENTS", summary['experience']))
        report_lines.extend(format_section("SUPPORT LEVELS & ITSM", summary.get('support_levels', {})))
        report_lines.extend(format_section("WORK ARRANGEMENTS", summary.get('work_arrangements', {})))
        report_lines.extend(format_section("BENEFITS & PERKS", summary.get('benefits', {})))
        report_lines.extend(format_section("OTHER REQUIREMENTS", summary['other_requirements']))
        
        # Key insights
        report_lines.extend([
            "",
            "=" * 50,
            "KEY INSIGHTS",
            "=" * 50,
        ])
        
        # Most requested items
        all_tech = summary['technical_skills']
        if all_tech:
            top_3_tech = Counter(all_tech).most_common(3)
            report_lines.append(f"\n  Top 3 Technical Skills:")
            for skill, count in top_3_tech:
                report_lines.append(f"    - {skill}: {count} jobs ({(count/total_jobs)*100:.1f}%)")
        
        all_certs = summary['certifications']
        if all_certs:
            top_3_certs = Counter(all_certs).most_common(3)
            report_lines.append(f"\n  Top 3 Certifications:")
            for cert, count in top_3_certs:
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
    
    run_folders = sorted(scraped_data_dir.glob("run_*"), reverse=True)
    if run_folders:
        return str(run_folders[0])
    return None


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze job requirements from compiled listings")
    parser.add_argument('--input', '-i', help="Path to compiled_jobs.md file")
    parser.add_argument('--output', '-o', help="Output directory for reports")
    args = parser.parse_args()
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        # Try to find latest run
        latest_run = find_latest_run()
        if latest_run:
            input_file = os.path.join(latest_run, "compiled_jobs.md")
        else:
            input_file = None
    
    if not input_file or not os.path.exists(input_file):
        print("Error: Could not find compiled_jobs.md")
        print("Please specify the path with --input or run the scraper first")
        return
    
    print(f"Analyzing: {input_file}")
    
    # Determine output directory
    output_dir = args.output or os.path.dirname(input_file)
    
    # Run analysis
    analyzer = JobRequirementsAnalyzer()
    jobs = analyzer.extract_jobs_from_markdown(input_file)
    
    print(f"Found {len(jobs)} job listings")
    
    analysis = analyzer.analyze_all_jobs(jobs)
    report = analyzer.generate_report(analysis, output_dir)
    
    print(report)


if __name__ == "__main__":
    main()
