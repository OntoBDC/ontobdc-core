"""Installed CLI routing for `run --fsm <yaml> [--container <id>] [--<param> <value>]`."""

from pathlib import Path
from typing import ClassVar, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcRunFsmCommand:
    """
    The `run --fsm` command runs a finite state machine from the YAML of its
    statechart. The container_refresh machine is used as a safe, real FSM:
    it runs against a container and only updates its own Data Package and
    RO-Crate metadata, leaving user files untouched.
    """

    REFRESH_FSM: ClassVar[str] = (
        "ontobdc/container/plugin/machine/container_refresh/"
        "standard_container_refresh.yaml"
    )

    def test_run_help_lists_fsm_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--fsm" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--fsm",),
            ("--fsm", REFRESH_FSM, "value"),
            ("--fsm", REFRESH_FSM, "--capability", "x"),
            ("--fsm", REFRESH_FSM, "--fsm", REFRESH_FSM),
            ("--fsm", REFRESH_FSM, "----bad", "value"),
            ("--fsm", REFRESH_FSM, "--container"),
            ("--fsm", REFRESH_FSM, "--param"),
            ("--fsm", REFRESH_FSM, "--empty", ""),
            ("--fsm", REFRESH_FSM, "--empty", "   "),
        ],
    )
    def test_invalid_fsm_route_fails(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    def test_nonexistent_fsm_yaml_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "run", "--fsm", "/nonexistent/machine.yaml"
        )
        assert result.exit_code != 0, result.stdout
        assert "not a statechart file" in result.stdout

    def test_fsm_runs_against_container_resolved_from_cwd(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run(
            "run", "--fsm", self.REFRESH_FSM
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert "ContainerRefreshStateTransitionHandler" in result.json["description"]

    def test_fsm_runs_with_explicit_container_selector(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--fsm",
            self.REFRESH_FSM,
            "--container",
            workspace.selector("id"),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert "ContainerRefreshStateTransitionHandler" in result.json["description"]

    def test_fsm_accepts_container_flag_before_fsm_flag(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "run",
            "--container",
            workspace.selector("id"),
            "--fsm",
            self.REFRESH_FSM,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert "ContainerRefreshStateTransitionHandler" in result.json["description"]
