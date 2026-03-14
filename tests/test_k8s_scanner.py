from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipescope.core.k8s_scanner import scan_kubernetes_manifests
from pipescope.core.models import Severity


KUBESCAPE_OUTPUT = {
    "results": [
        {
            "source": "test.yaml",
            "controls": [
                {
                    "controlID": "C-0001",
                    "name": "Privileged container",
                    "baseScore": "9.0",
                    "status": {"status": "failed"},
                    "description": "Allowing privileged containers can lead to container breakout.",
                    "remediation": "Do not allow privileged containers.",
                }
            ],
        }
    ]
}


@patch("subprocess.run")
@patch("shutil.which")
def test_scan_kubernetes_manifests_with_kubescape(
    mock_which: MagicMock,
    mock_subprocess_run: MagicMock,
):
    mock_which.side_effect = ["/usr/local/bin/kubescape"]

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = json.dumps(KUBESCAPE_OUTPUT)
    mock_process.stderr = ""
    mock_subprocess_run.return_value = mock_process

    findings = scan_kubernetes_manifests(Path("/fake/path"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.id == "C-0001"
    assert finding.title == "Privileged container"
    assert finding.severity == Severity.CRITICAL
    assert finding.description == "Allowing privileged containers can lead to container breakout."
    assert finding.recommendation == "Do not allow privileged containers."
    assert finding.evidence["file"] == "test.yaml"
    mock_subprocess_run.assert_called_once_with(
        ["/usr/local/bin/kubescape", "scan", "/fake/path", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=None,
    )


@patch("subprocess.run")
@patch("shutil.which")
@patch("pathlib.Path.exists")
def test_scan_kubernetes_manifests_uses_cloned_repo_when_binary_missing(
    mock_exists: MagicMock,
    mock_which: MagicMock,
    mock_subprocess_run: MagicMock,
):
    mock_which.side_effect = [None, "/usr/local/bin/go"]
    mock_exists.return_value = True

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = '{"results": []}'
    mock_process.stderr = ""
    mock_subprocess_run.return_value = mock_process

    findings = scan_kubernetes_manifests(Path("/fake/path"))

    assert findings == []
    called_args, called_kwargs = mock_subprocess_run.call_args
    assert called_args[0][:3] == ["go", "run", "."]
    assert called_args[0][3:] == ["scan", "/fake/path", "--format", "json"]
    assert called_kwargs["capture_output"] is True
    assert called_kwargs["text"] is True
    assert called_kwargs["check"] is False
    assert called_kwargs["cwd"] is not None


@patch("subprocess.run")
@patch("shutil.which")
def test_scan_kubernetes_manifests_parses_kubescape_v2_result_shape(
    mock_which: MagicMock,
    mock_subprocess_run: MagicMock,
):
    mock_which.side_effect = ["/usr/local/bin/kubescape"]

    v2_output = {
        "results": [
            {
                "resourceID": "path=123/api=v1//Pod/test",
                "controls": [
                    {
                        "controlID": "C-0057",
                        "name": "Privileged container",
                        "severity": "High",
                        "status": {"status": "failed"},
                        "description": "Container is privileged.",
                        "remediation": "Set privileged to false.",
                    }
                ],
            }
        ]
    }

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = json.dumps(v2_output)
    mock_process.stderr = ""
    mock_subprocess_run.return_value = mock_process

    findings = scan_kubernetes_manifests(Path("/fake/path"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.id == "C-0057"
    assert finding.severity == Severity.HIGH
    assert finding.evidence["file"] == "path=123/api=v1//Pod/test"
