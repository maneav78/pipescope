# Final Report

This report summarizes the work done to enhance the PipeScope security enumeration tool.

## Implemented Features

The following features have been added or enhanced to meet the project requirements:

### 1. Advanced Web-based Reconnaissance

The web-based reconnaissance module has been significantly enhanced to support advanced discovery techniques, similar to tools like `dirb` and `gobuster`. The module now performs directory and file brute-forcing using a wordlist.

- **Concurrent Scanning:** The scanner uses multiple threads to perform the scan quickly.
- **Multiple Wordlists:** The tool now includes multiple wordlists for web reconnaissance. A smaller, faster `common.txt` and a more comprehensive `quickhits.txt` from the SecLists project.
- **Selectable Wordlists:** Users can now choose which wordlist to use for the scan using the `--wordlist-name` option. The default is `common.txt`, but `quickhits.txt` can be used for a more thorough scan.
- **Custom Wordlists:** Users can specify their own wordlist for a more thorough scan.

This feature is available via the `--web-url` command-line option, and can be customized with `--wordlist` and `--threads`.

### 2. Infrastructure Enumeration (Jenkins)

A new module has been added to scan for common Jenkins endpoints. This helps identify potentially exposed Jenkins servers. The scanner checks for the following paths:

- `script`
- `cli`
- `login`
- `asynchPeople/`
- `computer/(master)/`
- `jnlpJars/jenkins-cli.jar`
- `userContent/`
- `whoAmI/`

This feature is available via the `--jenkins-url` command-line option.

### 3. PDF Report Generation

The tool can now generate a PDF report summarizing the scan findings. The report includes a title, a summary, and a table of findings with severity, ID, title, and evidence.

This feature is available via the `--pdf` command-line option.

### 4. CI/CD Friendliness

The tool has been made more CI/CD friendly with the following enhancements:

- **Findings Summary:** A summary table of findings by severity is now printed to the console after each scan.
- **Exit Codes:** The tool will now exit with a non-zero status code if any findings with `HIGH` or `CRITICAL` severity are detected. This allows CI/CD pipelines to fail automatically when significant security risks are found.

### 5. GitHub Action

A GitHub Action has been created to automate the process of running PipeScope scans on a repository. This allows for continuous security scanning on every push or pull request to the `main` branch.

The action is defined in `.github/workflows/pipescope.yml` and can be customized to fit different needs. It currently performs the following steps:
1.  Checks out the repository.
2.  Sets up Python.
3.  Installs the `pipescope` tool and its dependencies.
4.  Runs a scan on the repository.

This makes it easy to integrate PipeScope into any GitHub-based development workflow.

## How to Use the New Features

To use the new features, you can run the `pipescope` command with the following options:

```bash
pipescope <target> --web-url <url> --wordlist <path_to_wordlist> --wordlist-name <name> --threads 20 --jenkins-url <url> --pdf <output_path>
```

- `<target>`: The repository to scan (local path or git URL).
- `--web-url <url>`: The URL to run web reconnaissance on.
- `--wordlist <path_to_wordlist>`: Path to a custom wordlist for web recon.
- `--wordlist-name <name>`: Name of the wordlist to use for web recon (e.g., common, quickhits).
- `--threads <int>`: Number of concurrent threads for web recon.
- `--jenkins-url <url>`: The URL of the Jenkins server to scan.
- `--pdf <output_path>`: The path to write the PDF report to.

## Missing Features and Future Work

While the tool is now more capable, there are still some features from the initial project requirements that are not yet fully implemented:

- **CVE Scanning for Infrastructure:** The current infrastructure scanner only checks for the presence of common endpoints. A major next step is to add version detection and CVE lookup for services like Jenkins and GitLab. This would allow the tool to identify specific vulnerabilities based on the software version in use.

- **CI/CD Plugin:** The tool is CI/CD friendly, but it is not yet a full-fledged CI/CD plugin. Creating dedicated plugins for popular platforms (e.g., a GitHub Action, a GitLab CI template) would make it much easier to integrate PipeScope into development workflows.

- **Broader Infrastructure Scanning:** The current infrastructure scanning is focused on Jenkins. Expanding this to other CI/CD platforms like GitLab, and other related infrastructure components, would make the tool more versatile.

## Conclusion

These enhancements significantly improve the capabilities of the PipeScope tool, making it a more comprehensive and effective solution for identifying security risks in CI/CD pipelines and related infrastructure. The next steps should focus on deepening the infrastructure analysis capabilities.
