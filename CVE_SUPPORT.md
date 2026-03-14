**What I changed**

- **Models:** Added `cves: List[str]` to the finding model and included it in the JSON output. See [pipescope/core/models.py](pipescope/core/models.py).
- **Rule engine:** `scan_with_rules()` now forwards an optional `cves` list from rule TOML entries into `Finding.cves`. See [pipescope/core/rule_engine.py](pipescope/core/rule_engine.py).

**Why**

We want findings to be able to reference known CVEs so that users can track specific vulnerability identifiers alongside heuristic findings.

**How to test (quick manual test)**

1. Activate your virtualenv if not already active.

```bash
source .venv/bin/activate
```

2. (Optional) Install requirements and the package in editable mode to enable the CLI.

```bash
pip install -r requirements.txt
pip install -e .
```

3. Edit a rule to include CVEs. Modify the rule in [pipescope/rules/secrets.toml](pipescope/rules/secrets.toml) (example added to the file):

```toml
[[rule]]
id = "PS-SECRET-RSA-001"
severity = "CRITICAL"
cwe = "CWE-798"
cves = ["CVE-2024-1234", "CVE-2023-9876"]
description = "Hardcoded RSA private key"
regex = "MIIC[A-Za-z0-9+/=]{200,}"
```

4. Run against a repo that contains a matching file (for example `repos/gamerpolls.com`):

```bash
pipescope ./repos/gamerpolls.com --json results_test.json
```

5. Open `results_test.json` and confirm each matching finding contains a `cves` array with the CVE IDs you added. Example excerpt:

```json
{
  "id": "PS-SECRET-RSA-001",
  "title": "Hardcoded RSA private key",
  "severity": "Critical",
  "description": "Matched rule PS-SECRET-RSA-001 (CWE-798)",
  "evidence": { "file": "app/config.py" },
  "recommendation": "Remove hardcoded secret and rotate affected credentials.",
  "cves": ["CVE-2024-1234", "CVE-2023-9876"]
}
```


**Automated quick-check script (optional)**

Create a quick script to run inside the repo (example `scripts/check_cve_output.py`):

```python
from pipescope.core.scan import run_scan
import json

res = run_scan("repos/gamerpolls.com", version="dev")
print(json.dumps(res.to_dict(), indent=2))
```

Run it with:

```bash
python scripts/check_cve_output.py > out.json
# then inspect out.json for the `cves` fields
```

---

**Dynamic CVE lookup in Dockerfile scans**

The scanner now reaches out to the NVD REST API when processing `FROM` lines in
Dockerfiles.  For each base image it will perform a keyword search and attach any
CVE identifiers it finds to a separate finding (`PS-DOCKER-CVE-001`).

**Current implementation note:** The system now relies exclusively on live NVD API calls
and no longer includes any hardcoded mock CVE data. The infrastructure still caches
results to reduce repeated network activity.

To see this in action:

1. Start with the virtualenv active and the package installed (see earlier
   instructions).
2. Make sure the machine has network access to `services.nvd.nist.gov`.
3. Run the scan against a repository containing a Dockerfile, e.g.:  
   ```bash
   pipescope ./repos/gamerpolls.com --json results_test.json
   ```
4. Open `results_test.json` and look for entries with `id` "PS-DOCKER-CVE-001".
   They will include a `cves` array showing whatever the NVD search returned.

Because the lookup is cached, scanning multiple Dockerfiles or running the
scanner repeatedly will not result in repeated network calls for the same image.

This dynamic behaviour means new vulnerabilities are automatically surfaced
without having to manually encode them in rules.

**Next steps / suggestions**

- Add CVE mapping for base OS images and common packages in `dockerfile_scanner.py` (map image names/tags to known CVEs) — I can help build a small mapping table.
- Add unit tests to assert `cves` serializes correctly and `rule_engine` populates `cves` when provided.

If you want, I can add the quick script (`scripts/check_cve_output.py`) and/or add a basic unit test now. Which do you prefer next?
