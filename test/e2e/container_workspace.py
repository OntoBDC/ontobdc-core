"""On-disk container fixtures, independent of the container-create command."""

import json
from typing import Any, Callable, Dict, List, Set, Tuple
from pathlib import Path
from dataclasses import dataclass

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as prepare_metadata,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as prepare_manifest,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.hotfix import (
    main as prepare_datapackage,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as prepare_storage_index,
)


@dataclass(frozen=True)
class ContainerE2eWorkspace:
    root: Path
    container: Path
    identifier: str

    @classmethod
    def create(
        cls, root: Path, name: str = "container-under-test"
    ) -> "ContainerE2eWorkspace":
        root = root.resolve()
        runner: OntobdcCliProcessRunner = OntobdcCliProcessRunner(root)
        initialized: CliInvocationResult = runner.run("init")
        assert initialized.exit_code == 0, initialized.stdout + initialized.stderr
        container: Path = root / name
        container.mkdir()
        repairs: Tuple[Callable[..., int], ...] = (
            prepare_metadata,
            prepare_storage_index,
            prepare_datapackage,
            prepare_manifest,
        )
        repair: Callable[..., int]
        for repair in repairs:
            assert repair(container_path=str(container), root_path=str(root)) == 0, (
                repair.__module__
            )
        listing: CliInvocationResult = runner.run("container")
        assert listing.exit_code == 0, listing.stdout + listing.stderr
        containers: List[Dict[str, Any]] = listing.json["content"]["containers"]
        matches: List[Dict[str, Any]] = [
            entry
            for entry in containers
            if Path(entry["location"]).resolve() == container
        ]
        assert len(matches) == 1, containers
        identifier: Any = matches[0]["id"]
        assert isinstance(identifier, str) and identifier.startswith("urn:uuid:")
        return cls(root=root, container=container, identifier=identifier)

    def runner(self) -> OntobdcCliProcessRunner:
        return OntobdcCliProcessRunner(self.container)

    def snapshot(self) -> Dict[str, bytes]:
        files: Dict[str, bytes] = {}
        path: Path
        for path in self.container.rglob("*"):
            if path.is_file():
                files[path.relative_to(self.container).as_posix()] = path.read_bytes()
        return files

    def manifest_files(self) -> Set[str]:
        manifest: Dict[str, Any] = json.loads(
            (self.container / ".__ontobdc__" / "ro-crate-metadata.json").read_text(
                encoding="utf-8"
            )
        )
        nodes: List[Dict[str, Any]] = manifest["@graph"]
        return {node["@id"] for node in nodes if node.get("@type") == "File"}

    def selector(self, kind: str) -> str:
        if kind == "id":
            return self.identifier
        if kind == "path":
            return str(self.container)
        raise ValueError(f"Unknown fixture selector: {kind}")
