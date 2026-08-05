import subprocess
import sys
from typing import Dict, List

import pytest

from ontobdc.dev.plugin.command.proxy import DevProxyCommand


def test_windows_proxy_preserves_quoted_commit_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_arguments: List[str] = [
        sys.executable,
        "-m",
        "ontobdc_dev",
        "commit",
        "General commit from ontobdc dev",
    ]
    environment: Dict[str, str] = {"PYTHONPATH": "test"}
    captured_arguments: List[str] = []

    def fake_run(
        arguments: List[str],
        env: Dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        assert env == environment
        assert check is False
        captured_arguments.extend(arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    proxy: DevProxyCommand = object.__new__(DevProxyCommand)

    with pytest.raises(SystemExit) as exit_result:
        proxy._exec_dev_cli(
            execution_arguments=execution_arguments,
            environment=environment,
            platform_name="nt",
        )

    assert exit_result.value.code == 0
    assert captured_arguments == execution_arguments
    assert captured_arguments[-1] == "General commit from ontobdc dev"
