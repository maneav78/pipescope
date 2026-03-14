from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


_CURL_PIPE_SHELL_RE = re.compile(r"(?i)\b(curl|wget)\b.*\|\s*(bash|sh)\b")
_ECHO_SECRET_RE = re.compile(r"(?i)\becho\b.*\b(password|passwd|token|secret|api[_-]?key)\b")


def extract_jenkins_observations(jenkinsfile_path: Path) -> Dict[str, Any]:
    try:
        raw = jenkinsfile_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw = ""

    has_curl_pipe_shell = bool(_CURL_PIPE_SHELL_RE.search(raw))
    has_echo_secret_like = bool(_ECHO_SECRET_RE.search(raw))

    return {
        "has_curl_pipe_shell": str(has_curl_pipe_shell).lower(),
        "has_echo_secret_like": str(has_echo_secret_like).lower(),
    }
