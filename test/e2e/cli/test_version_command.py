import re
from typing import Any, Dict, Pattern

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.cli.installed_package_version import InstalledPackageVersionLookup

_SEMANTIC_VERSION_PATTERN: Pattern[str] = re.compile(r"^\d+\.\d+\.\d+$")
_PACKAGE_NAME: str = "ontobdc"


class TestOntobdcVersionCommand:
    """
    E2E coverage for `ontobdc --version --json` / `ontobdc -v --json`,
    cross-checked against the version `pip list` reports as installed for
    the `ontobdc` package itself.
    """

    def test_version_flag_matches_installed_pip_version(self, cli_runner: OntobdcCliProcessRunner) -> None:
        result: CliInvocationResult = cli_runner.run("--version")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Version"
        assert payload["description"] == "Display the package version."
        assert payload["severity"] is None

        reported_version: str = payload["content"]["version"]
        assert _SEMANTIC_VERSION_PATTERN.match(reported_version)

        installed_version: str = InstalledPackageVersionLookup().version_of(_PACKAGE_NAME)
        assert reported_version == installed_version

    def test_short_version_flag_matches_installed_pip_version(self, cli_runner: OntobdcCliProcessRunner) -> None:
        result: CliInvocationResult = cli_runner.run("-v")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Version"

        reported_version: str = payload["content"]["version"]
        assert _SEMANTIC_VERSION_PATTERN.match(reported_version)

        installed_version: str = InstalledPackageVersionLookup().version_of(_PACKAGE_NAME)
        assert reported_version == installed_version

    def test_version_flag_agrees_with_short_version_flag(self, cli_runner: OntobdcCliProcessRunner) -> None:
        long_flag_result: CliInvocationResult = cli_runner.run("--version")
        short_flag_result: CliInvocationResult = cli_runner.run("-v")

        assert long_flag_result.json["content"]["version"] == short_flag_result.json["content"]["version"]
