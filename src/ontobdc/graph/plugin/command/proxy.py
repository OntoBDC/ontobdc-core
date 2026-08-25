import os
import subprocess
import sys
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from pathlib import Path
from typing import Dict, Iterable, List, NoReturn, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class DevProxyCommand(CliCommandPort):
    """Locate and execute the external brasidatacenter package."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="graph",
        logical_component="graph",
        description="Delegate graph commands to the brasidatacenter workspace CLI.",
        arguments=[
            {
                "accepts": ["graph"],
                "description": "Delegate graph commands to the brasidatacenter CLI.",
                "usage": "ontobdc graph <command> [flags/parameters]",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) > 0 and args[0] == "graph"

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return True

    def run(self) -> CommandResponse:
        dev_src_path: Optional[Path] = self._resolve_dev_src_path()
        if dev_src_path is None:
            current_directory: Path = Path.cwd().resolve()
            raise ModuleNotFoundError(
                "Unable to locate the brasidatacenter package. Install "
                "brasidatacenter in the active Python environment or place its "
                "checkout below a nearby workspace root. Current working "
                f"directory: {current_directory}"
            )

        forwarded_args: List[str] = list(self._request.command_args)
        if not forwarded_args:
            forwarded_args = ["--help"]

        environment: Dict[str, str] = dict(os.environ)
        python_path_entries: List[str] = self._python_path_entries(
            environment
        )
        dev_src_path_text: str = str(dev_src_path)
        if dev_src_path_text not in python_path_entries:
            python_path_entries.insert(0, dev_src_path_text)
        environment["PYTHONPATH"] = os.pathsep.join(python_path_entries)

        execution_arguments: List[str] = [
            sys.executable,
            "-m",
            "brasidatacenter",
            *forwarded_args,
        ]

        self._exec_dev_cli(
            execution_arguments=execution_arguments,
            environment=environment,
        )

    def _resolve_dev_src_path(self) -> Optional[Path]:
        installed_src_path: Optional[Path] = (
            self._resolve_installed_dev_src_path()
        )
        if installed_src_path is not None:
            return installed_src_path

        return self._resolve_checkout_dev_src_path()

    def _resolve_installed_dev_src_path(self) -> Optional[Path]:
        try:
            module_spec: Optional[ModuleSpec] = find_spec("brasidatacenter")
        except (AttributeError, ImportError, ValueError):
            return None

        if module_spec is None:
            return None

        package_locations: Iterable[str] = (
            module_spec.submodule_search_locations or []
        )
        package_location: str
        for package_location in package_locations:
            package_path: Path = Path(package_location).expanduser().resolve()
            if self._is_valid_dev_package_path(package_path):
                return package_path.parent

        if module_spec.origin is None:
            return None

        origin_package_path: Path = (
            Path(module_spec.origin).expanduser().resolve().parent
        )
        if self._is_valid_dev_package_path(origin_package_path):
            return origin_package_path.parent

        return None

    def _resolve_checkout_dev_src_path(self) -> Optional[Path]:
        search_roots: List[Path] = []
        base_path: Path
        for base_path in (
            Path.cwd().resolve(),
            Path(__file__).resolve().parent,
        ):
            candidate_root: Path
            for candidate_root in (base_path, *base_path.parents):
                if candidate_root in search_roots:
                    continue
                search_roots.append(candidate_root)

        search_root: Path
        for search_root in search_roots:
            dev_root_candidates: List[Path] = [
                search_root,
                search_root / "brasidatacenter",
            ]
            dev_root: Path
            for dev_root in dev_root_candidates:
                dev_src_path: Path = dev_root / "src"
                if self._is_valid_dev_src_path(dev_src_path):
                    return dev_src_path.resolve()

        return None

    def _is_valid_dev_package_path(self, package_path: Path) -> bool:
        return (
            package_path.is_dir()
            and package_path.name == "brasidatacenter"
            and (package_path / "__main__.py").is_file()
        )

    def _is_valid_dev_src_path(self, dev_src_path: Path) -> bool:
        return self._is_valid_dev_package_path(
            dev_src_path / "brasidatacenter"
        )

    def _python_path_entries(
        self,
        environment: Dict[str, str],
    ) -> List[str]:
        python_path_entries: List[str] = []
        current_python_path: str = str(
            environment.get("PYTHONPATH") or ""
        )
        python_path_entry: str
        for python_path_entry in current_python_path.split(os.pathsep):
            normalized_entry: str = python_path_entry.strip()
            if normalized_entry:
                python_path_entries.append(normalized_entry)

        return python_path_entries

    def _exec_dev_cli(
        self,
        execution_arguments: List[str],
        environment: Dict[str, str],
        platform_name: Optional[str] = None,
    ) -> NoReturn:
        resolved_platform_name: str = (
            os.name if platform_name is None else platform_name
        )
        if resolved_platform_name == "nt":
            completed_process: subprocess.CompletedProcess[bytes] = (
                subprocess.run(
                    execution_arguments,
                    env=environment,
                    check=False,
                )
            )
            raise SystemExit(completed_process.returncode)

        os.execvpe(sys.executable, execution_arguments, environment)
