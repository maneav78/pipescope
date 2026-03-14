from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import List

from pipescope.core.models import Finding, Severity
from pipescope.utils.fs import iter_files, safe_relpath


RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "secrets.toml"


def load_rules():
    with open(RULES_PATH, "rb") as f:
        data = tomllib.load(f)
    return data.get("rule", [])

def _parse_severity(raw: str) -> Severity:
    s = (raw or "").strip().lower()
    if s == "critical":
        return Severity.CRITICAL
    if s == "high":
        return Severity.HIGH
    if s == "medium":
        return Severity.MEDIUM
    if s in ("info", "informational"):
        return Severity.INFO
    return Severity.MEDIUM

def scan_with_rules(root: Path) -> List[Finding]:
    rules = load_rules()
    findings: List[Finding] = []

    for f in iter_files(root):
        if f.suffix.lower() not in {".java", ".js", ".ts", ".py", ".yml", ".yaml", ".env"}:
            continue

        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue

        rel = safe_relpath(f, root)

        for r in rules:
            rx = re.compile(r["regex"])
            if rx.search(text):
                findings.append(
                    Finding(
                        id=r["id"],
                        title=r["description"],
                        severity=_parse_severity(r["severity"]),
                        description=f"Matched rule {r['id']} ({r.get('cwe')})",
                        evidence={"file": rel},
                        recommendation="Remove hardcoded secret and rotate affected credentials.",
                        cves=r.get("cves", []),
                    )
                )

    return findings
