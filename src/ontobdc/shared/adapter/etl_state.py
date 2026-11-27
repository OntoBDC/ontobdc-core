import hashlib
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class EtlStateFile:
    """
    The ETL file a state of a machine leaves, in the shape the machines of OntoBDC share::

        <container>/.__ontobdc__/etl/<module>/<phase>/<entity>/<state>.json

    A machine that works on one thing of the container named by an IRI, as a job does with the procedure
    it executes, leaves it under the md5 of that IRI instead::

        <container>/.__ontobdc__/etl/<module>/<md5 of the IRI>/<state>.json

    It holds the state, what the machine was working on and what the state produced. A state that runs
    again replaces its file, which is written whole or not at all.
    """

    @classmethod
    def directory(cls, container_path: Path, module: str, phase: str, entity: str) -> Path:
        return cls._module_directory(container_path, module) / phase / entity

    @classmethod
    def directory_by_iri(cls, container_path: Path, module: str, iri: str) -> Path:
        """
        The directory of the ETL of the one thing an IRI names: the md5 of the IRI, so that any IRI fits
        in a single segment whatever it holds.
        """
        return cls._module_directory(container_path, module) / hashlib.md5(iri.encode("utf-8")).hexdigest()

    @staticmethod
    def _module_directory(container_path: Path, module: str) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / module
        )

    @classmethod
    def write(
        cls,
        container_path: Path,
        module: str,
        phase: str,
        entity: str,
        state: str,
        result: Dict[str, Any],
    ) -> Path:
        return cls._store(
            cls.directory(container_path, module, phase, entity),
            {"state": state, "phase": phase, "entity": entity, "result": result},
        )

    @classmethod
    def write_by_iri(
        cls,
        container_path: Path,
        module: str,
        iri: str,
        state: str,
        result: Dict[str, Any],
    ) -> Path:
        return cls._store(
            cls.directory_by_iri(container_path, module, iri),
            {"state": state, "iri": iri, "result": result},
        )

    @classmethod
    def _store(cls, directory: Path, payload: Dict[str, Any]) -> Path:
        target: Path = directory / f"{payload['state']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path = target.with_name(f"{target.name}.tmp")
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=cls._serializable,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target

    @staticmethod
    def _serializable(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (set, frozenset)):
            return sorted(str(item) for item in value)

        return str(value)
