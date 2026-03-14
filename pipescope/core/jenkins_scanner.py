from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests
from rich.console import Console
from typing import List, Optional

from pipescope.core.models import Finding, Severity
from pipescope.core.cve_lookup import lookup_product_cves

console = Console()

def get_jenkins_version(url: str) -> Optional[str]:
    """Get Jenkins version from X-Jenkins header."""
    try:
        response = requests.head(url, timeout=5)
        version = response.headers.get("X-Jenkins")
        if version:
            console.print(f"[green]Found Jenkins version: {version}[/green]")
            return version
    except requests.RequestException:
        pass
    console.print("[yellow]Could not determine Jenkins version.[/yellow]")
    return None

def check_jenkins_path(url, path) -> Optional[str]:
    try:
        full_url = urljoin(url, path)
        response = requests.get(full_url, timeout=5)
        if response.status_code == 200:
            console.print(f"[green]Found Jenkins endpoint: {full_url}[/green]")
            return full_url
    except requests.RequestException:
        pass
    return None

def run_jenkins_scan(url: str) -> List[Finding]:
    console.print(f"[bold]Starting Jenkins scan on {url}[/bold]")
    findings: List[Finding] = []

    version = get_jenkins_version(url)
    if version:
        cves = lookup_product_cves("jenkins", version)
        for cve in cves:
            findings.append(
                Finding(
                    id="PIPESCOPE-JENKINS-CVE-001",
                    title=f"Potential Jenkins CVE: {cve['id']}",
                    severity=Severity.HIGH,
                    description=f"A potential vulnerability ({cve['id']}) was found for Jenkins version {version}. Please investigate further.",
                    evidence={"url": cve["url"], "version": version},
                    recommendation=f"Upgrade Jenkins to the latest version and review the CVE details at {cve['url']}",
                    cves=[cve],
                )
            )

    common_paths = [
        "script",
        "cli",
        "login",
        "asynchPeople/",
        "computer/(master)/",
        "jnlpJars/jenkins-cli.jar",
        "userContent/",
        "whoAmI/",
    ]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_path = {executor.submit(check_jenkins_path, url, path): path for path in common_paths}
        
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            found_url = future.result()
            
            if found_url:
                findings.append(
                    Finding(
                        id="PIPESCOPE-JENKINS-001",
                        title=f"Exposed Jenkins Endpoint: {path}",
                        severity=Severity.MEDIUM,
                        description=f"A potentially sensitive Jenkins endpoint was found at {found_url}",
                        evidence={"url": found_url},
                        recommendation="Ensure that only authorized users have access to this endpoint. Review your Jenkins security configuration.",
                    )
                )
            
    return findings
