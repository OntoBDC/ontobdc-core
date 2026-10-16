"""Installed CLI routing for `container --remote <url>` (remote container download)."""

from pathlib import Path
from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContainerRemoteCommand:
    def test_container_help_lists_remote_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--remote" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--remote",),
            ("--remote", ""),
            ("--remote", "   "),
            ("--remote", "http://example.com/file.obdc", "extra"),
        ],
    )
    def test_remote_rejects_routing_invalid_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--remote", "not-a-url"),
            ("--remote", "ftp://example.com/file.obdc"),
        ],
    )
    def test_remote_rejects_invalid_urls_without_downloading(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid remote container URL" in result.stdout

    def test_remote_valid_url_reaches_the_download_stage(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        """
        A syntactically valid http URL passes the check stage and reaches the
        download machine, which fails because nothing is served locally.
        """
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "container", "--remote", "http://127.0.0.1:1/nonexistent.obdc"
        )

        assert result.exit_code != 0
        assert "RemoteFileDownloadError" in result.stdout + result.stderr
        assert not list(tmp_path.rglob("*.obdc"))
