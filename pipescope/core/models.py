from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    INFO = "Info"

@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    cves: List[Dict[str, str]] = field(default_factory=list)

@dataclass
class ScanResult:
    tool: str
    version: str
    target: str
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "version": self.version,
            "target": self.target,
            "metadata": self.metadata,
            "findings": [
                {
                    "id": f.id,
                    "title": f.title,
                    "severity": f.severity.value,
                    "description": f.description,
                    "evidence": f.evidence,
                    "recommendation": f.recommendation,
                    "cves": f.cves,
                }
                for f in self.findings
            ],
        }