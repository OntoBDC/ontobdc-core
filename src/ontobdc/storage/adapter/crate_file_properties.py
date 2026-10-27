import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary
from ontobdc.storage.adapter.bootstrap import StoragePathStatHelper
from ontobdc.storage.adapter.media_type import MediaTypeResolver


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class CrateFileProperties:
    """
    What the RO-Crate of a container says about each file it holds.

    Which properties the node of a file carries, in which order, and where each value comes from
    is not decided here: it is what the core ontology of OntoBDC declares as crate file
    properties (``core/ns.ttl``). This reads that declaration. What the code owns is how to read
    each value source (``_READERS``): a source the ontology names and the code cannot read is an
    error, never a property left out without saying.
    """

    ONTOLOGY_IRI: ClassVar[str] = "http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl"
    CORE: ClassVar[Namespace] = Namespace(ONTOLOGY_IRI + "#")

    # How each source of the ontology is read from a file: its name, its status, its extension.
    _READERS: ClassVar[Dict[str, Callable[[Path, Any], Optional[str]]]] = {
        "FileNameSource": lambda file_path, _stat: file_path.name,
        "FileSizeSource": lambda _path, stat: str(stat.st_size),
        "ModificationTimeSource": lambda _path, stat: iso_utc(stat.st_mtime),
        "MediaTypeSource": lambda file_path, _stat: MediaTypeResolver.of(file_path.name) or None,
        "CreationTimeSource": lambda _path, stat: CrateFileProperties.creation_time(stat),
    }

    _declared: ClassVar[Optional[List[Tuple[str, str, bool]]]] = None

    @classmethod
    def declared(cls) -> List[Tuple[str, str, bool]]:
        """
        The properties the ontology declares, in their order: the name in the crate, the source of
        the value, and whether a file may have none.

        Raises:
            ValueError: a property lacks its name or its source, or names a source nothing reads.
        """
        if cls._declared is None:
            graph: Graph = BrasidataCenterOntologyLibrary().graph(cls.ONTOLOGY_IRI)
            found: List[Tuple[int, str, str, bool]] = []
            subject: Any
            for subject in graph.subjects(RDF.type, cls.CORE.CrateFileProperty):
                name: Optional[Any] = graph.value(subject, cls.CORE.cratePropertyName)
                source: Optional[Any] = graph.value(subject, cls.CORE.hasValueSource)
                if not isinstance(name, Literal) or not isinstance(source, URIRef):
                    raise ValueError(f"The crate file property <{subject}> has no name or no value source.")
                reader: str = str(source).rsplit("#", 1)[-1]
                if reader not in cls._READERS:
                    raise ValueError(f"No code reads the value source <{source}> of the crate file property <{subject}>.")
                order: Optional[Any] = graph.value(subject, cls.CORE.cratePropertyOrder)
                optional: Optional[Any] = graph.value(subject, cls.CORE.isOptionalCrateProperty)
                found.append((int(order) if isinstance(order, Literal) else 0, str(name), reader, bool(optional)))

            cls._declared = [(name, reader, optional) for _, name, reader, optional in sorted(found)]

        return cls._declared

    @classmethod
    def of(cls, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        The properties of the file for its node in the crate, or None when the file cannot be
        statted even after the extended-path retry of Windows: the only case that is acceptable is
        a file that vanished between the walk of the directory and now. A property with no value
        is left out when the ontology says it is optional, and is an error when it says it is not.
        """
        stat_result: Any = StoragePathStatHelper.safe_stat(file_path)
        if stat_result is None:
            return None

        properties: Dict[str, Any] = {}
        name: str
        reader: str
        optional: bool
        for name, reader, optional in cls.declared():
            value: Optional[str] = cls._READERS[reader](file_path, stat_result)
            if value is None:
                if not optional:
                    raise ValueError(f"The file {file_path} has no value for the crate property '{name}', which is not optional.")
                continue
            properties[name] = value

        return properties

    @classmethod
    def modification_time(cls, stat_result: Any) -> Optional[str]:
        """
        When the file was last modified, in UTC; when the system tells no modification time (none,
        or the zero of the epoch), when it was created; None when it tells neither.
        """
        modified: Optional[Any] = getattr(stat_result, "st_mtime", None)
        if modified:
            return iso_utc(float(modified))
        return cls.creation_time(stat_result)

    @staticmethod
    def creation_time(stat_result: Any) -> Optional[str]:
        birth_time: Optional[Any] = getattr(stat_result, "st_birthtime", None)
        if birth_time is None and os.name == "nt":
            birth_time = stat_result.st_ctime
        return iso_utc(float(birth_time)) if birth_time is not None else None
