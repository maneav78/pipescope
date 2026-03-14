from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from pipescope.core.cicd_detector import run_cicd_enumeration
from pipescope.core.gitleaks_adapter import run_gitleaks
from pipescope.core.rule_engine import scan_with_rules
from pipescope.core.models import ScanResult, Finding, Severity
from pipescope.core.dockerfile_scanner import scan_dockerfiles
from pipescope.core.dockerignore_scanner import scan_dockerignore
from pipescope.core.compose_scanner import scan_compose
from pipescope.core.k8s_scanner import scan_kubernetes_manifests
from pipescope.core.web_recon import run_web_recon
from pipescope.core.jenkins_scanner import run_jenkins_scan
from pipescope.core.gitlab_scanner import run_gitlab_scan


def run_scan(
    root: Optional[Path],
    version: str,
    web_url: Optional[str] = None,
    jenkins_url: Optional[str] = None,
    gitlab_url: Optional[str] = None,
    wordlist_path: Optional[str] = None,
    wordlist_name: str = "common",
    threads: int = 10,
) -> ScanResult:
    if root is not None:
        res = run_cicd_enumeration(root, version=version)

        # Primary detection
        res.findings.extend(scan_with_rules(root))

        # Reference detection (optional)
        res.findings.extend(run_gitleaks(root))
        res.findings.extend(scan_dockerfiles(root))
        res.findings.extend(scan_dockerignore(root))
        res.findings.extend(scan_compose(root))
        res.findings.extend(scan_kubernetes_manifests(root))
    else:
        res = ScanResult(tool="PipeScope", version=version, target="(no local target)")
        res.metadata["mode"] = "remote-only"

    if web_url:
        found_paths = run_web_recon(
            web_url,
            wordlist_path=wordlist_path,
            wordlist_name=wordlist_name,
            threads=threads
        )
        for path in found_paths:
            res.findings.append(
                Finding(
                    id="PIPESCOPE-WEB-001",
                    title="Exposed File or Directory",
                    severity=Severity.MEDIUM,
                    description=f"An exposed file or directory was found at the path: {path}",
                    evidence={"url": urljoin(web_url, path)},
                    recommendation="Ensure that sensitive files and directories are not publicly accessible. Review your web server's configuration.",
                )
            )

    if jenkins_url:
        res.findings.extend(run_jenkins_scan(jenkins_url))

    if gitlab_url:
        res.findings.extend(run_gitlab_scan(gitlab_url))

    return res
