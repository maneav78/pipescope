from __future__ import annotations

from pathlib import Path
from typing import List, Set

from pipescope.core.models import Finding, Severity
from pipescope.utils.fs import iter_files, safe_relpath


DOCKERFILE_NAMES = {"Dockerfile"}
DOCKERFILE_PREFIXES = ("Dockerfile.",)

COMMON_IGNORE_PATTERNS = {
    # VCS / build
    ".git",
    ".git/",
    "**/.git",
    "**/.git/",
    "node_modules",
    "node_modules/",
    "dist",
    "dist/",
    "build",
    "build/",
    "__pycache__",
    ".venv",
    "venv",
    # common secrets
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_rsa.pub",
    ".aws",
    ".aws/",
    ".ssh",
    ".ssh/",
    "*secrets*",
}


def _is_dockerfile(p: Path) -> bool:
    if p.name in DOCKERFILE_NAMES:
        return True
    return any(p.name.startswith(pref) for pref in DOCKERFILE_PREFIXES)


def _dockerfile_copies_repo(text: str) -> bool:
    """
    Heuristic: COPY/ADD of '.' into image (common risky pattern)
    """
    upper = text.upper()
    for line in upper.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("COPY ") or s.startswith("ADD "):
            # crude detection that catches: COPY . . , COPY . /app , ADD . /src
            if "COPY ." in s or "ADD ." in s:
                return True
    return False


def _read_lines(p: Path) -> List[str]:
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def scan_dockerignore(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    dockerfiles = [p for p in iter_files(root) if _is_dockerfile(p)]
    if not dockerfiles:
        return findings

    # Only care if at least one Dockerfile copies repo context
    copies_repo = False
    for df in dockerfiles:
        try:
            text = df.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if _dockerfile_copies_repo(text):
            copies_repo = True
            break

    if not copies_repo:
        return findings

    dockerignore = root / ".dockerignore"
    if not dockerignore.exists():
        findings.append(
            Finding(
                id="PS-DOCKERIGNORE-001",
                title="Missing .dockerignore while copying build context",
                severity=Severity.MEDIUM,
                description=(
                    "A Dockerfile appears to copy the repository context (e.g., COPY . ...), "
                    "but no .dockerignore file was found. This can bake secrets and unnecessary "
                    "files into container images."
                ),
                evidence={"file": "Dockerfile(s)", "dockerignore": "missing"},
                recommendation=(
                    "Add a .dockerignore excluding secrets (.env, *.pem, *.key), VCS (.git), "
                    "and build artifacts (node_modules, dist, build)."
                ),
            )
        )
        return findings

    # Evaluate contents
    try:
        lines = _read_lines(dockerignore)
    except Exception:
        return findings

    normalized: Set[str] = set()
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        normalized.add(s)

    # Check for absence of key ignore patterns (not exact match; best-effort)
    missing = []
    # we’ll check a small, meaningful subset to avoid nitpicking
    must_haves = {".git", ".env", "*.pem", "*.key", "node_modules", "dist", "build"}
    for m in must_haves:
        if not any(m == x or x.startswith(m) or m in x for x in normalized):
            missing.append(m)

    if missing:
        findings.append(
            Finding(
                id="PS-DOCKERIGNORE-002",
                title=".dockerignore may be incomplete",
                severity=Severity.INFO,
                description="The .dockerignore file exists but may be missing common exclusions.",
                evidence={"file": ".dockerignore", "missing_examples": missing[:12]},
                recommendation=(
                    "Update .dockerignore to exclude secrets (.env, *.pem, *.key), VCS (.git), "
                    "and heavy build artifacts (node_modules, dist, build) to reduce leakage and image size."
                ),
            )
        )

    return findings
