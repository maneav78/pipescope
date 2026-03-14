from urllib.parse import urljoin
import requests
from rich.console import Console
from typing import List, Optional
import re

from pipescope.core.models import Finding, Severity
from pipescope.core.cve_lookup import lookup_product_cves

console = Console()

def get_gitlab_version(url: str) -> Optional[str]:
    """Get GitLab version from the login page."""
    try:
        response = requests.get(urljoin(url, "users/sign_in"), timeout=5)
        # Look for content="GitLab Community Edition 15.8.1" or similar
        match = re.search(r'content="GitLab (Community|Enterprise) Edition ([0-9]+\.[0-9]+\.[0-9]+)"', response.text)
        if match:
            version = match.group(2)
            console.print(f"[green]Found GitLab version: {version}[/green]")
            return version
    except requests.RequestException:
        pass
    console.print("[yellow]Could not determine GitLab version.[/yellow]")
    return None

def run_gitlab_scan(url: str) -> List[Finding]:
    console.print(f"[bold]Starting GitLab scan on {url}[/bold]")
    findings: List[Finding] = []

    version = get_gitlab_version(url)
    if version:
        cves = lookup_product_cves("gitlab", version)
        for cve in cves:
            findings.append(
                Finding(
                    id="PIPESCOPE-GITLAB-CVE-001",
                    title=f"Potential GitLab CVE: {cve['id']}",
                    severity=Severity.HIGH,
                    description=f"A potential vulnerability ({cve['id']}) was found for GitLab version {version}. Please investigate further.",
                    evidence={"url": cve["url"], "version": version},
                    recommendation=f"Upgrade GitLab to the latest version and review the CVE details at {cve['url']}",
                    cves=[cve],
                )
            )

    # Add checks for weak configurations here in the future
    # For example, check for public projects: url/explore/projects
            
    return findings
