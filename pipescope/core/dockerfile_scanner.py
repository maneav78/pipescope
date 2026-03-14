from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pipescope.core.models import Finding, Severity
from pipescope.core.cve_lookup import lookup_image_cves
from pipescope.utils.fs import iter_files, safe_relpath


DOCKERFILE_NAMES = {"Dockerfile"}
DOCKERFILE_PREFIXES = ("Dockerfile.",)


SECRET_KEYS_RE = re.compile(r"(?i)\b(password|passwd|token|secret|api[_-]?key|access[_-]?key)\b")


def _is_dockerfile(p: Path) -> bool:
    if p.name in DOCKERFILE_NAMES:
        return True
    return any(p.name.startswith(pref) for pref in DOCKERFILE_PREFIXES)


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def scan_dockerfiles(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    dockerfiles: List[Path] = [p for p in iter_files(root) if _is_dockerfile(p)]
    if not dockerfiles:
        return findings

    for df in dockerfiles:
        rel = safe_relpath(df, root)
        try:
            text = _read_text(df)
        except Exception:
            continue

        lines = text.splitlines()

        # Track state
        has_user = False
        user_root = False
        copy_all = False
        from_latest = False
        unpinned_from = False

        for i, raw in enumerate(lines, start=1):
            line = raw.strip()

            # ignore comments
            if not line or line.startswith("#"):
                continue

            # FROM checks
            if line.upper().startswith("FROM "):
                image = line.split(None, 1)[1].strip()
                # examples: ubuntu:latest, python:3.11, alpine
                if ":latest" in image:
                    from_latest = True
                if ":" not in image:
                    unpinned_from = True  # no tag at all
                # (we can later add digest pinning check: @sha256:...)
                # dynamic CVE lookup for the base image
                cves = lookup_image_cves(image)
                if cves:
                    findings.append(
                        Finding(
                            id="PS-DOCKER-CVE-001",
                            title="Base image may match known CVEs",
                            severity=Severity.HIGH,
                            description=f"Image '{image}' heuristically matched {len(cves)} CVE(s) based on product/version search.",
                            evidence={"file": rel, "line": i, "image": image},
                            recommendation="Validate with an image-level scanner such as Trivy or Grype, then upgrade to a fixed image version or digest.",
                            cves=cves,
                        )
                    )
            # USER checks
            if line.upper().startswith("USER "):
                has_user = True
                user = line.split(None, 1)[1].strip()
                if user == "0" or user.lower() == "root":
                    user_root = True

            # ADD vs COPY
            if line.upper().startswith("ADD "):
                findings.append(
                    Finding(
                        id="PS-DOCKER-001",
                        title="Use of ADD in Dockerfile",
                        severity=Severity.MEDIUM,
                        description="ADD can have surprising behavior (tar auto-extract, remote URL fetch).",
                        evidence={"file": rel, "line": i, "instruction": raw.strip()},
                        recommendation="Prefer COPY for predictable behavior unless ADD is specifically required.",
                    )
                )

            # curl|bash / wget|sh pattern
            if re.search(r"(?i)\b(curl|wget)\b.*\|\s*(sh|bash)\b", line):
                findings.append(
                    Finding(
                        id="PS-DOCKER-002",
                        title="Remote script piped to shell in Dockerfile",
                        severity=Severity.HIGH,
                        description="Piping remote content directly to a shell is a high-risk supply-chain pattern.",
                        evidence={"file": rel, "line": i, "instruction": raw.strip()},
                        recommendation="Download with verification (checksum/signature) or use trusted packages/artifacts.",
                    )
                )

            # ENV/ARG secrets
            if line.upper().startswith(("ENV ", "ARG ")):
                if SECRET_KEYS_RE.search(line):
                    findings.append(
                        Finding(
                            id="PS-DOCKER-003",
                            title="Potential secret in ENV/ARG",
                            severity=Severity.HIGH,
                            description="Secrets in ENV/ARG can leak via image layers, build logs, and history.",
                            evidence={"file": rel, "line": i, "instruction": raw.strip()},
                            recommendation="Use build-time secrets (BuildKit secrets), runtime secret manager, or CI protected variables.",
                        )
                    )

            # COPY . .
            if line.upper().startswith("COPY "):
                if re.search(r"(?i)\bcopy\s+\.\s+\.", line) or re.search(r"(?i)\bcopy\s+\.\s+/", line):
                    copy_all = True

        # Aggregate findings
        if from_latest:
            findings.append(
                Finding(
                    id="PS-DOCKER-004",
                    title="Base image uses :latest tag",
                    severity=Severity.MEDIUM,
                    description="Using :latest reduces reproducibility and increases supply-chain risk.",
                    evidence={"file": rel},
                    recommendation="Pin to a specific version tag or, ideally, a digest (@sha256:...).",
                )
            )

        if unpinned_from:
            findings.append(
                Finding(
                    id="PS-DOCKER-005",
                    title="Base image tag not pinned",
                    severity=Severity.MEDIUM,
                    description="Base images without explicit tags are mutable over time.",
                    evidence={"file": rel},
                    recommendation="Pin base image version tag or digest for reproducible builds.",
                )
            )

        if not has_user or user_root:
            findings.append(
                Finding(
                    id="PS-DOCKER-006",
                    title="Container may run as root",
                    severity=Severity.HIGH,
                    description="Running as root increases blast radius if the container is compromised.",
                    evidence={"file": rel, "user_instruction_present": has_user, "user_is_root": user_root},
                    recommendation="Create and switch to a non-root user (USER appuser) and drop Linux capabilities where possible.",
                )
            )

        # If copying whole repo, check dockerignore existence
        if copy_all:
            dockerignore = root / ".dockerignore"
            if not dockerignore.exists():
                findings.append(
                    Finding(
                        id="PS-DOCKER-007",
                        title="COPY . . without .dockerignore",
                        severity=Severity.MEDIUM,
                        description="Copying the whole repo without .dockerignore can bake secrets and unnecessary files into the image.",
                        evidence={"file": rel},
                        recommendation="Add a .dockerignore excluding secrets (.env, *.pem, *.key), VCS (.git), and build artifacts.",
                    )
                )

    return findings
