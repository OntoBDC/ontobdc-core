from typing import List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcRunTagCommand:
    @pytest.mark.parametrize("separator", [" ", ",", ";", "|", "/"])
    def test_tag_parses_supported_separators_and_reports_unavailable_execution(
        self,
        cli_runner: OntobdcCliProcessRunner,
        separator: str,
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "run", "--tag", separator.join(["storage", "health"])
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Tag Run Not Available"
        assert (
            result.json["content"]["error"] == "Tag capability selection not restored."
        )
        assert result.json["content"]["tags"] == ["storage", "health"]

    def test_tag_preserves_order_and_removes_duplicate_tags(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "run", "--tag", " health,storage;health | dataset/storage "
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Tag Run Not Available"
        tags: List[str] = result.json["content"]["tags"]
        assert tags == ["health", "storage", "dataset"]

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--tag",),
            ("--tag", ""),
            ("--tag", "   "),
            ("--tag", ",;|/"),
            ("--tag", "health", "storage"),
        ],
    )
    def test_tag_rejects_missing_empty_or_extra_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
