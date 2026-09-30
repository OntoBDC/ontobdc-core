from pathlib import Path
from typing import Any, ClassVar, List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
)


class DatasetTitleRepository:
    """
    Writes the title a reader recognises into the metadata of a dataset.

    The creation hotfix names a dataset after its directory, which carries
    the slug; the title the user typed is the name the domain recognises, so
    it replaces the generated one as soon as the metadata exists.
    """

    _ONTOLOGY_ADAPTER: ClassVar[OntologyConfigAdapter] = OntologyConfigAdapter(
        config_adapter=UnsetProjectRootConfigDataAdapter(),
    )
    _OBDC: ClassVar[Any] = _ONTOLOGY_ADAPTER.get_ontology_namespace_by_prefix("obdc")

    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path: Path = dataset_path
        self._metadata_path: Path = StorageBootstrap.get_dataset_storage_file_path(
            dataset_path,
        )

    def write_title(self, title: str) -> None:
        """
        Overwrite the title of the dataset, keeping the language tag it had.
        """
        if not self._metadata_path.is_file():
            raise FileNotFoundError(
                f"The dataset at {self._dataset_path} carries no metadata file."
            )

        graph: Graph = Graph()
        graph.parse(str(self._metadata_path), format="turtle")
        subject: URIRef = self._dataset_subject(graph)

        language: Optional[str] = None
        previous: Any
        for previous in list(graph.objects(subject, DCTERMS.title)):
            if isinstance(previous, Literal) and previous.language is not None:
                language = previous.language
            graph.remove((subject, DCTERMS.title, previous))

        graph.add((subject, DCTERMS.title, Literal(title, lang=language)))
        self._metadata_path.write_bytes(
            graph.serialize(format="turtle", encoding="utf-8")
        )

    def _dataset_subject(self, graph: Graph) -> URIRef:
        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, self._OBDC.EntityDataset)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError(
                f"The metadata of the dataset at {self._dataset_path} declares "
                f"{len(subjects)} datasets, expected exactly one."
            )

        return subjects[0]


class RegisteredDatasets:
    """
    Reads the datasets a container registers, in the order it lists them.

    The container metadata is the register: a dataset belongs to the
    container when the container graph points at it and states where it
    is. A directory that merely looks like a dataset is not one, and an
    entry whose location the graph states more than once is skipped rather
    than guessed at.
    """

    _LOCATION_SAFE_LENGTH_LIMIT: ClassVar[int] = 512

    @classmethod
    def of(cls, container_path: Path) -> List[Path]:
        """
        Return the path of every dataset the given container registers.
        """
        container_storage_file_path: Path = (
            StorageBootstrap.get_container_storage_file_path(container_path)
        )
        if not container_storage_file_path.is_file():
            return []

        graph: Graph = Graph()
        graph.parse(str(container_storage_file_path), format="turtle")

        container_subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, cls._obdc().DataContainer)
            if isinstance(subject, URIRef)
        ]
        if len(container_subjects) != 1:
            return []

        dataset_paths: List[Path] = []
        dataset_subject: URIRef
        for dataset_subject in cls._dataset_subjects(graph, container_subjects[0]):
            locations: List[Any] = list(
                graph.objects(dataset_subject, PROV.atLocation)
            )
            if len(locations) != 1:
                continue

            location_string: str = str(locations[0])
            try:
                resolved_location: Path = cls._location_to_path(
                    location_string,
                    container_path,
                )
            except (FileNotFoundError, ValueError, OSError):
                continue
            dataset_paths.append(resolved_location)

        return dataset_paths

    @classmethod
    def _dataset_subjects(
        cls,
        graph: Graph,
        container_subject: URIRef,
    ) -> List[URIRef]:
        """
        Return the entity datasets the container points at.
        """
        obdc: Any = cls._obdc()

        return [
            subject
            for subject in graph.objects(container_subject, obdc.hasEntityDataset)
            if isinstance(subject, URIRef)
            and (subject, RDF.type, obdc.EntityDataset) in graph
        ]

    @staticmethod
    def _obdc() -> Any:
        """
        Return the OntoBDC namespace, bootstrapping it on first reach.
        """
        StorageNamespaceBootstrap.initialize()

        return StorageNamespaceBootstrap.OBDC

    @staticmethod
    def _safe_basename(raw: Any) -> str:
        raw_string: str = raw if isinstance(raw, str) else ""
        if not raw_string:
            try:
                raw_string = str(raw)
            except (TypeError, ValueError):
                return ""
        stripped: str = raw_string.strip()
        if not stripped:
            return ""
        normalized: str = stripped.replace("\\", "/").rstrip("/")
        slash_at: int = normalized.rfind("/")
        if slash_at == -1:
            return normalized
        return normalized[slash_at + 1 :]

    @staticmethod
    def _locate_unique_by_name(
        container_path: Path,
        file_name: str,
    ) -> Optional[Path]:
        if not file_name or not container_path.is_dir():
            return None
        matches: List[Path] = sorted(
            candidate
            for candidate in container_path.rglob(file_name)
            if candidate.is_file()
        )
        if len(matches) == 1:
            return matches[0]
        return None

    @classmethod
    def _location_to_path(cls, location: str, container_path: Path) -> Path:
        """
        Return the location the graph states as a path on this filesystem.

        Handles poisoned locations produced by the old ``os.path.relpath`` bug,
        where a relative path like ``DEV/DXF/linkset/datapackage.json`` was
        re-concatenated dozens of times producing strings longer than the OS
        ``MAXPATH`` limit.  Canonicalisation therefore stays entirely in
        string space until a provenly-short suffix or the trailing basename
        is used to locate the actual file on disk.
        """
        if not isinstance(location, str) or not location.strip():
            raise ValueError(
                f"Empty dataset location in graph for container {container_path}."
            )
        raw: str = location.strip()
        resolved_container: Path = container_path.expanduser().resolve()
        if not resolved_container.is_dir():
            raise ValueError(
                f"Container path is not a directory: {resolved_container}."
            )
        limit: int = cls._LOCATION_SAFE_LENGTH_LIMIT

        parsed = urlparse(raw)
        if parsed.scheme == "file":
            decoded: str = url2pathname(unquote(parsed.path))
            if len(decoded) <= limit:
                try:
                    return Path(decoded).expanduser().resolve()
                except (OSError, ValueError, RuntimeError):
                    pass
            basename: str = cls._safe_basename(decoded)
            located: Optional[Path] = cls._locate_unique_by_name(
                resolved_container,
                basename,
            )
            if located is not None:
                return located.resolve()
            raise FileNotFoundError(
                f"Poisoned file-scheme dataset location could not be "
                f"resolved. Basename={basename!r}."
            )

        if len(raw) <= limit:
            try:
                location_path: Path = Path(raw).expanduser()
                if not location_path.is_absolute():
                    location_path = resolved_container / location_path
                return location_path.resolve()
            except (OSError, ValueError, RuntimeError):
                pass

        raw_segments: List[str] = [
            segment
            for segment in raw.replace("\\", "/").split("/")
            if segment
        ]
        try:
            linkset_index: int = raw_segments.index("linkset")
            tail_segments: List[str] = raw_segments[linkset_index:]
            linkset_tail: str = "/".join(tail_segments)
            if len(linkset_tail) <= limit:
                try:
                    tail_candidate: Path = (
                        resolved_container / Path(linkset_tail)
                    ).resolve()
                    if tail_candidate.is_file():
                        return tail_candidate
                except (OSError, ValueError, RuntimeError):
                    pass
        except ValueError:
            pass

        basename = cls._safe_basename(raw)
        located = cls._locate_unique_by_name(resolved_container, basename)
        if located is not None:
            return located.resolve()

        raise FileNotFoundError(
            f"Dataset location could not be resolved. Raw location length="
            f"{len(raw)} (possibly poisoned). Basename={basename!r}."
        )
