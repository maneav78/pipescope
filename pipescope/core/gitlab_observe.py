from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key)\b\s*:\s*['\"]?[^'\"\n]{6,}['\"]?"
)
_CURL_PIPE_SHELL_RE = re.compile(r"(?i)\b(curl|wget)\b.*\|\s*(bash|sh)\b")
_PRIVILEGED_RE = re.compile(r"(?i)\bprivileged\s*:\s*true\b")


def extract_gitlab_observations(ci_path: Path) -> Dict[str, Any]:
    try:
        raw = ci_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    has_plaintext_secrets = bool(_SECRET_ASSIGN_RE.search(raw))
    has_curl_pipe_shell = bool(_CURL_PIPE_SHELL_RE.search(raw))
    has_dind_or_privileged = ("docker:dind" in raw.lower()) or bool(_PRIVILEGED_RE.search(raw))

    return {
        "has_plaintext_secrets": str(has_plaintext_secrets).lower(),
        "has_curl_pipe_shell": str(has_curl_pipe_shell).lower(),
        "has_dind_or_privileged": str(has_dind_or_privileged).lower(),
    }
