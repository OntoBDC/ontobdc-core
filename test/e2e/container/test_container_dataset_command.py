from typing import Dict, List, Tuple
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.term import Identifier
from rdflib.namespace import DCTERMS

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerDatasetCommand:
    @pytest.mark.parametrize("selector", ["id", "path", "cwd"])
    def test_create_dataset_persists_the_title_and_registers_it_in_the_container(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        selector: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        title: str = "Medições de Campo"
        result: CliInvocationResult
        if selector == "cwd":
            result = workspace.runner().run("container", "--create-dataset", title)
        else:
            result = cli_runner.run(
                "container",
                "--container",
                workspace.selector(selector),
                "--create-dataset",
                title,
            )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Dataset Created"
        assert result.json["content"]["dataset_title"] == title
        assert result.json["content"]["dataset_slug"] == "medicoes-de-campo"
        dataset: Path = workspace.container / "medicoes-de-campo"
        assert Path(result.json["content"]["dataset_path"]).resolve() == dataset
        assert (
            Path(result.json["content"]["container_path"]).resolve()
            == workspace.container
        )
        dataset_graph: Graph = Graph()
        dataset_graph.parse(dataset / ".__ontobdc__" / "dataset.ttl", format="turtle")
        subjects: List[Identifier] = list(
            dataset_graph.subjects(DCTERMS.title, Literal(title))
        )
        assert len(subjects) == 1
        container_graph: Graph = Graph()
        container_graph.parse(
            workspace.container / ".__ontobdc__" / "container.ttl", format="turtle"
        )
        assert (subjects[0], DCTERMS.title, Literal(title)) in container_graph
        assert any(
            container_graph.triples((URIRef(workspace.identifier), None, subjects[0]))
        )
        assert any(
            dataset_graph.triples((subjects[0], None, URIRef(workspace.identifier)))
        )

    def test_create_dataset_rejects_a_duplicate_without_overwriting_existing_data(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        arguments: Tuple[str, ...] = (
            "container",
            "--container",
            workspace.identifier,
            "--create-dataset",
            "Measurements",
        )
        created: CliInvocationResult = cli_runner.run(*arguments)
        assert created.exit_code == 0, created.stdout
        (workspace.container / "measurements" / "keep.csv").write_text(
            "value\n42\n", encoding="utf-8"
        )
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(*arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
        assert "already holds a dataset" in result.json["content"]["error"]
        assert workspace.snapshot() == before

    @pytest.mark.parametrize("title", ["", "   ", "!!!"])
    def test_create_dataset_rejects_titles_without_a_usable_slug(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        title: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "container",
            "--container",
            workspace.identifier,
            "--create-dataset",
            title,
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
        assert workspace.snapshot() == before

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--container", "container", "--create-dataset"),
            ("--container", "", "--create-dataset", "Measurements"),
        ],
    )
    def test_create_dataset_requires_a_selector_and_a_title(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_create_dataset_requires_a_container_when_no_selector_is_given(
        self,
        cli_runner: OntobdcCliProcessRunner,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0
        result: CliInvocationResult = cli_runner.run(
            "container", "--create-dataset", "Measurements"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
