from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from pipescope.core.models import Finding, Severity
from pipescope.utils.fs import iter_files, safe_relpath


COMPOSE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}

SECRET_KEYWORDS = ("password", "passwd", "token", "secret", "api_key", "apikey", "access_key", "private_key")


def _load_yaml(path: Path) -> Dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _iter_compose_files(root: Path) -> List[Path]:
    return [p for p in iter_files(root) if p.name in COMPOSE_NAMES]


def _is_plaintext_secret_env(k: str, v: Any) -> bool:
    key = (k or "").lower()
    if not any(s in key for s in SECRET_KEYWORDS):
        return False
    # If value references env expansion (${VAR}) or file, it's less direct. Flag only literals.
    if isinstance(v, str):
        vv = v.strip()
        if vv.startswith("${") and vv.endswith("}"):
            return False
        if vv.startswith("$") and len(vv) > 1:
            return False
        return True
    return True


def scan_compose(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for f in _iter_compose_files(root):
        rel = safe_relpath(f, root)
        doc = _load_yaml(f)
        if not doc:
            continue

        services = doc.get("services")
        if not isinstance(services, dict):
            continue

        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue

            # privileged
            if svc.get("privileged") is True:
                findings.append(
                    Finding(
                        id="PS-COMPOSE-001",
                        title="privileged: true in docker-compose service",
                        severity=Severity.HIGH,
                        description="Privileged containers effectively disable many isolation boundaries.",
                        evidence={"file": rel, "service": svc_name, "key": "privileged"},
                        recommendation="Avoid privileged containers. Use least privilege, minimal capabilities, and read-only FS where possible.",
                    )
                )

            # network_mode: host
            nm = svc.get("network_mode")
            if isinstance(nm, str) and nm.strip().lower() == "host":
                findings.append(
                    Finding(
                        id="PS-COMPOSE-002",
                        title="network_mode: host in docker-compose service",
                        severity=Severity.HIGH,
                        description="Host networking removes network isolation and increases attack surface.",
                        evidence={"file": rel, "service": svc_name, "key": "network_mode", "value": nm},
                        recommendation="Avoid host networking unless strictly required; prefer bridge networks with explicit ports.",
                    )
                )

            # docker socket mount
            vols = svc.get("volumes")
            if isinstance(vols, list):
                for v in vols:
                    if isinstance(v, str) and "/var/run/docker.sock" in v:
                        findings.append(
                            Finding(
                                id="PS-COMPOSE-003",
                                title="Docker socket mounted into container",
                                severity=Severity.CRITICAL,
                                description="Mounting docker.sock allows container to control the Docker daemon (host compromise risk).",
                                evidence={"file": rel, "service": svc_name, "volume": v},
                                recommendation="Do not mount the Docker socket. Use a dedicated build service or narrowly scoped APIs.",
                            )
                        )
                        break

            # cap_add risky
            cap_add = svc.get("cap_add")
            if isinstance(cap_add, list):
                risky_caps = {"SYS_ADMIN", "SYS_PTRACE", "NET_ADMIN"}
                used = {str(c).strip().upper() for c in cap_add}
                hit = sorted(list(used.intersection(risky_caps)))
                if hit:
                    findings.append(
                        Finding(
                            id="PS-COMPOSE-004",
                            title="High-risk Linux capabilities added",
                            severity=Severity.HIGH,
                            description="Adding broad Linux capabilities increases container escape and privilege escalation risk.",
                            evidence={"file": rel, "service": svc_name, "cap_add": hit},
                            recommendation="Remove risky capabilities and redesign to run with minimal privileges.",
                        )
                    )

            # ports exposure (heuristic)
            ports = svc.get("ports")
            if isinstance(ports, list) and ports:
                # If user explicitly binds 0.0.0.0 or publishes ports, warn (Medium)
                exposed = []
                for p in ports:
                    if isinstance(p, str):
                        exposed.append(p)
                if exposed:
                    findings.append(
                        Finding(
                            id="PS-COMPOSE-005",
                            title="Service publishes ports (review exposure)",
                            severity=Severity.MEDIUM,
                            description="Published ports can expose services publicly depending on host firewall/networking.",
                            evidence={"file": rel, "service": svc_name, "ports": exposed[:12]},
                            recommendation="Bind only necessary ports, restrict to localhost where possible, and use a reverse proxy/LB with auth.",
                        )
                    )

            # plaintext secrets in environment
            env = svc.get("environment")
            plaintext_hits = []

            if isinstance(env, dict):
                for k, v in env.items():
                    if _is_plaintext_secret_env(str(k), v):
                        plaintext_hits.append(str(k))
            elif isinstance(env, list):
                # list format: KEY=VALUE
                for item in env:
                    if isinstance(item, str) and "=" in item:
                        k, v = item.split("=", 1)
                        if _is_plaintext_secret_env(k, v):
                            plaintext_hits.append(k)

            if plaintext_hits:
                findings.append(
                    Finding(
                        id="PS-COMPOSE-006",
                        title="Potential plaintext secrets in docker-compose environment",
                        severity=Severity.HIGH,
                        description="Secret-like environment variables appear to be set to literal values in compose.",
                        evidence={"file": rel, "service": svc_name, "keys": plaintext_hits[:20]},
                        recommendation="Use env var injection from a secret manager, Docker/Swarm secrets, or external config files with strict access.",
                    )
                )

    return findings