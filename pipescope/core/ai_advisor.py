"""
AI-powered advisor that enriches findings with prioritised recommendations.

- If an OpenAI-compatible API key is available (``OPENAI_API_KEY`` env var or
  passed explicitly) the module sends a compact prompt and returns LLM-generated,
  context-aware recommendations.
- When no key is available it falls back to a rich rule-based lookup so the
  feature still delivers real value without external dependencies.
"""
from __future__ import annotations

import os
import json
import textwrap
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Rule-based fallback – always available, no API key required
# ---------------------------------------------------------------------------

_RULE_RECOMMENDATIONS: Dict[str, str] = {
    # Jenkins
    "PIPESCOPE-JENKINS-CVE": (
        "Update Jenkins to the latest LTS release immediately. "
        "Enable the Security Realm, disable anonymous access, and subscribe "
        "to the Jenkins Security Advisory feed. Use `--jenkins.model.Jenkins.disableRememberMe=true` "
        "and restrict agent-to-controller access via the built-in node security configuration."
    ),
    "PIPESCOPE-JENKINS-001": (
        "Restrict Jenkins endpoint access: enable authentication, disable the CLI "
        "over Remoting, configure a reverse proxy to expose only required paths, "
        "and set `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy` headers."
    ),
    # GitLab
    "PIPESCOPE-GITLAB": (
        "Upgrade GitLab to the latest patched version. Enforce 2FA for all users, "
        "use group-level protected branches, rotate runner registration tokens, and "
        "enable audit-log streaming to a SIEM."
    ),
    # Docker / Dockerfile
    "PIPESCOPE-DOCKER": (
        "Pin base images to a digest (e.g., `FROM python:3.12-slim@sha256:...`), "
        "run containers as a non-root user, enable Docker Content Trust, "
        "and integrate a container image scanner (Trivy/Grype) in your pipeline."
    ),
    # Kubernetes / K8s
    "PIPESCOPE-K8S": (
        "Enable Pod Security Admission, set `runAsNonRoot: true` and a read-only "
        "root filesystem in every container's `securityContext`. Use NetworkPolicies "
        "to restrict pod-to-pod traffic and regularly audit RBAC roles with `kubectl auth can-i`."
    ),
    # GitHub Actions
    "PS-CICD-GHA": (
        "Pin all third-party actions to their full commit SHA instead of a tag. "
        "Restrict `permissions` to the minimum required per-job. Enable `CODEOWNERS` "
        "review for `.github/workflows/` and consider OpenID Connect (OIDC) instead "
        "of long-lived secrets for cloud authentication."
    ),
    # GitLab CI
    "PS-CICD-GL": (
        "Store secrets in GitLab CI/CD Variables with `Protected` and `Masked` flags. "
        "Pin runner images, use `needs:` instead of `dependencies:` to restrict artifact "
        "access, and enforce branch-protection rules on the default branch."
    ),
    # Jenkinsfile
    "PS-CICD-JENK": (
        "Use Jenkins Credentials Binding (`withCredentials`) instead of bare environment "
        "variables. Enable the Job DSL and Pipeline Shared Libraries approval process, "
        "and configure the Restrict Matrix Authorization Strategy plugin."
    ),
    # Web / exposed paths
    "PIPESCOPE-WEB": (
        "Remove or restrict access to exposed administrative paths. Apply authentication, "
        "rate-limiting, and a Web Application Firewall (WAF) rule in front of the service. "
        "Audit server response headers for information disclosure."
    ),
    # Secrets
    "PIPESCOPE-SECRET": (
        "Rotate any exposed credentials immediately. Add the affected file patterns to "
        "`.gitleaksignore` or use `git-filter-repo` to purge history. Enforce pre-commit "
        "hooks with `detect-secrets` and set up SAST secret scanning at the CI level."
    ),
    # Compose
    "PIPESCOPE-COMPOSE": (
        "Avoid publishing ports unnecessarily. Use named secrets instead of environment "
        "variable files, and pin service images to immutable digests. Enable "
        "`read_only: true` for stateless services in Docker Compose."
    ),
    # Rule engine
    "PIPESCOPE-RULE": (
        "Review the flagged configuration field against CIS Benchmarks and your "
        "organisation's security baseline. Apply the principle of least privilege and "
        "validate the change in a staging environment before merging."
    ),
}

_DEFAULT_RECOMMENDATION = (
    "Review the flagged issue against CIS Benchmarks and OWASP Top-10 CI/CD Security "
    "Risks. Apply the principle of least privilege, follow secure-by-default "
    "configuration guidance, and validate remediation in a staging environment."
)


def _rule_based_recommendation(finding_id: str, title: str) -> str:
    """Return the best-matching rule-based recommendation for a finding."""
    upper_id = finding_id.upper()
    for prefix, rec in _RULE_RECOMMENDATIONS.items():
        if upper_id.startswith(prefix.upper()):
            return rec
    # Fallback: try matching on title keywords
    title_lower = title.lower()
    if "secret" in title_lower or "credential" in title_lower or "password" in title_lower:
        return _RULE_RECOMMENDATIONS["PIPESCOPE-SECRET"]
    if "docker" in title_lower or "container" in title_lower:
        return _RULE_RECOMMENDATIONS["PIPESCOPE-DOCKER"]
    if "kubernetes" in title_lower or "k8s" in title_lower or "manifest" in title_lower:
        return _RULE_RECOMMENDATIONS["PIPESCOPE-K8S"]
    if "jenkins" in title_lower:
        return _RULE_RECOMMENDATIONS["PIPESCOPE-JENKINS-001"]
    if "gitlab" in title_lower:
        return _RULE_RECOMMENDATIONS["PIPESCOPE-GITLAB"]
    if "github" in title_lower or "action" in title_lower:
        return _RULE_RECOMMENDATIONS["PS-CICD-GHA"]
    return _DEFAULT_RECOMMENDATION


# ---------------------------------------------------------------------------
# OpenAI-enhanced recommendations (optional)
# ---------------------------------------------------------------------------

def _openai_recommendations(
    findings: List[Dict],
    api_key: str,
    model: str = "gpt-4o-mini",
) -> Dict[str, str]:
    """Call OpenAI to get concise, context-aware recommendations per finding."""
    try:
        import openai  # type: ignore
    except ImportError:
        return {}

    client = openai.OpenAI(api_key=api_key)

    compact = [
        {
            "id": f.get("id", ""),
            "title": f.get("title", ""),
            "severity": f.get("severity", ""),
            "description": f.get("description", ""),
        }
        for f in findings[:30]  # cap to keep prompt small
    ]

    prompt = textwrap.dedent(
        f"""
        You are a senior DevSecOps engineer. Below is a JSON list of security findings
        from a CI/CD pipeline scan. For each finding (identified by "id"), return a
        concise actionable remediation recommendation (2-4 sentences). Return **only**
        a JSON object mapping each finding "id" to its recommendation string.

        Findings:
        {json.dumps(compact, indent=2)}
        """
    ).strip()

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_findings(
    findings: List[Dict],
    openai_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> List[Dict]:
    """
    Return a new list of findings with an ``ai_recommendation`` key added to
    each finding dict.  Uses OpenAI when a key is available, otherwise falls
    back to rule-based recommendations.
    """
    key = openai_key or os.getenv("OPENAI_API_KEY", "")

    ai_map: Dict[str, str] = {}
    if key:
        ai_map = _openai_recommendations(findings, key, model)

    enriched = []
    for f in findings:
        fid = f.get("id", "")
        title = f.get("title", "")
        ai_rec = ai_map.get(fid) or _rule_based_recommendation(fid, title)
        enriched.append({**f, "ai_recommendation": ai_rec})

    return enriched


def build_ai_summary(findings: List[Dict]) -> str:
    """
    Return a short plain-text executive summary paragraph derived from the
    enriched findings list (no API call – always fast).
    """
    from collections import Counter

    if not findings:
        return "No security issues were detected in this scan. Maintain regular scanning to stay ahead of emerging threats."

    counts: Counter = Counter(f.get("severity", "Info") for f in findings)
    critical = counts.get("Critical", 0)
    high = counts.get("High", 0)
    medium = counts.get("Medium", 0)
    info = counts.get("Info", 0) + counts.get("Low", 0)

    parts: List[str] = []
    if critical:
        parts.append(f"{critical} Critical finding(s) require immediate remediation")
    if high:
        parts.append(f"{high} High-severity issue(s) should be addressed within 24-48 hours")
    if medium:
        parts.append(f"{medium} Medium-severity issue(s) should be scheduled for the next sprint")
    if info:
        parts.append(f"{info} informational note(s) are provided for awareness")

    headline = "; ".join(parts) + "." if parts else "All findings are informational."

    top_ids = list({f.get("id", "").split("-")[0] + f.get("id", "") for f in findings[:5]})
    focus_areas = ", ".join(
        f.get("title", "")
        for f in sorted(findings, key=lambda x: ["Critical", "High", "Medium", "Info"].index(
            x.get("severity", "Info") if x.get("severity", "Info") in ["Critical", "High", "Medium", "Info"] else "Info"
        ))[:3]
    )
    return (
        f"{headline} "
        f"Priority focus areas: {focus_areas}. "
        "Review the detailed findings and AI-generated recommendations below for "
        "targeted remediation guidance."
    )
