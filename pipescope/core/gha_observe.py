from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


_PINNED_SHA_RE = re.compile(r"@([0-9a-fA-F]{40})\b")
_USES_RE = re.compile(r"^\s*uses:\s*(.+?)\s*$", re.IGNORECASE)


def _load_yaml(path: Path) -> Dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        doc = yaml.safe_load(raw)
        return doc if isinstance(doc, dict) else None
    except Exception:
        return None


def extract_gha_observations(workflow_path: Path) -> Dict[str, Any]:
    """
    Extracts a small, stable set of observations from a GitHub Actions workflow
    so that rule packs can be evaluated without hardcoding each check in Python.
    """
    doc = _load_yaml(workflow_path) or {}

    # triggers normalization (on:)
    triggers: List[str] = []
    on_block = doc.get("on") or doc.get(True)  # best-effort for YAML oddities
    if isinstance(on_block, str):
        triggers = [on_block]
    elif isinstance(on_block, list):
        triggers = [str(x) for x in on_block]
    elif isinstance(on_block, dict):
        triggers = [str(k) for k in on_block.keys()]

    # permissions raw (string like write-all OR dict OR missing)
    permissions_raw = doc.get("permissions")

    # self-hosted runner signal
    uses_self_hosted_runner = False
    jobs = doc.get("jobs")
    if isinstance(jobs, dict):
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            runs_on = job.get("runs-on")
            vals: List[str] = []
            if isinstance(runs_on, str):
                vals = [runs_on]
            elif isinstance(runs_on, list):
                vals = [str(x) for x in runs_on]
            if any(v.strip().lower() == "self-hosted" for v in vals):
                uses_self_hosted_runner = True
                break

    # raw scan for uses + curl|bash
    try:
        raw = workflow_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    uses_unpinned: List[bool] = []
    has_curl_pipe_shell = False

    for line in raw.splitlines():
        m = _USES_RE.match(line)
        if m:
            uses_val = m.group(1).strip()
            if uses_val.startswith("./"):
                continue  # local action
            if "@" in uses_val and not _PINNED_SHA_RE.search(uses_val):
                uses_unpinned.append(True)

        if re.search(r"(?i)\b(curl|wget)\b.*\|\s*(bash|sh)\b", line):
            has_curl_pipe_shell = True

    return {
        "triggers": triggers,
        "permissions_raw": permissions_raw,
        "uses_unpinned": uses_unpinned,
        "has_curl_pipe_shell": str(has_curl_pipe_shell).lower(),
        "uses_self_hosted_runner": str(uses_self_hosted_runner).lower(),
    }
