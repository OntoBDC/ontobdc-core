
import os
import sys
import warnings
import subprocess
from pathlib import Path
from rdflib import Graph, URIRef
from rocrate.rocrate import ROCrate
from typing import Any, Iterable, List, Tuple
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.storage.adapter.container import StorageLocalContainerAdapter
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.storage.domain.port.repository import LoadedStorageContainerCratePort
from ontobdc.storage.adapter.repository import LoadedStorageContainerCrate, LoadedStorageGraph
from ontobdc.storage import EMPTY_STORAGE_GRAPH, CRATE_METADATA_FILE, is_enabled, get_storage_file


class StorageCreateCommand(CliCommandPort):
    """
    Command for creating a new local storage container at the given path.
    """
    METADATA = CliCommandMetadata(
        id="create",
        logical_component="storage",
        description="Create a new local storage container at the given path.",
        arguments=[
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": "Create a new local storage container at the given path.",
                "usage": "ontobdc storage --create <path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage container creation command at the CLI routing stage.
        """
        return len(args) > 2 and args[0] == "storage" and args[1] == "--create"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return (
            is_enabled()
            and len(self._request.command_args) == 2
            and self._request.command_args[0] == "--create"
        )

    def run(self) -> CommandResponse:
        """
        Execute the command to create a new local container.
        """
        try:
            root_dir = Path(ConfigDataAdapter().root_dir).resolve()
            full_dir_path, container_path = self._resolve_container_path(root_dir, self._request.command_args[1])
            full_dir_path.mkdir(parents=True, exist_ok=True)

            container_id = self._build_container_id(container_path)
            graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())
            container_ref = URIRef(container_id)
            container = StorageLocalContainerAdapter(graph, container_id, full_dir_path.as_uri())
            if container.container_exists():
                raise ValueError(f"Container {container_id} already exists.")

            container.save()

            self._container_set_finish(
                full_dir_path=full_dir_path,
                predicate_objects=graph.graph.predicate_objects(container_ref),
                container_ref=container_ref,
            )

            self._print_info_log(f"Created local container at {container_path}")
            self._run_hotfix_async(root_dir)

            return CommandResponse(
                title="Storage Container Created",
                description=f"Successfully created a new local storage container at {container_path}.",
                content={
                    "container_id": container_id,
                    "location": container_id,
                    "path": container_path,
                }
            )
        except Exception as e:
            return CommandResponse(
                title="Failed to Create Container",
                description=f"An error occurred while creating the storage container: {str(e)}",
                content={"error": str(e)}
            )

    def _print_info_log(self, message: str):
        if self._print_log:
            self._print_log("INFO", "Create Storage", message)

    def _resolve_container_path(self, root_dir: Path, path_arg: str) -> Tuple[Path, str]:
        requested_path = Path(path_arg).expanduser()
        if not requested_path.is_absolute():
            requested_path = (Path.cwd() / requested_path).resolve()
        else:
            requested_path = requested_path.resolve()

        try:
            relative_path = requested_path.relative_to(root_dir)
        except ValueError as exc:
            raise ValueError(
                f"Storage container path must be inside the project root: {root_dir}"
            ) from exc

        normalized_path = relative_path.as_posix().strip("/")
        if not normalized_path:
            raise ValueError("Storage container path cannot be the project root itself.")

        return (root_dir / relative_path, normalized_path)

    def _build_container_id(self, container_path: str) -> str:
        return f"urn:ontobdc:storage/local/{container_path}"

    def _run_hotfix_async(self, root_dir: Path) -> None:
        try:
            env = os.environ.copy()
            # Inherit the current sys.path to ensure we can import ontobdc dynamically
            env["PYTHONPATH"] = os.pathsep.join(sys.path)

            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.argv=['ontobdc', 'storage', '--fix']; from ontobdc.cli import main; main()"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
        except Exception as exc:
            self._print_info_log(f"Warning: Could not complete the process: {exc}")

    def _container_set_finish(
        self,
        full_dir_path: Path,
        predicate_objects: Iterable[Tuple[Any, Any]],
        container_ref: URIRef,
    ) -> None:
        container_config_dir = full_dir_path / ".__ontobdc__"
        if not container_config_dir.exists():
            container_config_dir.mkdir(parents=True, exist_ok=True)
            self._print_info_log(f"Created {container_config_dir}")

        container_storage_file = container_config_dir / "storage.ttl"
        if not container_storage_file.exists():
            container_storage_file.write_text(EMPTY_STORAGE_GRAPH, encoding="utf-8")
            self._print_info_log(f"Created {container_storage_file}")

        g_container: Graph = Graph()
        g_container.parse(str(container_storage_file), format="turtle")

        for p, o in predicate_objects:
            g_container.add((container_ref, p, o))

        g_container.serialize(destination=str(container_storage_file), format="turtle")
        self._print_info_log(f"Synced data for container in {container_storage_file}")

        container_ro_crate_file = container_config_dir / CRATE_METADATA_FILE
        if not container_ro_crate_file.exists() or not container_ro_crate_file.is_file():
            container_ro_crate: ROCrate = ROCrate(gen_preview=False)

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=r"No source for .*")
                container_ro_crate.write(str(container_config_dir))
                self._print_info_log(f"Created RO-Crate file {container_ro_crate_file}")

        container_ro_crate: LoadedStorageContainerCratePort = LoadedStorageContainerCrate(
            str(container_ro_crate_file)
        )
        container_ro_crate.refresh()
        self._print_info_log(f"The RO-Crate file {container_ro_crate_file} is up to date.")
