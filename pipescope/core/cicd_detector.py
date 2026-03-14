

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pipescope.core.models import Finding, ScanResult, Severity
from pipescope.core.weak_secrets import scan_for_weak_secrets
from pipescope.utils.fs import safe_relpath
from pipescope.core.secrets_scanner import scan_for_secrets_detect_secrets

from pipescope.core.rules_eval import load_rules, eval_rules
from pipescope.core.gha_observe import extract_gha_observations
from pipescope.core.gitlab_observe import extract_gitlab_observations
from pipescope.core.jenkins_observe import extract_jenkins_observations


RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
GHA_RULES = RULES_DIR / "cicd_github_actions.toml"
GITLAB_RULES = RULES_DIR / "cicd_gitlab.toml"
JENKINS_RULES = RULES_DIR / "cicd_jenkins.toml"

@dataclass(frozen=True)
class DetectedCICD:
    kind: str  # GitHubActions | GitLabCI | Jenkins
    path: str

def _load_yaml(path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None
    
def detect_cicd_files(root: Path) -> List[DetectedCICD]:
    found: List[DetectedCICD] = []

    gha_dir = root / ".github" / "workflows"
    if gha_dir.is_dir():
        for p in gha_dir.glob("*.y*ml"):
            found.append(DetectedCICD(kind="GitHubActions", path=safe_relpath(p, root)))

    gl = root / ".gitlab-ci.yml"
    if gl.is_file():
        found.append(DetectedCICD(kind="GitLabCI", path=safe_relpath(gl, root)))

    jf = root / "Jenkinsfile"
    if jf.is_file():
        found.append(DetectedCICD(kind="Jenkins", path=safe_relpath(jf, root)))

    return found

def analyze_github_actions(root: Path, workflow_relpath: str) -> List[Finding]:
    p = root / workflow_relpath
    doc = _load_yaml(p)
    if not doc:
        return []

    findings: List[Finding] = [
        Finding(
            id="PS-CICD-GHA-001",
            title="GitHub Actions workflow detected",
            severity=Severity.INFO,
            description="A GitHub Actions workflow file was found.",
            evidence={"file": workflow_relpath},
            recommendation="Pin actions by SHA, set least-privilege permissions, and avoid long-lived secrets.",
        )
    ]

    # Heuristic: unpinned actions (uses: org/action@v1) rather than full SHA
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    unpinned: List[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("uses:"):
            val = s.split("uses:", 1)[1].strip()
            if "@" in val and len(val.split("@", 1)[1]) < 40:
                unpinned.append(val)

    if unpinned:
        findings.append(
            Finding(
                id="PS-CICD-GHA-002",
                title="Unpinned GitHub Actions detected",
                severity=Severity.MEDIUM,
                description="Floating tags/branches can increase supply-chain risk.",
                evidence={"file": workflow_relpath, "uses": unpinned[:20]},
                recommendation="Pin third-party actions to a full commit SHA.",
            )
        )

    permissions = doc.get("permissions")
    if isinstance(permissions, str) and permissions.lower() == "write-all":
        findings.append(
            Finding(
                id="PS-CICD-GHA-003",
                title="Workflow requests write-all permissions",
                severity=Severity.HIGH,
                description="Broad GITHUB_TOKEN permissions increase blast radius.",
                evidence={"file": workflow_relpath, "permissions": permissions},
                recommendation="Set minimal permissions globally and elevate only per job if required.",
            )
        )

    return findings

def analyze_gitlab_ci(root: Path) -> List[Finding]:
    p = root / ".gitlab-ci.yml"
    doc = _load_yaml(p)
    if not doc:
        return []

    findings: List[Finding] = [
        Finding(
            id="PS-CICD-GL-001",
            title="GitLab CI pipeline detected",
            severity=Severity.INFO,
            description="A GitLab CI configuration file was found.",
            evidence={"file": ".gitlab-ci.yml"},
            recommendation="Review protected variables, runner security, and avoid secrets in logs.",
        )
    ]

    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    if "curl" in raw and "| bash" in raw:
        findings.append(
            Finding(
                id="PS-CICD-GL-002",
                title="Potentially unsafe install pattern detected (curl | bash)",
                severity=Severity.MEDIUM,
                description="Piping remote scripts directly to shell can be risky.",
                evidence={"file": ".gitlab-ci.yml"},
                recommendation="Use checksum/signature verification or vetted internal artifacts.",
            )
        )

    return findings

def analyze_jenkinsfile(root: Path) -> List[Finding]:
    p = root / "Jenkinsfile"
    if not p.is_file():
        return []

    findings: List[Finding] = [
        Finding(
            id="PS-CICD-JENK-001",
            title="Jenkins pipeline detected",
            severity=Severity.INFO,
            description="A Jenkinsfile was found.",
            evidence={"file": "Jenkinsfile"},
            recommendation="Harden Jenkins (auth, CSRF, script security) and use credential bindings.",
        )
    ]

    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    suspects = ["password", "passwd", "secret", "token", "apikey", "api_key"]
    if any(s in raw.lower() for s in suspects) and "credentials(" not in raw.lower():
        findings.append(
            Finding(
                id="PS-CICD-JENK-002",
                title="Possible hardcoded secret indicators in Jenkinsfile",
                severity=Severity.MEDIUM,
                description="Credential-like keywords appear outside typical Jenkins credential usage.",
                evidence={"file": "Jenkinsfile"},
                recommendation="Use withCredentials/credentials binding; never embed secrets in pipeline code.",
            )
        )

    return findings

def run_cicd_enumeration(root: Path, version: str = "0.1.0") -> ScanResult:
    result = ScanResult(tool="PipeScope", version=version, target=str(root.resolve()))
    detected = detect_cicd_files(root)
    result.metadata["detected_cicd"] = [d.__dict__ for d in detected]

    for d in detected:
        if d.kind == "GitHubActions":
            # existing hardcoded heuristics (keep for now)
            result.findings.extend(analyze_github_actions(root, d.path))

            # NEW: rule-pack evaluation
            obs = extract_gha_observations(root / d.path)
            result.findings.extend(
                eval_rules(obs, load_rules(GHA_RULES), evidence_file=d.path)
            )

        elif d.kind == "GitLabCI":
            # existing hardcoded heuristics (keep for now)
            result.findings.extend(analyze_gitlab_ci(root))

            # NEW: rule-pack evaluation
            ci_rel = ".gitlab-ci.yml"
            ci_path = root / ci_rel
            obs = extract_gitlab_observations(ci_path)
            result.findings.extend(
                eval_rules(obs, load_rules(GITLAB_RULES), evidence_file=ci_rel)
            )

        elif d.kind == "Jenkins":
            # existing hardcoded heuristics (keep for now)
            result.findings.extend(analyze_jenkinsfile(root))

            # NEW: rule-pack evaluation
            jf_rel = "Jenkinsfile"
            jf_path = root / jf_rel
            obs = extract_jenkins_observations(jf_path)
            result.findings.extend(
                eval_rules(obs, load_rules(JENKINS_RULES), evidence_file=jf_rel)
            )

            
    result.findings.extend(scan_for_secrets_detect_secrets(root))
    result.findings.extend(scan_for_weak_secrets(root))
    return result