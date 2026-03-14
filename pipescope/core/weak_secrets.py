from __future__ import annotations

import re
from pathlib import Path
from typing import List

from pipescope.core.models import Finding, Severity
from pipescope.utils.fs import iter_files, safe_relpath

EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
MAX_BYTES = 1_000_000  # 1MB

# File extensions for which single-line comments (lines starting with #) are stripped
# before pattern matching to avoid false positives in documentation/example code.
COMMENT_STRIPPABLE_EXTENSIONS = {".py", ".js", ".ts", ".yml", ".yaml", ".env"}

# Extremely common weak/default secrets
WEAK_VALUES = {
    "secret", "changeme", "change-me", "default", "password", "admin", "test", "1234", "12345", "qwerty"
}

# Target common “secret-ish” keys (expand over time)
KEYWORDS = [
    "secret", "session_secret", "sessionsecret", "cookie_secret", "cookiesecret",
    "jwt_secret", "jwtsecret", "app_secret", "appsecret",
]

# Match patterns like:
# secret: 'secret'
# SECRET="changeme"
# jwtSecret = "1234"
ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    \b(?P<key>""" + "|".join(re.escape(k) for k in KEYWORDS) + r""")\b
    \s*[:=]\s*
    (?P<quote>['"])(?P<value>[^'"\n]{1,64})(?P=quote)
    """
)

def _is_excluded(path: Path) -> bool:
    return any(p in EXCLUDE_DIRS for p in path.parts)

def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        return ""
    return data.decode("utf-8", errors="replace")

def _strip_comment_lines(text: str, suffix: str) -> str:
    """Remove single-line comment lines to avoid false positives from documentation/examples."""
    if suffix in COMMENT_STRIPPABLE_EXTENSIONS:
        lines = []
        for line in text.splitlines(keepends=True):
            if not line.lstrip().startswith("#"):
                lines.append(line)
        return "".join(lines)
    return text

def scan_for_weak_secrets(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for f in iter_files(root):
        if _is_excluded(f):
            continue
        # scan common code/config
        if f.suffix.lower() not in {".js", ".ts", ".py", ".yml", ".yaml", ".json", ".env"} and f.name != "Dockerfile":
            continue

        try:
            text = _read_text(f)
        except Exception:
            continue
        if not text:
            continue

        text = _strip_comment_lines(text, f.suffix.lower())

        rel = safe_relpath(f, root)

        for m in ASSIGNMENT_RE.finditer(text):
            key = (m.group("key") or "").lower()
            value = (m.group("value") or "").strip().lower()

            if value in WEAK_VALUES:
                # best-effort line number
                line_no = text[: m.start()].count("\n") + 1

                findings.append(
                    Finding(
                        id="PS-REPO-WEAK-001",
                        title="Weak hardcoded secret value detected",
                        severity=Severity.HIGH,
                        description=(
                            "A secret-like configuration key is assigned a weak/default value "
                            f"('{value}'), which is insecure."
                        ),
                        evidence={"file": rel, "line": line_no, "key": key, "value": value},
                        recommendation=(
                            "Replace weak/default secrets with strong random values and load them from a "
                            "secret manager or protected environment variables. Never hardcode secrets in code."
                        ),
                    )
                )

    return findings
