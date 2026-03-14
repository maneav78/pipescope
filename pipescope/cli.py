from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pipescope import __version__
from pipescope.core.scan import run_scan
from pipescope.utils.target import cleanup_resolved_target, resolve_target_to_path

console = Console()


def scan(
    target: Optional[str] = typer.Argument(None, help="Local repo path or git URL (https://... or git@...). Omit for URL-only scans."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write full results to a JSON file."),
    pdf_out: Optional[Path] = typer.Option(None, "--pdf", help="Write a summary of the results to a PDF file."),
    ref: Optional[str] = typer.Option(None, "--ref", help="Branch/tag/commit to scan (URLs only)."),
    depth: int = typer.Option(1, "--depth", help="Git clone depth for URL targets."),
    token: Optional[str] = typer.Option(None, "--token", help="Token for HTTPS clone (URLs only)."),
    keep: bool = typer.Option(False, "--keep", help="Keep cloned temp directory (do not cleanup)."),
    workdir: Optional[Path] = typer.Option(None, "--workdir", help="Directory to place temporary clones."),
    web_url: Optional[str] = typer.Option(None, "--web-url", help="URL to run web reconnaissance on."),
    jenkins_url: Optional[str] = typer.Option(None, "--jenkins-url", help="URL of Jenkins server to scan."),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url", help="URL of GitLab server to scan."),
    wordlist: Optional[Path] = typer.Option(None, "--wordlist", help="Path to wordlist for web recon."),
    wordlist_name: str = typer.Option("common", "--wordlist-name", help="Name of the wordlist to use for web recon (e.g., common, quickhits)."),
    threads: int = typer.Option(10, "--threads", help="Number of threads for web recon."),
    ai: bool = typer.Option(True, "--ai/--no-ai", help="Enrich findings with AI recommendations (rule-based by default; uses OpenAI if OPENAI_API_KEY is set)."),
    openai_key: Optional[str] = typer.Option(None, "--openai-key", envvar="OPENAI_API_KEY", help="OpenAI API key for LLM-enhanced recommendations."),
    fail_on_high: bool = typer.Option(True, "--fail-on-high/--no-fail-on-high", help="Exit with code 1 when High or Critical findings are detected (default: True)."),
):
    """
    Scan a repository for CI/CD configuration presence and basic risk heuristics.
    Accepts a local path (primary) or a URL (cloned to a temp workspace).
    Automatically writes a rich GitHub Actions job summary when running in CI.
    """
    if target is None and not any([web_url, jenkins_url, gitlab_url]):
        raise typer.BadParameter(
            "Provide TARGET or at least one of --web-url, --jenkins-url, or --gitlab-url."
        )

    resolved = None
    if target is not None:
        resolved = resolve_target_to_path(
            target,
            ref=ref,
            depth=depth,
            token=token,
            keep=keep,
            workdir=workdir,
        )

    try:
        res = run_scan(
            resolved.path if resolved else None,
            version=__version__,
            web_url=web_url,
            jenkins_url=jenkins_url,
            gitlab_url=gitlab_url,
            wordlist_path=str(wordlist) if wordlist else None,
            wordlist_name=wordlist_name,
            threads=threads,
        )
        data = res.to_dict()

        # ── AI enrichment ────────────────────────────────────────────────────
        from pipescope.core.ai_advisor import enrich_findings, build_ai_summary
        from pipescope.core.github_summary import (
            is_github_actions,
            print_ai_panel,
            write_github_summary,
        )

        enriched_findings = enrich_findings(data["findings"], openai_key=openai_key) if ai else data["findings"]
        ai_summary = build_ai_summary(enriched_findings)

        # ── Terminal output ──────────────────────────────────────────────────
        table = Table(title="PipeScope — CI/CD Enumeration Summary")
        table.add_column("Severity", style="bold")
        table.add_column("ID")
        table.add_column("Title")
        table.add_column("Evidence")
        table.add_column("CVEs")

        for f in data["findings"]:
            ev = f.get("evidence", {}) or {}
            evidence = str(ev.get("file", "")) or str(ev.get("url", ""))
            cves_str = ""
            if f.get("cves"):
                cves_str = ", ".join(cve["id"] for cve in f["cves"])
            table.add_row(f["severity"], f["id"], f["title"], evidence, cves_str)

        console.print(table)

        # Summary table
        summary_table = Table(title="Findings Summary")
        summary_table.add_column("Severity")
        summary_table.add_column("Count")
        
        severities = [f["severity"] for f in data["findings"]]
        severity_counts = {sev: severities.count(sev) for sev in set(severities)}
        
        for sev, count in sorted(severity_counts.items()):
            summary_table.add_row(sev, str(count))
        
        console.print(summary_table)

        # AI panel (terminal)
        if ai:
            print_ai_panel(enriched_findings, ai_summary, console)

        # ── File outputs ─────────────────────────────────────────────────────
        # Merge ai_recommendation into JSON if AI is enabled
        output_data = {**data, "findings": enriched_findings}

        if json_out:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote JSON report:[/green] {json_out}")
        
        if pdf_out:
            from pipescope.core.pdf_report import generate_pdf_report
            pdf_out.parent.mkdir(parents=True, exist_ok=True)
            generate_pdf_report(output_data, pdf_out)
            console.print(f"[green]Wrote PDF report:[/green] {pdf_out}")

        # ── GitHub Actions: write job summary ────────────────────────────────
        write_github_summary(data, enriched_findings, ai_summary)
        if is_github_actions():
            # Emit output variables for downstream steps
            github_output = os.getenv("GITHUB_OUTPUT", "")
            if github_output:
                counts = {sev: severities.count(sev) for sev in set(severities)}
                with open(github_output, "a", encoding="utf-8") as gh:
                    gh.write(f"findings-count={len(data['findings'])}\n")
                    gh.write(f"high-count={counts.get('High', 0)}\n")
                    gh.write(f"critical-count={counts.get('Critical', 0)}\n")

        # ── Exit code ────────────────────────────────────────────────────────
        has_high_crit = any(f["severity"] in ("High", "Critical") for f in data["findings"])
        if has_high_crit and fail_on_high:
            console.print("[bold red]High or Critical severity findings detected. Exiting with status 1.[/bold red]")
            raise typer.Exit(code=1)

    finally:
        if resolved:
            cleanup_resolved_target(resolved)


def main():
    typer.run(scan)


if __name__ == "__main__":
    main()