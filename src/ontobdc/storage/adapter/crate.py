
import os
import json
import warnings
from pathlib import Path
from rocrate.rocrate import ROCrate


class CrateStorageAdapter():

    PAYLOAD_TRIPLE_DIR = os.path.join(".__icdd__", "payload", "triples")
    CRATE_METADATA_FILE = "ro-crate-metadata.json"

    def __init__(self, crate_path: str) -> None:
        if not CrateStorageAdapter.is_valid(crate_path):
            raise ValueError(f"The crate path {crate_path} is not valid")

        self._crate_path: str = crate_path
        self._crate_metadata_path: str = os.path.join(crate_path, self.PAYLOAD_TRIPLE_DIR, self.CRATE_METADATA_FILE)
        self._crate: ROCrate | None = None

    @classmethod
    def create(cls, crate_path: str) -> "CrateStorageAdapter":
        if not os.path.isdir(crate_path):
            raise ValueError(f"The crate path {crate_path} is not a directory")

        if CrateStorageAdapter.is_valid(crate_path):
            return cls(crate_path)

        payload_triples: str = os.path.join(crate_path, cls.PAYLOAD_TRIPLE_DIR)
        os.makedirs(payload_triples, exist_ok=True)

        crate_root = Path(crate_path).resolve()
        payload_root = (crate_root / cls.PAYLOAD_TRIPLE_DIR).resolve()

        crate = ROCrate(gen_preview=False)

        for root, dirs, files in os.walk(crate_root):
            root_path = Path(root).resolve()

            if root_path == payload_root or payload_root in root_path.parents:
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                if filename.startswith("."):
                    continue
                if filename == cls.CRATE_METADATA_FILE:
                    continue

                file_path = (root_path / filename).resolve()
                try:
                    rel_path = file_path.relative_to(crate_root)
                except ValueError:
                    continue

                crate.add_file(
                    source=None,
                    dest_path=str(rel_path).replace(os.sep, "/"),
                )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"No source for .*")
            crate.write(payload_triples)

        crate_adapter: CrateStorageAdapter = cls(crate_path)

        return crate_adapter

    @classmethod
    def is_valid(cls, crate_path: str) -> bool:
        if not os.path.isdir(crate_path):
            return False

        crate_metadata: str = os.path.join(crate_path, cls.PAYLOAD_TRIPLE_DIR, cls.CRATE_METADATA_FILE)
        if not os.path.exists(crate_metadata):
            return False

        try:
            with open(crate_metadata, "r", encoding="utf-8") as f:
                data = json.load(f)
            graph = data.get("@graph", [])
            if not isinstance(graph, list) or len(graph) == 0:
                return False
        except Exception:
            return False

        return True
