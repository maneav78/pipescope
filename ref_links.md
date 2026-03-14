# Final Report

This report summarizes the work done to enhance the PipeScope security enumeration tool.

## Implemented Features

The following features have been added or enhanced to meet the project requirements:

### 1. Web-based Reconnaissance

A new module has been added to perform web-based reconnaissance on a given URL. This module checks for the presence of common sensitive files and directories, such as:

- `.env`
- `.git/config`
- `.DS_Store`
- `config.json`
- `secrets.yml`
- `admin`
- `dashboard`
- `login`
- `api`
- `uploads`

This feature is available via the `--web-url` command-line option.

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

## How to Use the New Features

To use the new features, you can run the `pipescope` command with the following options:

```bash
pipescope <target> --web-url <url> --jenkins-url <url> --pdf <output_path>
```

- `<target>`: The repository to scan (local path or git URL).
- `--web-url <url>`: The URL to run web reconnaissance on.
- `--jenkins-url <url>`: The URL of the Jenkins server to scan.
- `--pdf <output_path>`: The path to write the PDF report to.

## Conclusion

These enhancements significantly improve the capabilities of the PipeScope tool, making it a more comprehensive and effective solution for identifying security risks in CI/CD pipelines and related infrastructure.
