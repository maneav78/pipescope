from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import List

from pipescope.core.models import Finding, Severity


def is_gitleaks_available() -> bool:
    return shutil.which("gitleaks") is not None


def run_gitleaks(root: Path) -> List[Finding]:
    if not is_gitleaks_available():
        return []

    cmd = [
        "gitleaks",
        "detect",
        "--source", str(root),
        "--report-format", "json",
        "--no-git",
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if proc.returncode not in (0, 1):
        # 1 = findings found (normal for gitleaks)
        return []

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    findings: List[Finding] = []

    for item in report:
        rule = item.get("RuleID", "GITLEAKS")
        desc = item.get("Description", "Secret detected by gitleaks")
        file = item.get("File", "")
        line = item.get("StartLine", None)

        sev = Severity.HIGH
        if "private" in desc.lower() or "key" in desc.lower():
            sev = Severity.CRITICAL

        findings.append(
            Finding(
                id=f"PS-REF-GITLEAKS-{rule}",
                title="Secret detected (Gitleaks reference)",
                severity=sev,
                description=desc,
                evidence={"file": file, "line": line},
                recommendation="Rotate the secret immediately and remove it from source code.",
            )
        )

    return findings
