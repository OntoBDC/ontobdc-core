"""Installed CLI routing for `context --pdf-to-graph <path> [--output-path <dir>]`."""

from pathlib import Path
from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContextPdfToGraphCommand:
    def test_context_help_lists_pdf_to_graph_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--pdf-to-graph" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--pdf-to-graph",),
            ("--pdf-to-graph", "file.pdf", "--output-path"),
            ("--output-path", "/tmp", "--pdf-to-graph", "file.pdf"),
            ("--pdf-to-graph", "file.pdf", "--output-path", "/tmp", "--extra"),
            ("--pdf-to-graph", "file.pdf", "--unknown", "x"),
        ],
    )
    def test_invalid_pdf_to_graph_route_fails(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    def test_nonexistent_pdf_path_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "context", "--pdf-to-graph", "/nonexistent/file.pdf"
        )
        assert result.exit_code != 0, result.stdout
        assert "Invalid PDF path" in result.stdout

    def test_non_pdf_file_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        text_file: Path = tmp_path / "document.txt"
        text_file.write_text("not a pdf\n")

        result: CliInvocationResult = cli_runner.run(
            "context", "--pdf-to-graph", str(text_file)
        )

        assert result.exit_code != 0, result.stdout
        assert "supports only PDF files" in result.stdout

    def test_nonexistent_output_directory_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        pdf_file: Path = tmp_path / "document.pdf"
        pdf_file.write_text("not a real pdf\n")
        missing_dir: Path = tmp_path / "missing-parent" / "subdir"

        result: CliInvocationResult = cli_runner.run(
            "context",
            "--pdf-to-graph",
            str(pdf_file),
            "--output-path",
            str(missing_dir),
        )

        assert result.exit_code != 0, result.stdout
        assert "Invalid output directory" in result.stdout

    def test_valid_pdf_route_reaches_the_pipeline(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        """
        A syntactically valid PDF path passes the check stage and reaches the
        PDF-to-graph FSM. The pipeline fails because the file is not a real
        PDF, but routing and validation must succeed.
        """
        pdf_file: Path = tmp_path / "document.pdf"
        pdf_file.write_text("not a real pdf\n")

        result: CliInvocationResult = cli_runner.run(
            "context", "--pdf-to-graph", str(pdf_file)
        )

        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" not in result.stdout
        assert "CodeEvaluationError" in result.stdout

    def test_valid_pdf_route_with_output_directory_reaches_the_pipeline(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        pdf_file: Path = tmp_path / "document.pdf"
        pdf_file.write_text("not a real pdf\n")

        result: CliInvocationResult = cli_runner.run(
            "context",
            "--pdf-to-graph",
            str(pdf_file),
            "--output-path",
            str(tmp_path),
        )

        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" not in result.stdout
        assert "CodeEvaluationError" in result.stdout
