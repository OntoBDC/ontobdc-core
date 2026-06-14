
import os
import warnings
from typing import Any
from rdflib import Graph
from rocrate.rocrate import ROCrate
from ontobdc.cli import get_root_dir
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.resource.command import CommandResponse
from ontobdc.storage.adapter.container import StorageLocalContainerAdapter
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.storage.domain.port.repository import LoadedStorageContainerCratePort
from ontobdc.storage import EMPTY_STORAGE_GRAPH, CRATE_METADATA_FILE, is_enabled, get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageContainerCrate, LoadedStorageGraph


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
        return is_enabled() and len(self._request.command_args) == 2

    def run(self) -> CommandResponse:
        """
        Execute the command to create a new local container.
        """
        try:
            import os
            path_arg: str = self._request.command_args[1]
            abs_path = os.path.abspath(path_arg).split(get_root_dir())[-1].strip("/")

            # Ensure the directory exists
            full_dir_path = os.path.join(get_root_dir(), abs_path)
            if not os.path.exists(full_dir_path):
                os.makedirs(full_dir_path, exist_ok=True)

            file_uri = f"urn:ontobdc:storage/local/{abs_path}"
            container_id = f"urn:ontobdc:storage/local/{abs_path}"

            # Load the storage graph
            graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file())

            # Create and save the local container
            container = StorageLocalContainerAdapter(graph, container_id, f"file://{full_dir_path}")
            if container.container_exists():
                raise ValueError(f"Container {container_id} already exists.")

            container.save()
            
            self._container_set_finish(full_dir_path, graph.graph.predicate_objects(container_id), container_id)

            self._print_info_log(f"Created local container at {abs_path}")

            # Execute hotfix command asynchronously
            try:
                import subprocess
                import sys
                
                # We need to construct the environment to make sure PYTHONPATH points to wip/src
                # Also, ontobdc.cli is a package, we need to point directly to its __init__.py
                # or pass -c to execute from the main namespace.
                # Since we know the path of the script, we can construct the direct call
                cli_path = os.path.join(get_root_dir(), "wip", "src", "ontobdc", "cli", "__init__.py")
                env = os.environ.copy()
                src_path = os.path.join(get_root_dir(), "wip", "src")
                env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

                # Start a detached process that executes the hotfix
                if get_root_dir():
                    subprocess.Popen(
                        [sys.executable, cli_path, "storage", "--fix"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env
                    )
            except Exception as e:
                self._print_info_log(f"Warning: Could not complete the process: {e}")

            return CommandResponse(
                title="Storage Container Created",
                description=f"Successfully created a new local storage container at {abs_path}.",
                content={"container_id": container_id, "location": file_uri, "path": abs_path}
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

    def _container_set_finish(self, full_dir_path: str, predicate_objects: Any, container_id: str) -> None:
        container_config_dir = os.path.join(full_dir_path, ".__ontobdc__")

        # Create config dir if not exists
        if not os.path.exists(container_config_dir):
            os.makedirs(container_config_dir, exist_ok=True)
            self._print_info_log(f"Created {container_config_dir}")

        container_storage_file = os.path.join(container_config_dir, "storage.ttl")

        # Create storage file if not exists
        if not os.path.exists(container_storage_file):
            # Write the empty storage RDF content to the file
            with open(container_storage_file, "w", encoding="utf-8") as f:
                f.write(EMPTY_STORAGE_GRAPH)
            self._print_info_log(f"Created {container_storage_file}")

        g_container: Graph = Graph()
        g_container.parse(container_storage_file, format="turtle")

        # 2. Add the correct properties from the root graph
        for p, o in predicate_objects:
            g_container.add((container_id, p, o))

        g_container.serialize(destination=container_storage_file, format="turtle")
        self._print_info_log(f"Synced data for container in {container_storage_file}")

        container_ro_crate_file: str = os.path.join(container_config_dir, CRATE_METADATA_FILE)
        if not os.path.exists(container_ro_crate_file) or not os.path.isfile(container_ro_crate_file):
            container_ro_crate: ROCrate = ROCrate(gen_preview=False)

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=r"No source for .*")
                container_ro_crate.write(container_config_dir)
                self._print_info_log(f"Created RO-Crate file {container_ro_crate_file}")

        container_ro_crate: LoadedStorageContainerCratePort = LoadedStorageContainerCrate(container_ro_crate_file)
        container_ro_crate.refresh()
        self._print_info_log(f"The RO-Crate file {container_ro_crate_file} is up to date.")


