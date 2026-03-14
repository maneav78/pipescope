from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

from pipescope.core.models import Finding, Severity
from pipescope.utils.fs import iter_files, safe_relpath


EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", ".tox", ".mypy_cache", "__pycache__"
}

MAX_FILE_BYTES = 2_000_000


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    return any(p in parts for p in EXCLUDE_DIRS)


def _should_scan_file(path: Path) -> bool:
    if _is_excluded(path):
        return False
    # detect-secrets is language agnostic; we can scan most text-like files.
    # But keep it lightweight: skip huge files and obvious binaries.
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def scan_for_secrets_detect_secrets(root: Path) -> List[Finding]:
    """
    Uses Yelp/detect-secrets engine and converts results into PipeScope Finding objects.
    """
    secrets = SecretsCollection()

    # Uses detect-secrets default plugins/settings (AWSKeyDetector, PrivateKeyDetector, GitHubTokenDetector, etc.)
    # See detect-secrets docs for plugin list and customization. :contentReference[oaicite:2]{index=2}
    with default_settings():
        for f in iter_files(root):
            if not _should_scan_file(f):
                continue
            try:
                secrets.scan_file(str(f))
            except Exception:
                # Don't fail the entire scan because one file can't be parsed
                continue

    data: Dict[str, Any] = secrets.json()  # structured results
    # detect-secrets format: {"version": "...", "plugins_used": [...], "results": { "file": [ ... ] } }
    results = data.get("results", {}) or {}

    findings: List[Finding] = []

    for abs_file, items in results.items():
        # abs_file may be absolute depending on how scan_file was called; map it safely
        p = Path(abs_file)
        rel = safe_relpath(p, root) if p.is_absolute() else str(p)

        for it in items:
            # Typical fields include: type, filename, line_number, hashed_secret, is_secret
            plugin = it.get("type", "UnknownDetector")
            line = it.get("line_number")
            hashed = it.get("hashed_secret")

            # Severity strategy (capstone-friendly, adjustable):
            # - Private keys / AWS / GitHub tokens often high/critical, but detect-secrets may already encode type.
            # For MVP: mark HIGH, promote PrivateKey-like detectors to CRITICAL.
            sev = Severity.HIGH
            if "PrivateKey" in plugin:
                sev = Severity.CRITICAL

            findings.append(
                Finding(
                    id="PS-REPO-SEC-DS-001",
                    title="Potential secret detected (detect-secrets)",
                    severity=sev,
                    description="detect-secrets flagged a potential secret in the repository.",
                    evidence={
                        "file": rel,
                        "detector": plugin,
                        "line": line,
                        "hashed_secret": hashed,
                    },
                    recommendation=(
                        "Remove secrets from the repo, rotate/revoke affected credentials, "
                        "and migrate to a secret manager (AWS Secrets Manager/Vault/etc.). "
                        "Add secret scanning in CI and pre-commit to prevent recurrence."
                    ),
                )
            )

    return findings
