"""Quick smoke test for ai_advisor and github_summary modules."""
import os
import sys
import tempfile

sys.path.insert(0, "/Users/mavoyan/Desktop/PipeScope")

from pipescope.core.ai_advisor import enrich_findings, build_ai_summary
from pipescope.core.github_summary import is_github_actions, write_github_summary

findings = [
    {
        "id": "PIPESCOPE-JENKINS-CVE-001",
        "title": "Potential Jenkins CVE: CVE-2023-1234",
        "severity": "High",
        "description": "A CVE was found.",
        "evidence": {},
        "recommendation": "",
        "cves": [{"id": "CVE-2023-1234", "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-1234"}],
    },
    {
        "id": "PIPESCOPE-JENKINS-001",
        "title": "Exposed Jenkins Endpoint: login",
        "severity": "Medium",
        "description": "Login page exposed.",
        "evidence": {"url": "http://localhost:8080/login"},
        "recommendation": "",
        "cves": [],
    },
]

enriched = enrich_findings(findings)
assert len(enriched) == 2, "Expected 2 enriched findings"
assert "ai_recommendation" in enriched[0], "ai_recommendation key missing"
assert enriched[0]["ai_recommendation"], "ai_recommendation is empty"
print("ai_recommendation (High finding):", enriched[0]["ai_recommendation"][:100])

summary = build_ai_summary(enriched)
assert summary, "AI summary is empty"
print("ai_summary excerpt:", summary[:120])

# Test GitHub summary writing to a temp file
with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
    tmp_path = tmp.name

os.environ["GITHUB_STEP_SUMMARY"] = tmp_path
os.environ["GITHUB_ACTIONS"] = "true"

data = {"tool": "PipeScope", "version": "0.1.0", "target": "test", "metadata": {}, "findings": findings}
write_github_summary(data, enriched, summary)

with open(tmp_path) as f:
    content = f.read()

assert "PipeScope Security Assessment" in content, "Header missing"
assert "Severity Breakdown" in content, "Severity table missing"
assert "AI Recommendations" in content or "AI Executive Summary" in content, "AI section missing"
assert "PIPESCOPE-JENKINS" in content, "Finding IDs missing"
print("GitHub Summary line count:", len(content.splitlines()))
print("is_github_actions():", is_github_actions())
print("\nALL CHECKS PASSED")
