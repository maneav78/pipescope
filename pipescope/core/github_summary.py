"""
Writes a rich Markdown job summary to $GITHUB_STEP_SUMMARY so findings,
AI recommendations, and an info panel are visible directly in the GitHub
Actions run page.

Usage (called automatically by the CLI when running in GitHub Actions):
    from pipescope.core.github_summary import write_github_summary
    write_github_summary(data, enriched_findings)
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Info": "🔵",
    "Low": "🟢",
}

_SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Info"]


def _emoji(severity: str) -> str:
    return _SEVERITY_EMOJI.get(severity, "⚪")


def _md_escape(text: str) -> str:
    """Minimal Markdown escaping for table cells."""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def is_github_actions() -> bool:
    """Return True when running inside a GitHub Actions runner."""
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


def _summary_path() -> Optional[str]:
    return os.getenv("GITHUB_STEP_SUMMARY")


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _info_panel(data: Dict, ai_summary: str) -> str:
    tool = data.get("tool", "PipeScope")
    version = data.get("version", "N/A")
    target = data.get("target", "N/A")
    mode = data.get("metadata", {}).get("mode", "")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    repo = os.getenv("GITHUB_REPOSITORY", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""
    actor = os.getenv("GITHUB_ACTOR", "")
    ref = os.getenv("GITHUB_REF_NAME", "")

    lines = [
        "## 🔍 PipeScope Security Assessment",
        "",
        "> **AI-assisted CI/CD security analysis — powered by PipeScope**",
        "",
        "### 📋 Scan Information",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| **Tool** | {tool} `{version}` |",
        f"| **Target** | `{target}` |",
        f"| **Mode** | `{mode if mode else 'full-scan'}` |",
        f"| **Generated** | {generated} |",
    ]
    if ref:
        lines.append(f"| **Branch / Ref** | `{ref}` |")
    if actor:
        lines.append(f"| **Triggered by** | @{actor} |")
    if run_url:
        lines.append(f"| **Run** | [View run]({run_url}) |")

    lines += [
        "",
        "### 🧠 AI Executive Summary",
        "",
        f"> {ai_summary}",
        "",
    ]
    return "\n".join(lines)


def _severity_table(findings: List[Dict]) -> str:
    counts: Counter = Counter(f.get("severity", "Info") for f in findings)
    total = len(findings)

    lines = [
        "### 📊 Severity Breakdown",
        "",
        "| Severity | Count | Share | Bar |",
        "|---|---|---|---|",
    ]
    for sev in _SEVERITY_ORDER:
        count = counts.get(sev, 0)
        if count == 0:
            continue
        pct = (count / total * 100) if total else 0
        bar_filled = int(pct / 5)  # 1 block per 5 %
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        lines.append(f"| {_emoji(sev)} **{sev}** | {count} | {pct:.1f}% | `{bar}` |")

    if not any(counts.get(s, 0) for s in _SEVERITY_ORDER):
        lines.append("| ✅ None | 0 | — | — |")

    lines.append("")
    return "\n".join(lines)


def _findings_table(findings: List[Dict]) -> str:
    if not findings:
        return "### ✅ No Findings\n\nNo security issues were detected.\n"

    # Sort by severity
    order = {s: i for i, s in enumerate(_SEVERITY_ORDER)}
    sorted_findings = sorted(
        findings,
        key=lambda f: order.get(f.get("severity", "Info"), 99),
    )

    lines = [
        "### 🔎 Detailed Findings with AI Recommendations",
        "",
        "| # | Sev | ID | Title | Evidence | Recommendation |",
        "|---|---|---|---|---|---|",
    ]

    for idx, f in enumerate(sorted_findings, 1):
        sev = f.get("severity", "Info")
        fid = _md_escape(f.get("id", "N/A"))
        title = _md_escape(f.get("title", "Untitled"))
        ev = f.get("evidence", {}) or {}
        evidence = _md_escape(ev.get("file") or ev.get("url") or "—")
        ai_rec = _md_escape(
            f.get("ai_recommendation")
            or f.get("recommendation")
            or "See documentation."
        )
        lines.append(
            f"| {idx} | {_emoji(sev)} {sev} | `{fid}` | {title} | {evidence} | {ai_rec} |"
        )

    lines.append("")
    return "\n".join(lines)


def _cve_table(findings: List[Dict]) -> str:
    cve_rows = []
    for f in findings:
        for cve in f.get("cves", []):
            cve_rows.append({
                "id": cve.get("id", "N/A"),
                "title": f.get("title", "N/A"),
                "severity": f.get("severity", "N/A"),
                "url": cve.get("url") or cve.get("href") or "",
            })
    if not cve_rows:
        return ""

    lines = [
        "### 🛡️ CVE References",
        "",
        "| CVE | Related Finding | Severity | Link |",
        "|---|---|---|---|",
    ]
    for row in cve_rows:
        link = f"[Advisory]({row['url']})" if row["url"] else "—"
        lines.append(
            f"| `{row['id']}` | {_md_escape(row['title'])} | "
            f"{_emoji(row['severity'])} {row['severity']} | {link} |"
        )
    lines.append("")
    return "\n".join(lines)


def _footer(findings: List[Dict]) -> str:
    high_crit = sum(
        1 for f in findings if f.get("severity") in ("Critical", "High")
    )
    lines = ["---", ""]
    if high_crit:
        lines += [
            f"⚠️ **{high_crit} High/Critical finding(s) detected.** "
            "This workflow will exit with code `1`. "
            "Resolve the findings above before merging.",
            "",
        ]
    else:
        lines += [
            "✅ **No High or Critical findings.** Good posture — keep scanning regularly.",
            "",
        ]
    lines += [
        "_Report generated by [PipeScope](https://github.com/your-org/pipescope) — "
        "CI/CD security enumeration tool._",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_github_summary(
    data: Dict,
    enriched_findings: List[Dict],
    ai_summary: str = "",
) -> None:
    """
    Write the full GitHub Actions job summary to $GITHUB_STEP_SUMMARY.
    Safe to call outside GitHub Actions (no-op when env var is absent).
    """
    summary_file = _summary_path()
    if not summary_file:
        return

    if not ai_summary:
        from pipescope.core.ai_advisor import build_ai_summary
        ai_summary = build_ai_summary(enriched_findings)

    sections = [
        _info_panel(data, ai_summary),
        _severity_table(enriched_findings),
        _findings_table(enriched_findings),
        _cve_table(enriched_findings),
        _footer(enriched_findings),
    ]
    content = "\n".join(sections)

    with open(summary_file, "a", encoding="utf-8") as fh:
        fh.write(content)


def print_ai_panel(enriched_findings: List[Dict], ai_summary: str, console) -> None:
    """
    Print a Rich-formatted AI advisory panel to the terminal (used in CLI).
    """
    from rich.panel import Panel
    from rich.table import Table

    console.print(Panel(ai_summary, title="🧠 AI Executive Summary", border_style="cyan"))

    table = Table(title="AI Recommendations", show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Severity", style="bold")
    table.add_column("AI Recommendation", overflow="fold")

    order = {s: i for i, s in enumerate(_SEVERITY_ORDER)}
    for f in sorted(enriched_findings, key=lambda x: order.get(x.get("severity", "Info"), 99)):
        table.add_row(
            f.get("id", ""),
            f.get("severity", "Info"),
            f.get("ai_recommendation", ""),
        )

    console.print(table)
