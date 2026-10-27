"""Installed CLI routing for `container --entity <type> --dataset`."""

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace

DAY: str = "http://datacenter.app.br/ontology/domain/calendar/taxonomy/type.ttl#Day"


class TestOntobdcContainerEntityDatasetCommand:
    @pytest.mark.parametrize(
        "args",
        [
            ("--dataset",),
            ("--entity", DAY, "--dataset", "extra"),
            ("--entity", "--dataset"),
        ],
    )
    def test_invalid_route_creates_nothing(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("container", *args)

        assert result.exit_code != 0, result.stdout
        assert workspace.snapshot() == before

    def test_creates_the_dataset_once_and_it_is_listed_empty(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        runner: OntobdcCliProcessRunner = workspace.runner()

        first: Any = json.loads(
            runner.run("container", "--container", workspace.identifier, "--entity", DAY, "--dataset").stdout
        )
        again: Any = json.loads(
            runner.run("container", "--container", workspace.identifier, "--entity", DAY, "--dataset").stdout
        )
        listed: Any = json.loads(
            runner.run("container", "--container", workspace.identifier, "--entity", DAY, "--list").stdout
        )

        assert first["content"]["created"] is True
        assert again["content"]["created"] is False
        assert [dataset["entities"] for dataset in listed["content"]["datasets"]] == [[]]
