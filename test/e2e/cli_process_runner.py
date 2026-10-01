import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class CliInvocationResult:
    """
    Outcome of a single real `ontobdc` subprocess invocation.
    """
    arguments: List[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> Dict[str, Any]:
        """
        Parse stdout as JSON. Warnings and log noise are written to stderr,
        so stdout is expected to be exactly one JSON document.
        """
        return json.loads(self.stdout)


class OntobdcCliProcessRunner:
    """
    Invokes the `ontobdc` executable installed in the *current* virtualenv
    (the one running this test suite -- resolved from `sys.executable`,
    never whatever `ontobdc` happens to resolve to on PATH) as a real
    subprocess, isolated inside a project root with no `.__ontobdc__`
    marker of its own so no test run can resolve to, or pollute, the
    developer's shared `.__ontobdc__/context.ttl`.

    Resolving via PATH is deliberately avoided: on a machine with more than
    one `ontobdc` install (e.g. a stray global/Homebrew Python alongside
    the project's own venv), PATH can silently pick the wrong interpreter
    -- one missing dependencies (like ``frictionless``) that the venv has,
    making entire commands fail to even load.

    `ONTOBDC_PROJECT_ROOT` is deliberately left unset rather than pointed at
    the isolated directory: `ConfigDataAdapter` crashes with an
    `AttributeError` when that override names a directory without its own
    `.__ontobdc__/config.yaml`, since it never falls back to
    `UnsetProjectRootConfigDataAdapter` in that case.
    """
    _TIMEOUT_SECONDS: int = 30

    def __init__(self, isolated_project_root: Path) -> None:
        self._isolated_project_root: Path = isolated_project_root

    def run(self, *arguments: str) -> CliInvocationResult:
        """
        Execute `ontobdc <arguments> --json` and capture the result.
        """
        full_arguments: List[str] = [str(self._executable_path()), *arguments, "--json"]
        environment: Dict[str, str] = dict(os.environ)
        environment.pop("ONTOBDC_PROJECT_ROOT", None)

        completed_process: "subprocess.CompletedProcess[str]" = subprocess.run(
            full_arguments,
            cwd=self._isolated_project_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=self._TIMEOUT_SECONDS,
        )

        return CliInvocationResult(
            arguments=list(arguments),
            exit_code=completed_process.returncode,
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
        )

    def _executable_path(self) -> Path:
        """
        The `ontobdc` script installed next to the running interpreter --
        `sys.executable`'s own venv `bin/` directory, never PATH.
        """
        executable_path: Path = Path(sys.executable).parent / "ontobdc"
        if not executable_path.is_file():
            raise FileNotFoundError(
                f"No 'ontobdc' executable found next to the running interpreter "
                f"at '{executable_path}'. Is ontobdc installed in this venv?"
            )
        return executable_path
