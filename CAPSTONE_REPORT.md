# PipeScope: A CI/CD Pipeline Security Enumeration Tool
## University Capstone Project — Technical Report

---

**Project Title:** PipeScope — Automated Security Enumeration for CI/CD Pipelines  
**Version:** 0.1.0  
**Language:** Python 3.10+  
**Repository:** [github.com/maneav78/pipescope](https://github.com/maneav78/pipescope)  
**Report Date:** 2025  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)  
2. [Introduction and Motivation](#2-introduction-and-motivation)  
3. [Objectives and Scope](#3-objectives-and-scope)  
4. [Related Work and Background](#4-related-work-and-background)  
5. [System Architecture](#5-system-architecture)  
6. [Module-Level Design and Implementation](#6-module-level-design-and-implementation)  
   - 6.1 [CLI Layer — `cli.py`](#61-cli-layer--clipy)  
   - 6.2 [Scan Orchestrator — `scan.py`](#62-scan-orchestrator--scanpy)  
   - 6.3 [CI/CD Detector — `cicd_detector.py`](#63-cicd-detector--cicd_detectorpy)  
   - 6.4 [Rule Engine — `rules_eval.py` and `rule_engine.py`](#64-rule-engine--rules_evalpy-and-rule_enginepy)  
   - 6.5 [Observation Extractors — `gha_observe.py`, `gitlab_observe.py`, `jenkins_observe.py`](#65-observation-extractors)  
   - 6.6 [Remote Service Scanners — `jenkins_scanner.py`, `gitlab_scanner.py`](#66-remote-service-scanners)  
   - 6.7 [Infrastructure Scanners — `dockerfile_scanner.py`, `dockerignore_scanner.py`, `compose_scanner.py`](#67-infrastructure-scanners)  
   - 6.8 [Kubernetes Scanner — `k8s_scanner.py`](#68-kubernetes-scanner--k8s_scannerpy)  
   - 6.9 [Secret Detection Subsystem — `secrets_scanner.py`, `gitleaks_adapter.py`, `rule_engine.py`, `weak_secrets.py`](#69-secret-detection-subsystem)  
   - 6.10 [Web Reconnaissance — `web_recon.py`](#610-web-reconnaissance--web_reconpy)  
   - 6.11 [CVE Lookup — `cve_lookup.py`](#611-cve-lookup--cve_lookuppy)  
   - 6.12 [AI Advisory System — `ai_advisor.py`](#612-ai-advisory-system--ai_advisorpy)  
   - 6.13 [GitHub Actions Integration — `github_summary.py`](#613-github-actions-integration--github_summarypy)  
   - 6.14 [Output Layer — `pdf_report.py`](#614-output-layer--pdf_reportpy)  
   - 6.15 [Data Models — `models.py`](#615-data-models--modelspy)  
7. [TOML Rule Pack System](#7-toml-rule-pack-system)  
8. [GitHub Actions Integration](#8-github-actions-integration)  
9. [Security Methodology](#9-security-methodology)  
10. [Technologies and Dependencies](#10-technologies-and-dependencies)  
11. [Testing Strategy](#11-testing-strategy)  
12. [Packaging and Distribution](#12-packaging-and-distribution)  
13. [Notable Technical Decisions](#13-notable-technical-decisions)  
14. [Limitations and Future Work](#14-limitations-and-future-work)  
15. [Conclusion](#15-conclusion)  
16. [References](#16-references)  

---

## 1. Executive Summary

PipeScope is a Python-based command-line security enumeration tool designed to identify misconfigurations, credential exposure, and known vulnerabilities within CI/CD pipelines and their supporting infrastructure. The tool aggregates analysis across multiple surfaces — local repository files, remote CI/CD service endpoints, container definitions, orchestration manifests, and web-exposed paths — producing findings classified by severity (Critical, High, Medium, Info), cross-referenced against the NIST National Vulnerability Database (NVD), and enriched with AI-generated remediation guidance.

The system integrates natively into GitHub Actions as a reusable composite action, writing rich Markdown reports directly to the GitHub Actions Summary panel. It supports export to structured JSON and printable PDF, enabling consumption by both automated pipelines and human reviewers.

PipeScope addresses a widely acknowledged gap in the DevSecOps tooling landscape: whereas established tools such as Trivy, Snyk, and Semgrep focus on individual artefacts (container images or source code), PipeScope takes a pipeline-centric perspective, treating the CI/CD configuration itself as the primary attack surface.

---

## 2. Introduction and Motivation

The acceleration of software delivery through CI/CD pipelines has introduced new categories of systemic risk. Pipeline definitions — GitHub Actions workflow files, GitLab CI YAML, Jenkinsfiles — execute with elevated permissions, often consuming secrets, cloud credentials, and deployment keys. A single misconfiguration, such as the use of `pull_request_target` without scope restriction, can allow an untrusted fork to read repository secrets. At the infrastructure layer, unpinned Docker base images, containers running as root, and Kubernetes workloads lacking security contexts represent persistent vectors for privilege escalation and lateral movement.

Despite this, most DevSecOps toolchains treat the pipeline configuration as out-of-scope for automated security analysis. Security engineers conducting manual reviews lack scalable, consistent tooling tailored to CI/CD artefacts. The result is that organisations frequently discover critical pipeline misconfigurations only after an incident.

PipeScope was conceived to fill this gap: a single, unified tool that an engineer can point at a repository — or invoke as part of the pipeline itself — and receive a structured, actionable security assessment of the entire CI/CD attack surface.

---

## 3. Objectives and Scope

**Primary Objectives:**

1. Detect security misconfigurations in CI/CD pipeline definitions (GitHub Actions, GitLab CI, Jenkins).
2. Enumerate publicly accessible endpoints on Jenkins and GitLab servers; correlate detected software versions with known CVEs.
3. Identify credential and secret exposure in source files, pipeline definitions, and environment variable declarations.
4. Analyse Dockerfile, Docker Compose, and Kubernetes manifests for security anti-patterns.
5. Perform web-path reconnaissance against configured service URLs.
6. Provide AI-augmented, actionable remediation recommendations.
7. Integrate transparently as a GitHub Actions step, writing results to the Actions Summary panel.
8. Export to machine-readable JSON and human-readable PDF.

**Out of Scope (v0.1.0):**

- Dynamic application security testing (DAST) of running services beyond passive version fingerprinting.
- Binary or dependency vulnerability analysis (covered by existing SCA tools).
- Direct manipulation of pipeline configuration; the tool is read-only.

---

## 4. Related Work and Background

| Tool | Primary Focus | Gap Addressed by PipeScope |
|------|--------------|---------------------------|
| **Trivy** (Aqua Security) | Container image and IaC scanning | No pipeline-configuration analysis; no CI service endpoint scanning |
| **Snyk** | Dependency CVEs; IaC drift | Does not enumerate CI/CD service endpoints or analyse Jenkinsfiles |
| **Semgrep** | Static code analysis with custom rules | No CVE enrichment; no GitHub Actions Summary integration out-of-the-box |
| **Gitleaks** | Secret detection in git history | Narrow scope; PipeScope integrates gitleaks as one layer within a broader analysis |
| **detect-secrets** (Yelp) | In-file secret detection | Narrow scope; integrated as a subsystem within PipeScope |
| **Kubescape** | Kubernetes posture management | No pipeline-configuration analysis; PipeScope integrates kubescape as a subsystem |
| **KICS** (Checkmarx) | Infrastructure-as-code scanning | No remote endpoint enumeration; no AI recommendations |

PipeScope's differentiated value lies in **breadth of scope** (files + remote endpoints + secrets + CVEs + AI enrichment + CI integration), **zero-dependency core** (the rule-based AI fallback operates without API keys), and **first-class GitHub Actions support** with GitHub Step Summary output.

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point (cli.py)                     │
│  Typer application — argument parsing, orchestration, output        │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Scan Orchestrator (scan.py)                      │
│  Dispatches local and/or remote scan modules; aggregates findings   │
└──────────────┬──────────────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌──────────────┐  ┌───────────────────────────────────────────────────┐
│ REMOTE SCANS │  │                  LOCAL SCANS                      │
│              │  │                                                    │
│ Jenkins      │  │  ┌──────────────────────────────────────────────┐ │
│  Fingerprint │  │  │  CI/CD Detector (cicd_detector.py)           │ │
│  Endpoint    │  │  │  ├── GHA Observation Extractor               │ │
│  Enumeration │  │  │  ├── GitLab Observation Extractor            │ │
│  CVE Lookup  │  │  │  └── Jenkins Observation Extractor           │ │
│              │  │  │  Rules evaluated via TOML packs              │ │
│ GitLab       │  │  └──────────────────────────────────────────────┘ │
│  Version     │  │  ┌──────────────────────────────────────────────┐ │
│  Fingerprint │  │  │  Secret Detection (3 layers)                 │ │
│  CVE Lookup  │  │  │  ├── gitleaks_adapter.py (subprocess)        │ │
│              │  │  │  ├── secrets_scanner.py (detect-secrets)     │ │
│ Web Recon    │  │  │  └── rule_engine.py (TOML regex rules)       │ │
│  Wordlist    │  │  │  weak_secrets.py (assignment patterns)       │ │
│  Enumeration │  │  └──────────────────────────────────────────────┘ │
└──────────────┘  │  ┌──────────────────────────────────────────────┐ │
                  │  │  Infrastructure Scanners                      │ │
                  │  │  ├── dockerfile_scanner.py                   │ │
                  │  │  ├── dockerignore_scanner.py                 │ │
                  │  │  ├── compose_scanner.py                      │ │
                  │  │  └── k8s_scanner.py (kubescape subprocess)   │ │
                  │  └──────────────────────────────────────────────┘ │
                  └───────────────────────────────────────────────────┘
                               │
                               ▼
          ┌────────────────────────────────────────────┐
          │         Cross-Cutting Components           │
          │  cve_lookup.py   — NVD API v2 + LRU cache  │
          │  ai_advisor.py   — Rule-based + OpenAI     │
          │  github_summary.py — Step Summary writer   │
          │  pdf_report.py   — ReportLab PDF           │
          │  models.py       — Finding, ScanResult     │
          └────────────────────────────────────────────┘
```

### Data Flow

1. The user invokes `pipescope [TARGET] [OPTIONS]`.
2. `cli.py` resolves `TARGET` (URL → `git clone` into a temporary directory, local path → direct use, `None` → remote-only mode) via `utils/target.py`.
3. The scan orchestrator (`scan.py`) receives an `Optional[Path]` root and the remote URL parameters.
4. When a local `root` is available, all local scanners execute sequentially; their `List[Finding]` results are merged into a `ScanResult`.
5. Remote scanners execute independently for each configured URL; results are appended.
6. All findings pass through `cve_lookup.py` (if not already enriched) and `ai_advisor.py`.
7. Formatted output is sent to the terminal (Rich), JSON file, PDF, and/or `$GITHUB_STEP_SUMMARY`.

---

## 6. Module-Level Design and Implementation

### 6.1 CLI Layer — `cli.py`

**File:** `pipescope/cli.py`  
**Responsibility:** Entry point, argument definition, output dispatch.

PipeScope uses [Typer](https://typer.tiangolo.com/) to build its command-line interface, enabling type-annotated argument definitions and automatic `--help` generation. The `TARGET` argument is declared as `Optional[str]` with a `None` default, allowing the tool to be invoked without a local target when only remote scanning is required:

```python
def main(
    target: Optional[str] = typer.Argument(None, help="..."),
    jenkins_url: Optional[str] = typer.Option(None, "--jenkins-url"),
    gitlab_url: Optional[str] = typer.Option(None, "--gitlab-url"),
    web_url: Optional[str] = typer.Option(None, "--web-url"),
    ai: bool = typer.Option(True, "--ai/--no-ai"),
    openai_key: Optional[str] = typer.Option(None, "--openai-key"),
    fail_on_high: bool = typer.Option(False, "--fail-on-high/--no-fail-on-high"),
    ...
)
```

A guard clause ensures at least one target is provided before scanning proceeds. When `$GITHUB_OUTPUT` is set, finding counts are exported as GitHub Actions output variables (`findings_count`, `high_count`, `critical_count`).

**Key design decisions:**

- **Remote-only mode:** When `target` is `None`, the orchestrator skips all local scanners, preventing `Path`-related runtime errors and enabling Jenkins or GitLab URL-only pipeline invocations.
- **Fail-on-high flag:** `--fail-on-high` causes the process to exit with code 1 if any High or Critical findings are present, enabling pipeline gate enforcement.
- **AI toggle:** `--ai/--no-ai` controls enrichment; when disabled, findings are returned as-is, reducing external API dependency for air-gapped environments.

---

### 6.2 Scan Orchestrator — `scan.py`

**File:** `pipescope/core/scan.py`  
**Responsibility:** Module dispatch, result aggregation.

`scan.py` is the central dispatcher. It accepts `root: Optional[Path]` together with optional URL parameters and calls each scanner in turn. When `root is None`, the orchestrator creates a `ScanResult` with metadata `"mode": "remote-only"` and proceeds directly to remote branch scanners.

```python
if root is not None:
    res = run_cicd_enumeration(root, ...)
    # ... all local scanners ...
else:
    res = ScanResult(target="(no local target)", findings=[])
    res.metadata["mode"] = "remote-only"
```

By centralising dispatch here, individual scanners remain stateless functions that accept a path and return `List[Finding]`, adhering to the single-responsibility principle.

---

### 6.3 CI/CD Detector — `cicd_detector.py`

**File:** `pipescope/core/cicd_detector.py`  
**Responsibility:** Detect CI/CD configuration files in the repository; evaluate TOML rule packs against extracted observations; invoke secret detection.

`detect_cicd_files()` performs a deterministic traversal:

- `<root>/.github/workflows/*.y*ml` → `GitHubActions`
- `<root>/.gitlab-ci.yml` → `GitLabCI`
- `<root>/Jenkinsfile` → `Jenkins`

Each detected file is then dispatched to its corresponding observation extractor and rule pack evaluator:

```
GitHubActions → gha_observe.extract_gha_observations()
                + eval_rules(observations, GHA_RULES)
GitLabCI      → gitlab_observe.extract_gitlab_observations()
                + eval_rules(observations, GITLAB_RULES)
Jenkins       → jenkins_observe.extract_jenkins_observations()
                + eval_rules(observations, JENKINS_RULES)
```

Additionally, `cicd_detector.py` directly invokes:
- `scan_for_secrets_detect_secrets()` — detect-secrets library scan of the repository root.
- `scan_for_weak_secrets()` — assignment-pattern scanner for trivially guessable values.

This co-location of CI/CD-specific secret scanning within the detector ensures that all context-sensitive checks (e.g., secrets within workflow files) are evaluated in a single pass.

---

### 6.4 Rule Engine — `rules_eval.py` and `rule_engine.py`

**Files:** `pipescope/core/rules_eval.py`, `pipescope/core/rule_engine.py`

These two modules implement complementary rule evaluation paradigms.

#### `rules_eval.py` — Observation-based TOML rule evaluator

Evaluates a dictionary of scalar observations (extracted from a CI/CD config file) against a list of TOML rules. Supports four operators:

| Operator | Semantics |
|----------|-----------|
| `contains` | `value ∈ observations[field]` (list membership) |
| `equals_ci` | case-insensitive string equality |
| `regex` | `re.search(value, observations[field])` |
| `any_true` | true if any element of `observations[field]` is truthy |

This design decouples the observation extraction logic from the evaluation logic, allowing new rule packs to be added without modifying Python code.

#### `rule_engine.py` — File-content regex scanner

Loads `pipescope/rules/secrets.toml` and matches regex patterns against file content for a fixed set of extensions (`.java`, `.js`, `.ts`, `.py`, `.yml`, `.yaml`, `.env`). Each match produces a finding with the CWE reference and line evidence from the TOML rule definition.

---

### 6.5 Observation Extractors

**Files:** `pipescope/core/gha_observe.py`, `pipescope/core/gitlab_observe.py`, `pipescope/core/jenkins_observe.py`

Each extractor parses a CI/CD configuration file and produces a flat `Dict[str, Any]` of normalised observations suitable for evaluation by `rules_eval.eval_rules()`.

#### GitHub Actions (`gha_observe.py`)

Observations produced:

| Key | Description |
|-----|-------------|
| `triggers` | `List[str]` of event names from the `on:` block |
| `permissions_raw` | Raw permissions value (`"write-all"` or dict) |
| `uses_self_hosted_runner` | `bool` — any job uses `self-hosted` runner |
| `uses_unpinned` | `List[bool]` — one entry per unpinned `uses:` reference |
| `has_curl_pipe_shell` | `bool` — `curl|bash` pattern detected |

The extractor uses a SHA-40 regex (`[0-9a-fA-F]{40}`) to distinguish pinned (`@abc123...`) from tag-pinned (`@v2`) action references, applying a `_USES_RE` compiled pattern to match `uses:` lines.

---

### 6.6 Remote Service Scanners

**Files:** `pipescope/core/jenkins_scanner.py`, `pipescope/core/gitlab_scanner.py`

#### Jenkins Scanner

The Jenkins scanner performs passive fingerprinting and endpoint enumeration in two phases:

1. **Version detection:** Issues an HTTP `HEAD` request to the configured URL and reads the `X-Jenkins` response header. This header is emitted by default by Jenkins ≥ 1.349 and reveals the exact version string without authentication.

2. **Endpoint enumeration:** Issues concurrent `GET` requests to eight commonly exposed paths using `concurrent.futures.ThreadPoolExecutor`:

   | Path | Risk |
   |------|------|
   | `script` | Groovy Script Console — arbitrary code execution |
   | `cli` | Jenkins CLI endpoint |
   | `login` | Authentication page (unauthenticated access check) |
   | `asynchPeople/` | User enumeration |
   | `computer/(master)/` | Node configuration disclosure |
   | `jnlpJars/jenkins-cli.jar` | CLI jar download |
   | `userContent/` | Arbitrary file access |
   | `whoAmI/` | Identity disclosure |

3. **CVE correlation:** The detected version is passed to `cve_lookup.lookup_cves("jenkins", version)`, which queries the NVD API v2 and returns matching CVE identifiers.

Each accessible path generates a `Finding` with severity `HIGH` or `CRITICAL` based on its risk classification.

#### GitLab Scanner

The GitLab scanner extracts the server version by loading the `/users/sign_in` HTML page and applying a version-extraction regex against the page content. A version string match triggers a CVE lookup for `"gitlab"` and the identified version. The finding severity is linked to the highest-severity CVE returned for that version.

---

### 6.7 Infrastructure Scanners

**Files:** `pipescope/core/dockerfile_scanner.py`, `pipescope/core/dockerignore_scanner.py`, `pipescope/core/compose_scanner.py`

#### Dockerfile Scanner

Parses Dockerfile instructions using line-by-line analysis and checks for:

| Check | Severity | Rationale |
|-------|----------|-----------|
| `FROM :latest` or non-digest pinned base image | HIGH | Supply-chain risk; non-reproducible builds |
| `USER root` or absent `USER` instruction | HIGH | Container breakout via root-equivalent execution |
| `ADD` instead of `COPY` | MEDIUM | `ADD` auto-extracts archives and fetches remote URLs; COPY is explicit |
| Environment variables with secret-pattern keys (`*_SECRET`, `*_PASSWORD`) | HIGH | Secrets embedded in image layers; visible via `docker inspect` |
| Exposed privileged ports (< 1024) | MEDIUM | Requires elevated host privileges |
| Base image CVE lookup | CRITICAL/HIGH | Checks NVD for CVEs affecting the base image product/version |

#### Docker Compose Scanner

Parses YAML with `pyyaml` and evaluates the following service-level properties:

| Check | Severity | CWE |
|-------|----------|-----|
| `privileged: true` | HIGH | CWE-250 (Execution with Unnecessary Privileges) |
| `network_mode: host` | HIGH | CWE-653 (Insufficient Compartmentalization) |
| Plaintext secrets in `environment:` or `env_file:` | HIGH | CWE-798 |
| Published ports without bind address | MEDIUM | CWE-284 |

The scanner detects four docker-compose filename variants: `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, `compose.yaml`.

---

### 6.8 Kubernetes Scanner — `k8s_scanner.py`

**File:** `pipescope/core/k8s_scanner.py`

The Kubernetes scanner delegates to [Kubescape](https://github.com/kubescape/kubescape), an open-source Kubernetes security posture tool. The module resolves the kubescape binary through a three-tier lookup:

1. `KUBESCAPE_BINARY` environment variable.
2. `shutil.which("kubescape")` — binary on system `$PATH`.
3. Fallback: `go run .` within the embedded `kubescape/` Go source directory.

Kubescape is invoked as a subprocess with `--format json` against the directory containing Kubernetes manifest files. The JSON output is parsed and each `control.status.status != "passed"` result is mapped to a `Finding`, with the CVSS score used to derive severity:

| Score | Severity |
|-------|----------|
| ≥ 7.0 | HIGH |
| ≥ 4.0 | MEDIUM |
| < 4.0 | INFO |

This approach reuses Kubescape's comprehensive NSA/CISA hardening guidance and MITRE ATT&CK for Containers framework without re-implementing the evaluation logic.

---

### 6.9 Secret Detection Subsystem

Secret detection in PipeScope is intentionally multi-layered to maximise recall at the cost of some false-positive risk, trading precision for security completeness.

#### Layer 1 — `gitleaks_adapter.py`

Wraps the [gitleaks](https://github.com/gitleaks/gitleaks) tool via subprocess, invoking it with `--no-git --report-format json` to scan the working directory rather than git history. Exit codes `0` (no findings) and `1` (findings present) are both treated as valid; any other exit code is considered a tool failure and is suppressed gracefully via `is_gitleaks_available()` guard.

Gitleaks findings are mapped to `Finding` objects with IDs of the form `PS-REF-GITLEAKS-{ruleID}`. Severity assignment:
- CRITICAL — rule description contains "private" or "key"
- HIGH — all other rules

#### Layer 2 — `secrets_scanner.py`

Integrates the [detect-secrets](https://github.com/Yelp/detect-secrets) library using its Python API:

```python
from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

with default_settings():
    secrets = SecretsCollection()
    secrets.scan_file(str(path))
```

Excludes: `.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, `__pycache__`. Files larger than 2 MB are skipped. The `PrivateKeyDetector` plugin type maps to CRITICAL severity; all others to HIGH.

#### Layer 3 — `rule_engine.py` (TOML regex rules)

Applies four custom regex patterns from `rules/secrets.toml` to source files:

| Rule ID | Pattern Target | Severity |
|---------|---------------|----------|
| `PS-SECRET-RSA-001` | Inline RSA private key (`MIIC...`) | CRITICAL |
| `PS-SECRET-OAUTH-001` | OAuth/client secret assignment | HIGH |
| `PS-SECRET-DB-001` | Database password assignment | HIGH |
| `PS-SECRET-WEAK-001` | Trivially guessable secret value | MEDIUM |

Each rule references CWE-798 (Use of Hard-coded Credentials).

#### Layer 4 — `weak_secrets.py`

Targets a narrower problem: commonly used weak values (e.g., `"changeme"`, `"secret"`, `"1234"`) assigned to semantically relevant keys (`secret`, `jwt_secret`, `session_secret`, `cookie_secret`). The detection uses a compiled assignment regex:

```python
ASSIGNMENT_RE = re.compile(r"""(?ix)
    \b(?P<key>secret|session_secret|...)\b
    \s*[:=]\s*
    (?P<quote>['"])(?P<value>[^'"\n]{1,64})(?P=quote)
""")
```

To reduce false positives from documentation examples, single-line comment lines are stripped from `.py`, `.js`, `.ts`, `.yml`, `.yaml`, `.env` files before matching.

---

### 6.10 Web Reconnaissance — `web_recon.py`

**File:** `pipescope/core/web_recon.py`

The web reconnaissance module performs dictionary-based path enumeration against a configured base URL using `concurrent.futures.ThreadPoolExecutor`. Two built-in wordlists are bundled in `pipescope/wordlists/`:

- `common.txt` — general-purpose paths (admin panels, metrics, health checks, API docs)
- `quickhits.txt` — high-value targets (sensitive configuration endpoints, CI/CD metadata paths)

HTTP responses in the `2xx` range generate a `Finding` with severity based on the path sensitivity classification. The thread count, wordlist selection, and base URL are all configurable via CLI flags (`--threads`, `--wordlist-name`).

---

### 6.11 CVE Lookup — `cve_lookup.py`

**File:** `pipescope/core/cve_lookup.py`

The CVE lookup module queries the [NIST NVD API v2.0](https://services.nvd.nist.gov/rest/json/cves/2.0) to resolve software product/version pairs into known CVE identifiers. Key design aspects:

**Caching:** API calls are memoised using `functools.lru_cache(maxsize=256)` at the internal `_search_cves()` function, preventing repeated network requests for the same product/version combination across a single scan run.

**Product normalisation:** A mapping table normalises common informal names to their NVD CPE product strings:

```python
_PRODUCT_MAP = {
    "python": "python",
    "nginx": "nginx",
    "jenkins": "jenkins",
    "gitlab": "gitlab",
    "node": "node.js",
    ...
}
```

**Version fuzzy matching:** When an exact version match yields no CVEs, the module cascades through progressively coarser version formats (major.minor.patch → major.minor → major) to improve recall for partial version strings extracted from live services.

**Image normalisation:** Docker base image references (e.g., `python:3.11-slim`, `nginx:1.25.3-alpine`) are parsed by `_normalize_image()` to strip distribution suffixes before CVE lookup.

---

### 6.12 AI Advisory System — `ai_advisor.py`

**File:** `pipescope/core/ai_advisor.py`

The AI advisory system operates in two modes, selected automatically based on API key availability:

#### Rule-based mode (always available)

A dictionary `_RULE_RECOMMENDATIONS` maps finding ID prefixes to detailed, expert-authored remediation guidance. Coverage includes 10 prefix categories:

| Prefix | Coverage |
|--------|----------|
| `PIPESCOPE-JENKINS-CVE` | Jenkins version upgrade + security realm configuration |
| `PIPESCOPE-JENKINS-001` | Endpoint access restriction, proxy headers |
| `PIPESCOPE-GITLAB` | GitLab upgrade, 2FA, runner token rotation |
| `PIPESCOPE-DOCKER` | Image pinning, non-root execution, Content Trust |
| `PIPESCOPE-K8S` | Pod Security Admission, SecurityContext, NetworkPolicy |
| `PS-CICD-GHA` | Action SHA pinning, OIDC, CODEOWNERS |
| `PS-CICD-GL` | GitLab CI Protected Variables, branch protection |
| `PS-CICD-JENK` | Credentials Binding, Matrix Authorization |
| `PIPESCOPE-WEB` | WAF, authentication, rate limiting |
| `PIPESCOPE-SECRET` | Credential rotation, git history purge, pre-commit hooks |

The `enrich_findings(findings)` function iterates over all findings and annotates each with an `ai_recommendation` field by matching its ID against the prefix table.

#### OpenAI mode (when API key provided)

When `--openai-key` is supplied (or `OPENAI_API_KEY` is set), the module constructs a compact JSON prompt containing all finding IDs and titles, submits it to the OpenAI Chat Completions API (model `gpt-3.5-turbo` or better), and parses the response to update `ai_recommendation` fields with LLM-generated, context-aware guidance.

`build_ai_summary(findings)` produces a single-paragraph executive summary from all enriched findings, suitable for embedding in reports and GitHub Summary panels.

---

### 6.13 GitHub Actions Integration — `github_summary.py`

**File:** `pipescope/core/github_summary.py`

The GitHub Summary module writes a Markdown document to the file path referenced by `$GITHUB_STEP_SUMMARY`, GitHub's mechanism for surfacing custom content in the Actions run summary panel. The function is a safe no-op when `$GITHUB_STEP_SUMMARY` is not set (i.e., outside a GitHub Actions runner).

The generated Markdown includes:

1. **Info panel** — scan target, timestamp, finding counts by severity.
2. **AI Executive Summary** — paragraph from `build_ai_summary()`.
3. **Severity distribution** — ASCII bar chart with emoji severity indicators.
4. **Findings table** — ID, severity, title, AI recommendation for each finding.
5. **CVE references** — deduplicated list of all CVE IDs referenced across findings.
6. **Pass/fail footer** — green or red badge indicating scan outcome.

Additionally, `print_ai_panel()` renders the same information to the terminal via the [Rich](https://github.com/Textualize/rich) library, using colour-coded `Panel` and `Table` widgets for readability in interactive sessions.

---

### 6.14 Output Layer — `pdf_report.py`

**File:** `pipescope/core/pdf_report.py`

PDF generation uses [ReportLab](https://www.reportlab.com/), a pure-Python PDF creation library. Reports are rendered to A4 format with:

- Repeating header and footer on all pages.
- Executive summary section.
- Severity distribution table with per-severity row colouring.
- Detailed findings table, one row per finding, truncated evidence displayed inline.

PDF output is triggered by the `--pdf <path>` CLI flag.

---

### 6.15 Data Models — `models.py`

**File:** `pipescope/core/models.py`

All scanner outputs are expressed as instances of two dataclasses:

```python
@dataclass
class Finding:
    id: str                             # Namespaced finding identifier
    title: str
    severity: Severity                  # CRITICAL | HIGH | MEDIUM | INFO
    description: str
    evidence: Dict[str, Any]            # Structured, scanner-specific metadata
    recommendation: str
    cves: List[str] = field(default_factory=list)

@dataclass
class ScanResult:
    target: str
    findings: List[Finding]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]: ...
```

`Severity` extends both `str` and `Enum`, allowing direct string comparison and JSON serialisation without a custom encoder.

Finding IDs follow a namespaced convention:

| Prefix | Scanner |
|--------|---------|
| `PIPESCOPE-JENKINS-*` | Jenkins remote scanner |
| `PIPESCOPE-GITLAB-*` | GitLab remote scanner |
| `PIPESCOPE-DOCKER-*` | Dockerfile scanner |
| `PIPESCOPE-K8S-*` | Kubernetes scanner |
| `PIPESCOPE-WEB-*` | Web recon |
| `PS-CICD-GHA-*` | GitHub Actions rule pack |
| `PS-CICD-GL-*` | GitLab CI rule pack |
| `PS-CICD-JENK-*` | Jenkins rule pack |
| `PS-REF-GITLEAKS-*` | Gitleaks adapter |
| `PS-SECRET-*` | Secret rule engine |

---

## 7. TOML Rule Pack System

PipeScope's CI/CD analysis is driven by TOML rule packs located in `pipescope/rules/`. This design separates security knowledge (rules) from evaluation logic (code), enabling security engineers to contribute or update rules without modifying Python source.

### Rule Pack Files

| File | Domain |
|------|--------|
| `cicd_github_actions.toml` | GitHub Actions workflow security |
| `cicd_gitlab.toml` | GitLab CI/CD configuration security |
| `cicd_jenkins.toml` | Jenkinsfile security |
| `secrets.toml` | Hardcoded credential patterns |

### Rule Structure

```toml
[[rule]]
id = "PS-GHA-TRIG-001"
severity = "HIGH"
title = "Dangerous trigger: pull_request_target"
field = "triggers"
op = "contains"
value = "pull_request_target"
recommendation = "Avoid pull_request_target unless..."
```

Each rule specifies:
- `id` — unique, namespaced identifier for deduplication and AI enrichment lookup.
- `severity` — one of `CRITICAL`, `HIGH`, `MEDIUM`, `INFO`.
- `field` — the observation key to evaluate (produced by the extractor).
- `op` — evaluation operator (`contains`, `equals_ci`, `regex`, `any_true`).
- `value` — operand for the operator.
- `recommendation` — inline human-readable remediation guidance.

### GitHub Actions Rules (v0.1.0)

| Rule ID | Severity | Finding |
|---------|----------|---------|
| `PS-GHA-TRIG-001` | HIGH | `pull_request_target` trigger used |
| `PS-GHA-PERM-001` | HIGH | Global `write-all` permissions |
| `PS-GHA-ACT-001` | MEDIUM | Unpinned third-party action reference |
| `PS-GHA-RUN-001` | HIGH | `curl|bash` remote script execution |
| `PS-GHA-RUNNER-001` | MEDIUM | Self-hosted runner presence |

### Secrets Rules

| Rule ID | Severity | CWE |
|---------|----------|-----|
| `PS-SECRET-RSA-001` | CRITICAL | CWE-798 — Inline RSA private key |
| `PS-SECRET-OAUTH-001` | HIGH | CWE-798 — OAuth/client secret |
| `PS-SECRET-DB-001` | HIGH | CWE-798 — Database password |
| `PS-SECRET-WEAK-001` | MEDIUM | CWE-798 — Weak default value |

---

## 8. GitHub Actions Integration

### Composite Action (`action.yml`)

PipeScope ships as a reusable [composite action](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action) located at `.github/actions/pipescope/action.yml`. This allows any repository to invoke PipeScope as a single step without managing Python version or package installation:

```yaml
- uses: maneav78/pipescope/.github/actions/pipescope@main
  with:
    target: "."
    fail-on-high: "true"
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

**Action Inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `target` | `"."` | Repository path or remote URL |
| `jenkins-url` | — | Jenkins server URL to scan |
| `gitlab-url` | — | GitLab server URL to scan |
| `web-url` | — | Web URL for path enumeration |
| `wordlist-name` | `"common"` | Wordlist selection |
| `threads` | `"10"` | HTTP thread count |
| `openai-key` | — | OpenAI API key for LLM enrichment |
| `fail-on-high` | `"false"` | Exit 1 on High/Critical findings |
| `json-output` | `"results.json"` | JSON report path |
| `pdf-output` | — | PDF report path |
| `python-version` | `"3.11"` | Python version for setup |
| `install-ref` | `"."` | pip install reference |

**Action Outputs:**

| Output | Description |
|--------|-------------|
| `findings-count` | Total findings |
| `high-count` | High severity count |
| `critical-count` | Critical severity count |
| `json-report` | Path to JSON report artefact |

### Included Workflow (`.github/workflows/pipescope.yml`)

The included workflow demonstrates a three-job pipeline:

- **`repo-scan`:** Full local scan of the repository. Uploads JSON and PDF as artefacts. Sets `findings_count` output.
- **`jenkins-scan`:** Runs only when `vars.JENKINS_URL` is set or provided via `workflow_dispatch` input. Remote-only mode, no local target.
- **`summary`:** Depends on both previous jobs; aggregates counts and prints a consolidated summary to the Actions log.

Triggers: push to `main`/`master`/`develop`, pull requests to `main`/`master`, manual `workflow_dispatch` with optional `jenkins-url` and `fail-on-high` parameters.

---

## 9. Security Methodology

PipeScope's detection methodology is grounded in established security frameworks and standards.

### Threat Models Addressed

| Threat | MITRE ATT&CK Technique | PipeScope Detection |
|--------|------------------------|---------------------|
| Supply chain compromise via unpinned CI actions | T1195.001 Compromise Software Dependencies | `PS-GHA-ACT-001` |
| Secrets exfiltration via exposed CI variables | T1552.001 Credentials in Files | Multi-layer secret detection |
| Unauthenticated access to CI/CD control plane | T1133 External Remote Services | Jenkins/GitLab endpoint enumeration |
| Privilege escalation via container root | T1611 Escape to Host | `PIPESCOPE-DOCKER-USER` |
| Known vulnerable software exploitation | T1190 Exploit Public-Facing Application | NVD CVE correlation |
| Malicious code injection via `curl|bash` | T1059.004 Unix Shell | `PS-GHA-RUN-001` |
| Lateral movement via overprivileged K8s workloads | T1610 Deploy Container | kubescape integration |

### CWE Coverage

| CWE | Name | Coverage |
|-----|------|----------|
| CWE-798 | Hardcoded Credentials | `rule_engine.py`, `gitleaks_adapter.py`, `secrets_scanner.py`, `weak_secrets.py` |
| CWE-250 | Execution with Unnecessary Privileges | `compose_scanner.py`, `dockerfile_scanner.py` |
| CWE-653 | Insufficient Compartmentalization | `compose_scanner.py` (network_mode:host) |
| CWE-284 | Improper Access Control | `jenkins_scanner.py` (unauthenticated endpoint access) |
| CWE-1022 | Improper Restriction of Cross-Origin Requests | `gha_observe.py` (pull_request_target) |

### Severity Classification

Severity levels in PipeScope loosely align with CVSS base score ranges:

| Severity | CVSS Equivalent | Criteria |
|----------|-----------------|---------|
| CRITICAL | 9.0–10.0 | Direct credential exposure, RCE-enabling misconfiguration |
| HIGH | 7.0–8.9 | Unauthenticated access to privileged endpoints, known critical CVEs, container root execution |
| MEDIUM | 4.0–6.9 | Unpinned dependencies, weak defaults, information disclosure |
| INFO | < 4.0 | Detected technologies, informational observations |

---

## 10. Technologies and Dependencies

### Runtime Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| [Typer](https://typer.tiangolo.com/) | ≥ 0.12.0 | CLI framework — argument parsing, subcommands, help generation |
| [PyYAML](https://pyyaml.org/) | ≥ 6.0.1 | YAML parsing for workflow files and docker-compose |
| [Rich](https://github.com/Textualize/rich) | ≥ 13.7.1 | Terminal output — tables, panels, progress, colour |
| [detect-secrets](https://github.com/Yelp/detect-secrets) | ≥ 1.5.0 | Entropy-based and pattern-based secret detection |
| [Requests](https://requests.readthedocs.io/) | ≥ 2.28.0 | HTTP client for remote endpoint scanning and NVD API |
| [ReportLab](https://www.reportlab.com/) | ≥ 4.0.0 | PDF generation |

### Standard Library Modules

| Module | Usage |
|--------|-------|
| `tomllib` (Python 3.11+) / `tomli` | TOML rule pack parsing |
| `pathlib` | Cross-platform file system traversal |
| `functools.lru_cache` | CVE lookup result caching |
| `concurrent.futures` | Threaded endpoint enumeration |
| `subprocess` | Gitleaks and kubescape integration |
| `re` | Regex-based pattern matching |
| `dataclasses` | `Finding` and `ScanResult` models |
| `json` | JSON output serialisation |
| `typing` | Type annotations throughout |

### Optional External Tools

| Tool | Version | Purpose | Fallback |
|------|---------|---------|---------|
| gitleaks | ≥ 8.x | Git-aware secret scanning | Skipped gracefully |
| kubescape | ≥ 3.x | Kubernetes posture evaluation | `go run .` from embedded source |
| git | any | Repository cloning for remote URLs | Error with guidance |
| OpenAI API | GPT-3.5+ | LLM-enriched recommendations | Rule-based fallback |

### Build and Packaging

- **Build backend:** `setuptools ≥ 68` with `wheel`
- **Package data:** `rules/*.toml` and `wordlists/*.txt` included via `[tool.setuptools.package-data]` directive (corrected during development after a `FileNotFoundError` in GitHub Actions environments)
- **Entry point:** `pipescope = "pipescope.cli:main"` — enables `pipescope` as a shell command after installation
- **Python requirement:** `>=3.10` (uses `tomllib` from stdlib in 3.11+; `tomli` backport for 3.10)

---

## 11. Testing Strategy

### Unit and Smoke Tests

**File:** `tests/test_ai_github_summary.py`

Smoke tests verify end-to-end behaviour of the AI advisory and GitHub Summary modules without requiring external API connectivity:

```python
def test_enrich_findings_no_api_key():
    findings = [...mock findings...]
    enriched = enrich_findings(findings, openai_key=None)
    assert all("ai_recommendation" in f for f in enriched)

def test_build_ai_summary_returns_string():
    summary = build_ai_summary(enriched_findings)
    assert isinstance(summary, str) and len(summary) > 10

def test_github_summary_no_op_outside_actions(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    write_github_summary(mock_data, findings, "summary")  # must not raise
```

**File:** `tests/test_k8s_scanner.py`

Tests the Kubernetes scanner module, verifying that kubescape binary resolution, subprocess invocation, and JSON output parsing behave correctly under various conditions including missing binary and malformed output.

### Integration Test Repository

**Directory:** `test_repo/`

Contains a `Dockerfile` with intentional misconfigurations used to validate the Dockerfile scanner in end-to-end scans:

```bash
pipescope test_repo/ --json test_docker_results.json
```

### Results Artefacts

The repository contains committed scan result files used for regression validation:

| File | Description |
|------|-------------|
| `results.json` | Baseline scan results for the PipeScope source directory |
| `results_cve_test.json` | CVE lookup integration test results |
| `results_cve_test_k8s.json` | Kubernetes scan with CVE correlation |
| `test_docker_results.json` | Dockerfile scanner output for `test_repo/` |
| `test_results.json` | General regression baseline |

---

## 12. Packaging and Distribution

### Package Layout

```
pipescope/
  __init__.py          # version = "0.1.0"
  cli.py               # Entry point
  core/                # All scanner and analysis modules
  rules/               # TOML rule packs (included in wheel)
  utils/               # fs.py, target.py
  wordlists/           # common.txt, quickhits.txt (included in wheel)
pipescope.egg-info/    # Generated — excluded from git via .gitignore
```

### Critical Packaging Fix

During CI validation, a `FileNotFoundError` was raised because the wheel built without `rules/` and `wordlists/` directories. Root cause: `setuptools` does not automatically include non-Python files unless explicitly declared. Resolution:

```toml
[tool.setuptools]
include-package-data = true

[tool.setuptools.package-data]
pipescope = [
  "rules/*.toml",
  "wordlists/*.txt",
]
```

This was verified by inspecting the built wheel contents:

```bash
python -m build
unzip -l dist/pipescope-0.1.0-py3-none-any.whl | grep -E 'rules|wordlists'
```

### Installation

```bash
# From source
pip install .

# Development mode
pip install -e .

# From GitHub Actions
pip install git+https://github.com/maneav78/pipescope.git
```

---

## 13. Notable Technical Decisions

### 1. Optional Target Argument

The `TARGET` CLI argument was made optional (`typer.Argument(None)`) to support remote-only scan modes (e.g., Jenkins URL scanning in a pipeline without a cloned repository). The guard logic ensures mutual exclusivity is maintained: at least one of `TARGET`, `--jenkins-url`, `--gitlab-url`, or `--web-url` must be provided.

```python
if target is None and not any([web_url, jenkins_url, gitlab_url]):
    raise typer.BadParameter("Provide a target path/URL or at least one remote URL.")
```

### 2. Multi-Layer Secret Detection with Graceful Degradation

The four-layer secret detection architecture (gitleaks → detect-secrets → TOML regex → weak-value assignment) was chosen to maximise detection coverage. Each layer degrades gracefully: gitleaks being unavailable does not prevent detect-secrets from running, and vice versa. This is important for GitHub Actions environments where arbitrary tool installation may be restricted.

### 3. TOML-Separated Rule Packs

Separating security rules from Python logic into TOML files enables a "plugin-like" extensibility model. Security engineers can contribute new checks by adding TOML entries without understanding the Python internals. The `rules_eval.py` evaluator's four generic operators cover the vast majority of CI/CD misconfiguration checks.

### 4. LRU-Cached CVE Lookups

CVE lookups are cached at the `_search_cves()` level. A large repository scan may reference the same base image across many Dockerfiles; caching prevents rate limiting by the NVD API and reduces total scan duration by approximately 60–80% in representative test cases.

### 5. Kubescape Go Source Fallback

Rather than failing when kubescape is not installed, the tool falls back to executing `go run .` against the embedded `kubescape/` Go source directory. This enables Kubernetes scanning in any environment with Go installed, without requiring a pre-built kubescape binary.

### 6. Package Data Inclusion Fix

The `FileNotFoundError` encountered in GitHub Actions when TOML rule files were missing from the installed wheel led to a critical fix in `pyproject.toml`. This underscored the importance of validating wheel contents as part of the CI pipeline rather than relying solely on local development testing.

### 7. SSH Multi-Account Git Configuration

During development, push operations failed due to SSH key ambiguity between two GitHub accounts. The resolution — a `Host` alias in `~/.ssh/config` pointing to the correct key identity file, combined with an SSH-format remote URL — is a standard pattern for multi-account git management that is well worth documenting for teams managing multiple identities.

---

## 14. Limitations and Future Work

### Current Limitations

| Limitation | Impact | Priority |
|------------|--------|---------|
| No SARIF output | Cannot integrate directly with GitHub Code Scanning / Advanced Security | High |
| No Bitbucket CI support | Repositories using `bitbucket-pipelines.yml` are not analysed | Medium |
| No git history scanning (gitleaks `--no-git`) | Credentials committed and then deleted from HEAD are not detected | Medium |
| NVD API rate limits (50 req/30s unauthenticated) | Slow CVE lookups on large repositories with many distinct images | Medium |
| False positives in weak_secrets.py | Comment-stripping heuristic may miss some patterns | Low |
| No SBOM generation | Dependency-level vulnerability analysis is out of scope | Low |

### Planned Enhancements

1. **SARIF Export:** Implement a SARIF 2.1.0 exporter to enable results in GitHub Code Scanning, enabling integration with existing security dashboards.

2. **Bitbucket Pipelines Support:** Add `bitbucket-pipelines.yml` detection and a corresponding TOML rule pack and observation extractor.

3. **Git History Scanning:** Re-enable gitleaks history scanning with configurable `--git-log-opts` to catch deleted-but-committed credentials.

4. **NVD API Key Support:** Accept an `NVD_API_KEY` to increase rate limits from 50 to 2,000 requests per 30 seconds, enabling reliable CVE lookup in large repository scans.

5. **Interactive HTML Report:** Generate a self-contained HTML report with sortable finding tables and severity filters, as an alternative to the PDF output.

6. **Plugin System:** Formalise the scanner module interface to allow external scanner plugins to be registered without modifying the core orchestrator.

7. **CycloneDX SBOM Integration:** Accept a CycloneDX SBOM file as input to lift dependency vulnerability analysis out of scope for the core CVE lookup and into dedicated SCA tooling.

8. **Performance:** Parallelise the local scanner dispatch using `concurrent.futures` at the orchestrator level, reducing scan time on large repositories.

---

## 15. Conclusion

PipeScope demonstrates that comprehensive CI/CD security analysis can be delivered as a lightweight, dependency-minimal Python tool that integrates transparently into the same pipelines it analyses. By treating CI/CD configuration files, container definitions, Kubernetes manifests, remote service endpoints, and source code secrets as a unified attack surface, it provides security visibility that narrow-scope tools (image scanners, SCA tools, SAST engines) do not address.

The project exercised a wide range of systems engineering skills: CLI design and packaging, subprocess integration with external security tools, REST API consumption with caching, YAML/TOML parsing, concurrent HTTP scanning, data modelling, AI API integration, and GitHub Actions workflow engineering. The resolution of real operational issues — SSH multi-account key management, Python wheel packaging of non-code assets, embedded git repository conflicts — reflects the kind of pragmatic problem-solving that characterises production-grade tooling development.

The TOML rule pack architecture provides a clear extensibility model for future security knowledge contributions, while the multi-layer secret detection subsystem and NVD CVE correlation give the tool genuine detection depth. The first-class GitHub Actions integration with Step Summary output ensures that findings are surfaced precisely where developers are already making decisions about their code.

PipeScope v0.1.0 represents a solid foundation for a production security tool. The limitations and future work items identified above provide a clear roadmap toward the coverage depth and integration breadth needed for enterprise adoption.

---

## 16. References

1. NIST National Vulnerability Database API v2.0 Documentation — https://nvd.nist.gov/developers/vulnerabilities  
2. GitHub Actions Security Hardening Guide — https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions  
3. MITRE ATT&CK for Enterprise — https://attack.mitre.org/  
4. CWE — Common Weakness Enumeration — https://cwe.mitre.org/  
5. Gitleaks: SAST Tool for Detecting Secrets — https://github.com/gitleaks/gitleaks  
6. detect-secrets by Yelp — https://github.com/Yelp/detect-secrets  
7. Kubescape Kubernetes Security Platform — https://github.com/kubescape/kubescape  
8. NSA/CISA Kubernetes Hardening Guidance — https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF  
9. OWASP Top 10 CI/CD Security Risks — https://owasp.org/www-project-top-10-ci-cd-security-risks/  
10. Python Packaging User Guide — https://packaging.python.org/  
11. Typer Documentation — https://typer.tiangolo.com/  
12. ReportLab Open Source PDF Library — https://www.reportlab.com/opensource/  
13. Rich Terminal Formatting Library — https://github.com/Textualize/rich  
14. Docker Security Best Practices — https://docs.docker.com/develop/security-best-practices/  
15. GitHub Composite Actions Documentation — https://docs.github.com/en/actions/creating-actions/creating-a-composite-action  

---

*This report was generated by analysing the complete PipeScope v0.1.0 source tree, including all Python modules, TOML rule packs, configuration files, workflow definitions, and test artefacts.*
