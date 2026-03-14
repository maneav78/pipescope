from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, List

from pipescope.core.models import Finding, Severity


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


def load_rules(path: Path) -> List[dict]:
    """
    Loads TOML rule packs using [[rule]] blocks.
    Returns a list of rule dicts.
    """
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    return doc.get("rule", [])


def _equals_ci(a: Any, b: Any) -> bool:
    if isinstance(a, bool):
        a = "true" if a else "false"
    if isinstance(b, bool):
        b = "true" if b else "false"
    return str(a).strip().lower() == str(b).strip().lower()


def eval_rules(observations: Dict[str, Any], rules: List[dict], evidence_file: str) -> List[Finding]:
    """
    Applies rules to an observations dict and returns Finding objects.
    Supported ops:
      - contains: obs[field] contains value (list membership or substring)
      - equals_ci: case-insensitive equality
      - regex: obs[field] matches regex (string or any item in list)
      - any_true: obs[field] is truthy or any truthy item in list
    """
    import re

    findings: List[Finding] = []

    for r in rules:
        field = r.get("field")
        op = r.get("op")
        value = r.get("value")

        obs_val = observations.get(field)

        hit = False

        if op == "contains":
            if isinstance(obs_val, list):
                hit = value in obs_val
            elif isinstance(obs_val, str):
                hit = str(value) in obs_val

        elif op == "equals_ci":
            hit = _equals_ci(obs_val, value)

        elif op == "regex":
            pattern = re.compile(str(value))
            if isinstance(obs_val, str):
                hit = bool(pattern.search(obs_val))
            elif isinstance(obs_val, list):
                hit = any(bool(pattern.search(str(x))) for x in obs_val)

        elif op == "any_true":
            if isinstance(obs_val, list):
                hit = any(bool(x) for x in obs_val)
            else:
                hit = bool(obs_val)

        if hit:
            findings.append(
                Finding(
                    id=r["id"],
                    title=r.get("title", "CI/CD rule matched"),
                    severity=_parse_severity(r.get("severity", "medium")),
                    description="Matched rule from PipeScope rule pack.",
                    evidence={"file": evidence_file, "field": field, "op": op, "value": value},
                    recommendation=r.get("recommendation", "Review and remediate."),
                )
            )

    return findings
