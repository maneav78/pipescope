from __future__ import annotations

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from pipescope.core.models import Finding, Severity


def _resolve_kubescape_command(scan_root: Path) -> Tuple[Optional[List[str]], Optional[Path]]:
    configured_bin = os.environ.get("PIPESCOPE_KUBESCAPE_BIN")
    if configured_bin:
        configured_path = Path(configured_bin).expanduser()
        if configured_path.is_file() and os.access(configured_path, os.X_OK):
            return [str(configured_path)], None
        print(
            "Error running Kubescape: PIPESCOPE_KUBESCAPE_BIN is set but does not point to an executable file"
        )

    kubescape_bin = shutil.which("kubescape")
    if kubescape_bin:
        return [kubescape_bin], None

    project_root = Path(__file__).resolve().parents[2]
    candidate_repos = [
        scan_root / "kubescape",
        Path.cwd() / "kubescape",
        project_root / "kubescape",
    ]

    for repo_dir in candidate_repos:
        if (repo_dir / "go.mod").exists() and (repo_dir / "main.go").exists():
            if shutil.which("go"):
                return ["go", "run", "."], repo_dir
            print(
                "Error running Kubescape: found cloned kubescape repo but Go is not installed or not in PATH"
            )
            return None, None

    print(
        "Error running Kubescape: kubescape executable not found. "
        "Install kubescape, set PIPESCOPE_KUBESCAPE_BIN, or place a cloned kubescape repo in the project root."
    )
    return None, None


def _run_kubescape(path: Path) -> dict:
    command, command_cwd = _resolve_kubescape_command(path)
    if not command:
        return {}

    try:
        full_command = [*command, "scan", str(path), "--format", "json"]
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=False,
            cwd=command_cwd,
        )
        if result.returncode != 0:
            # Kubescape returns a non-zero exit code when it finds issues.
            # We need to check for actual errors.
            if "error" in result.stderr.lower():
                print(f"Error running Kubescape: {result.stderr}")
                return {}
        return json.loads(result.stdout)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error running Kubescape: {e}")
        return {}


def _map_severity(severity: str) -> Severity:
    severity_lower = str(severity).lower()
    if severity_lower == "critical":
        return Severity.CRITICAL
    if severity_lower == "high":
        return Severity.HIGH
    if severity_lower == "medium":
        return Severity.MEDIUM
    if severity_lower in {"low", "info", "informational"}:
        return Severity.INFO

    try:
        score = float(severity)
    except (TypeError, ValueError):
        return Severity.INFO

    if score >= 9.0:
        return Severity.CRITICAL
    if score >= 7.0:
        return Severity.HIGH
    if score >= 4.0:
        return Severity.MEDIUM
    return Severity.INFO


def _is_failed_status(status: object) -> bool:
    if isinstance(status, str):
        return status.lower() == "failed"
    if isinstance(status, dict):
        return str(status.get("status", "")).lower() == "failed"
    return False


def scan_kubernetes_manifests(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    kubescape_output = _run_kubescape(root)

    if not kubescape_output:
        return findings

    for result in kubescape_output.get("results", []):
        resource_id = result.get("source") or result.get("resourceID")
        for control in result.get("controls", []):
            if _is_failed_status(control.get("status")):
                findings.append(
                    Finding(
                        id=control.get("controlID"),
                        title=control.get("name"),
                        severity=_map_severity(control.get("severity") or control.get("baseScore")),
                        description=control.get("description"),
                        evidence={
                            "file": resource_id,
                            "remediation": control.get("remediation"),
                        },
                        recommendation=control.get("remediation"),
                    )
                )
    return findings
