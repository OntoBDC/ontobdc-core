
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from rocrate.rocrate import ROCrate
from rocrate.model.person import Person
from ontobdc.module.resource.domain.port.repository import DatasetRepositoryPort
from ontobdc.module.resource.adapter.folder import LocalFolderAdapter


class RoCrateDatasetAdapter:
    """
    Adapter for creating RO-Crate metadata from a DatasetRepositoryPort using the rocrate library.
    """

    def __init__(self, repository: DatasetRepositoryPort):
        """
        Initialize the RoCrateAdapter.

        :param repository: The dataset repository to create the crate from.
        """
        self.repository = repository

    def create_ro_crate(self, output_dir: Optional[str] = None, include_payload: bool = False) -> Dict[str, Any]:
        """
        Create an RO-Crate metadata file (ro-crate-metadata.json) for the dataset.
        
        The metadata is stored in a .__ontobdc__ subdirectory to avoid cluttering the root.
        
        If a directory contains a datapackage.json inside its .__ontobdc__ folder,
        only that datapackage.json is indexed, and all other contents of that directory
        are excluded from the RO-Crate.

        :param output_dir: The directory where the .__ontobdc__ folder should be created.
                           If None, it tries to use the first local folder path found in the repository.
        :return: The content of the ro-crate-metadata.json as a dictionary (for inspection).
        :raises ValueError: If output directory cannot be determined.
        """
        
        # 1. Determine base path (dataset root)
        base_path = None
        if output_dir:
            base_path = Path(output_dir)
        else:
            # Try to find a local folder path from repository
            for folder in self.repository.path_folders:
                if isinstance(folder, LocalFolderAdapter) and hasattr(folder, "path"):
                    base_path = Path(folder.path)
                    break
        
        if not base_path:
            raise ValueError("Could not determine output directory for RO-Crate. Please provide output_dir.")

        # Ensure base path exists
        if not base_path.exists():
            base_path.mkdir(parents=True, exist_ok=True)

        # 2. Determine metadata path (.__ontobdc__)
        metadata_path = base_path / ".__ontobdc__"
        if not metadata_path.exists():
            metadata_path.mkdir(parents=True, exist_ok=True)

        # 3. Initialize ROCrate
        # We initialize it with gen_preview=False to avoid generating HTML preview by default (optional)
        crate = ROCrate(gen_preview=False)
        
        # Set basic metadata for the root dataset
        crate.name = f"Dataset from {base_path.name}"
        crate.datePublished = datetime.now().isoformat()

        for folder in self.repository.path_folders:
            if isinstance(folder, LocalFolderAdapter) and hasattr(folder, "path"):
                folder_path = Path(folder.path)
                if folder_path.exists():
                    for root, dirs, files in os.walk(folder_path):
                        root_path = Path(root)
                        if ".__ontobdc__" in dirs:
                            dirs.remove(".__ontobdc__")

                        datapackage_path = root_path / ".__ontobdc__" / "datapackage.json"
                        if datapackage_path.exists():
                            try:
                                rel_path = datapackage_path.relative_to(base_path)
                                crate.add_file(
                                    source=(datapackage_path if include_payload else None),
                                    dest_path=rel_path,
                                )
                            except ValueError:
                                pass
                            dirs[:] = []
                            continue

                        for filename in files:
                            file_path = root_path / filename
                            if filename.startswith("."):
                                continue
                            if file_path.name == "ro-crate-metadata.json":
                                continue
                            try:
                                rel_path = file_path.relative_to(base_path)
                                crate.add_file(
                                    source=(file_path if include_payload else None),
                                    dest_path=rel_path,
                                )
                            except ValueError:
                                pass

        # 5. Write the crate to the hidden metadata directory
        # The ROCrate library writes ro-crate-metadata.json into the provided directory.
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"No source for .*")
            crate.write(metadata_path)

        # 6. Read back the generated metadata to return it
        ro_crate_file = metadata_path / "ro-crate-metadata.json"
        if ro_crate_file.exists():
            with open(ro_crate_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return {}
