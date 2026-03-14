# PipeScope — GitHub Actions Integration Guide

This guide walks you through publishing PipeScope to GitHub and running the security scan as a GitHub Actions workflow, from zero to seeing live results in the Actions UI.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Push the repository to GitHub](#2-push-the-repository-to-github)
3. [Understand the file structure](#3-understand-the-file-structure)
4. [Configure repository secrets and variables](#4-configure-repository-secrets-and-variables)
5. [Trigger the workflow — three ways](#5-trigger-the-workflow--three-ways)
6. [View the results](#6-view-the-results)
7. [Use PipeScope in another repository](#7-use-pipescope-in-another-repository)
8. [All action inputs and outputs reference](#8-all-action-inputs-and-outputs-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| GitHub account | Free tier is enough |
| Git installed locally | `git --version` to check |
| Python ≥ 3.11 (local testing only) | Not needed on the GitHub runner |
| (Optional) OpenAI API key | Enables LLM-enhanced recommendations; without it, rule-based AI is used for free |

---

## 2. Push the repository to GitHub

### 2a. Create a new repository on GitHub

1. Go to **github.com → New repository**.
2. Name it (e.g. `pipescope`), set visibility (**Public** or **Private**).
3. **Do NOT** initialise with a README — you already have local files.
4. Click **Create repository**.

### 2b. Push your local code

Run the following from the `PipeScope` project directory:

```bash
cd /Users/mavoyan/Desktop/PipeScope

# Initialise git if not already done
git init
git add .
git commit -m "feat: initial PipeScope with GitHub Actions support"

# Connect to your new GitHub repo (replace with your URL)
git remote add origin https://github.com/<YOUR_USERNAME>/pipescope.git

# Push
git branch -M main
git push -u origin main
```

> After the push, GitHub will automatically detect `.github/workflows/pipescope.yml`
> and queue the first workflow run.

---

## 3. Understand the file structure

These are the key files that make the action work:

```
.github/
├── actions/
│   └── pipescope/
│       └── action.yml          ← reusable composite action (the engine)
└── workflows/
    └── pipescope.yml           ← workflow that calls the action
```

| File | Purpose |
|---|---|
| `.github/actions/pipescope/action.yml` | Defines the composite action: installs Python + PipeScope, builds the command, runs the scan, uploads artifacts |
| `.github/workflows/pipescope.yml` | Orchestrates jobs: `repo-scan`, `jenkins-scan`, `summary` |

---

## 4. Configure repository secrets and variables

### Secrets (sensitive — never logged)

Go to your repo → **Settings → Secrets and variables → Actions → Secrets**

| Secret name | Value | Required |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key starting with `sk-…` | No — rule-based AI is used if absent |

### Variables (non-sensitive — visible in logs)

Go to your repo → **Settings → Secrets and variables → Actions → Variables**

| Variable name | Example value | Purpose |
|---|---|---|
| `JENKINS_URL` | `http://jenkins.example.com:8080` | Makes the `jenkins-scan` job run automatically on every push |

> **Tip:** If you don't set `JENKINS_URL`, the Jenkins scanner job is simply skipped —
> it will not cause errors.

---

## 5. Trigger the workflow — three ways

### Option A — Automatic (push / pull request)

The workflow runs automatically on every push to `main`, `master`, or `develop`,
and on every pull request targeting `main` or `master`. No manual action needed.

### Option B — Manual trigger with Jenkins URL

1. Go to your repo → **Actions** tab.
2. Select **PipeScope Security Scan** in the left sidebar.
3. Click **Run workflow** (top-right of the run list).
4. Fill in the inputs:

   | Input | Example | Notes |
   |---|---|---|
   | Jenkins server URL | `http://localhost:8080` | Leave empty to skip Jenkins scan |
   | Fail build on High/Critical findings | `true` | Set `false` to allow the workflow to pass regardless |

5. Click **Run workflow**.

### Option C — Trigger via GitHub CLI (from terminal)

```bash
# Repo scan only
gh workflow run pipescope.yml --repo <YOUR_USERNAME>/pipescope

# Repo scan + Jenkins scan
gh workflow run pipescope.yml \
  --repo <YOUR_USERNAME>/pipescope \
  -f jenkins-url=http://jenkins.example.com:8080 \
  -f fail-on-high=true
```

---

## 6. View the results

### 6a. Job Summary (main panel — richest view)

1. Go to **Actions** tab in your GitHub repo.
2. Click the latest **PipeScope Security Scan** run.
3. Click the **Repository Scan** job.
4. Scroll to the bottom of the job log — click **Summary** in the left sidebar or look for the expandable summary panel.

You will see:

```
🔍 PipeScope Security Assessment
─────────────────────────────────────────────
📋 Scan Information
  Tool       PipeScope 0.1.0
  Target     .
  Branch     main
  Triggered  @your-username

🧠 AI Executive Summary
  > 5 High-severity issues should be addressed within 24-48 hours; ...

📊 Severity Breakdown
  🔴 Critical  2   10.0%   ████░░░░░░░░░░░░░░░░
  🟠 High      5   25.0%   █████░░░░░░░░░░░░░░░
  🟡 Medium    8   40.0%   ████████░░░░░░░░░░░░
  🔵 Info      5   25.0%   █████░░░░░░░░░░░░░░░

🔎 Detailed Findings with AI Recommendations
  #  Sev       ID                         Title                   AI Recommendation
  1  🔴 Crit   PIPESCOPE-JENKINS-CVE-001  Potential Jenkins CVE   Update Jenkins to the latest LTS release...
  ...
```

### 6b. Artifacts (JSON + PDF reports)

1. On the run page, scroll to the bottom.
2. Under **Artifacts**, download:
   - `pipescope-json-report` → `pipescope-repo-results.json`
   - `pipescope-pdf-report` → `pipescope-repo-report.pdf`
   - `pipescope-jenkins-results.json` (if Jenkins scan ran)

### 6c. Step outputs (for downstream jobs)

If you use PipeScope as a step inside a larger workflow, you can read:

```yaml
- name: Check findings
  run: |
    echo "Total: ${{ steps.scan.outputs.findings-count }}"
    echo "High:  ${{ steps.scan.outputs.high-count }}"
```

### 6d. Build status badge

Add this to your `README.md`:

```markdown
![PipeScope](https://github.com/<YOUR_USERNAME>/pipescope/actions/workflows/pipescope.yml/badge.svg)
```

---

## 7. Use PipeScope in another repository

If you want to run PipeScope on a **different** project's repo (not the PipeScope repo itself), copy the workflow below into that project's `.github/workflows/pipescope.yml`:

```yaml
name: PipeScope Security Scan

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run PipeScope
        uses: <YOUR_USERNAME>/pipescope/.github/actions/pipescope@main
        with:
          target: '.'
          json-output: pipescope-results.json
          pdf-output:  pipescope-report.pdf
          openai-key:  ${{ secrets.OPENAI_API_KEY }}   # optional
          fail-on-high: 'true'
```

> Replace `<YOUR_USERNAME>/pipescope` with the actual path to your PipeScope repo.
> The `@main` suffix pins to the main branch — you can also use a tag like `@v1.0.0`.

### Jenkins-only scan in another repo

```yaml
      - name: Scan Jenkins
        uses: <YOUR_USERNAME>/pipescope/.github/actions/pipescope@main
        with:
          jenkins-url: ${{ vars.JENKINS_URL }}
          openai-key:  ${{ secrets.OPENAI_API_KEY }}
          fail-on-high: 'false'
```

---

## 8. All action inputs and outputs reference

### Inputs

| Input | Default | Description |
|---|---|---|
| `target` | _(empty)_ | Local path `.` or git URL to scan. Omit for URL-only mode. |
| `jenkins-url` | _(empty)_ | Jenkins server URL |
| `gitlab-url` | _(empty)_ | GitLab server URL |
| `web-url` | _(empty)_ | Base URL for web path recon |
| `wordlist-name` | `common` | Built-in wordlist (`common` or `quickhits`) |
| `threads` | `10` | Parallel threads for web recon |
| `openai-key` | _(empty)_ | OpenAI API key (maps to `OPENAI_API_KEY`) |
| `fail-on-high` | `true` | Exit code 1 on High/Critical findings |
| `json-output` | `pipescope-results.json` | Path for JSON report |
| `pdf-output` | _(empty)_ | Path for PDF report (skipped if empty) |
| `python-version` | `3.11` | Python version on the runner |
| `install-ref` | `.` | pip install specifier (`.` = current repo) |

### Outputs

| Output | Description |
|---|---|
| `findings-count` | Total number of findings |
| `high-count` | Number of High-severity findings |
| `critical-count` | Number of Critical-severity findings |
| `json-report` | Path to the JSON report file |

---

## 9. Troubleshooting

### Workflow doesn't appear in the Actions tab

The workflow file must be on the **default branch** (usually `main`).  
Push the `.github/` folder to `main` and refresh the Actions tab.

### `jenkins-scan` job is skipped

This is expected unless you set the `JENKINS_URL` repository variable **or** provide it manually via `workflow_dispatch`. Skipped ≠ failed.

### `uses: ./.github/actions/pipescope` fails with "Can't find action"

This error means the `action.yml` file isn't committed and pushed yet.  
Run:

```bash
git add .github/actions/pipescope/action.yml
git commit -m "feat: add composite action"
git push
```

### OpenAI key not working

- Confirm the secret name is exactly `OPENAI_API_KEY` (case-sensitive).
- Check the key starts with `sk-` and hasn't expired.
- Without the key, PipeScope still runs with rule-based AI — it doesn't error.

### Build fails on High findings but you want it to pass

Set `fail-on-high: 'false'` in the workflow `with:` block, or pass `--no-fail-on-high` if running locally.

### Artifacts not appearing

Artifacts are only uploaded when the scan step completes (even on failure, because of `if: always()`). If the install step itself fails, no artifact is produced. Check the **Install PipeScope** step logs for pip errors.
