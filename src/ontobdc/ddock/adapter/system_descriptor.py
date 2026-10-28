from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Dict, List, Optional

import yaml

from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.domain.model.system_descriptor import (
    PythonDependency,
    SystemDescriptor,
    SystemSource,
)


class SystemDescriptors:
    """
    Read and judge the ``system.obdc`` of a container: a YAML file with another
    name that says what to install.

    .. code-block:: yaml

        python:
          dep:
            - rdflib            # a name, or
            - name: pydantic    # a name with the version it must have
              version: 2.9.2
        source:
          local: src            # the folder of the ddock zip that becomes the application
          remote: ""            # the GitHub repository of the ddock; empty is the official one
        package:                # the GitHub address of each feature to add
          - https://github.com/usuario/feature-viewer
    """

    FILE_NAME: ClassVar[str] = "system.obdc"
    LOCK_FILE_NAME: ClassVar[str] = "system.obdc.lock"

    @classmethod
    def path_in(cls, container_path: Path) -> Path:
        return container_path / cls.FILE_NAME

    @classmethod
    def read(cls, container_path: Path) -> SystemDescriptor:
        """
        The descriptor of the container.

        Raises:
            FileNotFoundError: the container has no ``system.obdc``.
            ValueError: the file is not valid YAML, or says something a
                descriptor cannot say, or lacks what it needs.
        """
        path: Path = cls.path_in(container_path)
        if not path.is_file():
            raise FileNotFoundError(f"The container has no {cls.FILE_NAME}: {path}")

        try:
            data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise ValueError(f"{cls.FILE_NAME} is not valid YAML: {error}") from error
        if not isinstance(data, dict):
            raise ValueError(f"{cls.FILE_NAME} must be a mapping.")

        return SystemDescriptor(
            python_dependencies=cls._dependencies(data.get("python")),
            source=cls._source(data.get("source")),
            packages=cls._packages(data.get("package")),
        )

    @classmethod
    def _source(cls, value: Any) -> SystemSource:
        # A descriptor that names the folder alone is one from before the
        # source said where the ddock comes from.
        if isinstance(value, str):
            return SystemSource(local=cls._folder(value))
        if not isinstance(value, dict):
            raise ValueError(f"{cls.FILE_NAME} must say the source of the system in 'source'.")

        local: Any = value.get("local")
        if local is None:
            raise ValueError("'source' must say the folder to install, in 'source.local'.")

        return SystemSource(local=cls._folder(local), remote=cls._remote(value.get("remote")))

    @classmethod
    def _folder(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{cls.FILE_NAME} must say the folder to install in 'source'.")

        folder: PurePosixPath = PurePosixPath(value.strip())
        if folder.is_absolute() or ".." in folder.parts or folder == PurePosixPath("."):
            raise ValueError(f"'source' must be a folder inside the container, not '{value}'.")

        return str(folder)

    @staticmethod
    def _remote(value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("'source.remote' must be the address of a GitHub repository.")

        remote: str = value.strip()
        if not remote:
            return ""
        if GitHubZipAddress.repository(remote) is None:
            raise ValueError(f"'source.remote' must be the address of a GitHub repository: {value!r}")

        return remote

    @classmethod
    def _dependencies(cls, group: Any) -> List[PythonDependency]:
        if group is None:
            return []
        if not isinstance(group, dict):
            raise ValueError("'python' must be a mapping.")

        entries: Any = group.get("dep")
        if entries is None:
            return []
        if isinstance(entries, dict):
            entries = [{"name": name, "version": version} for name, version in entries.items()]
        if not isinstance(entries, list):
            raise ValueError("'python.dep' must be a list of packages.")

        return [cls._dependency(entry) for entry in entries]

    @staticmethod
    def _dependency(entry: Any) -> PythonDependency:
        name: Any
        version: Any = None
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict) and "name" in entry:
            name = entry["name"]
            version = entry.get("version")
        else:
            raise ValueError(f"A Python dependency is a name or a mapping with a name: {entry!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"A Python dependency needs a name: {entry!r}")
        if version is not None and (not str(version).strip()):
            version = None

        return PythonDependency(name=name.strip(), version=None if version is None else str(version).strip())

    @classmethod
    def _packages(cls, entries: Any) -> List[str]:
        if entries is None:
            return []
        if not isinstance(entries, list):
            raise ValueError("'package' must be a list of GitHub addresses.")

        addresses: List[str] = []
        entry: Any
        for entry in entries:
            address: Optional[str] = entry.get("url") if isinstance(entry, dict) else entry
            if not isinstance(address, str) or GitHubZipAddress.repository(address) is None:
                raise ValueError(f"A package must be the address of a GitHub repository: {entry!r}")
            addresses.append(address.strip())

        return addresses

    @classmethod
    def write_remote(cls, container_path: Path, remote: str) -> Path:
        """
        Record in ``system.obdc`` the address of the GitHub repository the
        ddock comes from, and return the file it was written to.

        Everything else the file says is kept as it is, so that the keys of a
        descriptor this reader does not know are not lost.
        """
        path: Path = cls.path_in(container_path)
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{cls.FILE_NAME} must be a mapping.")

        descriptor: SystemDescriptor = cls.read(container_path)
        data["source"] = {"local": descriptor.source.local, "remote": remote}
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

        return path
