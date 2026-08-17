from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Optional
import os

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, XSD, Namespace

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError


class StorageLayoutConstants:
    """Centralized file / directory naming for the on-disk storage layer.

    All file-name and directory-name constants previously kept as module
    globals (``ONTOBDC_DIRECTORY_NAME``, ``STORAGE_FILE_NAME``,
    ``CONTEXT_FILE_NAME``, …) live here as class-level typed values so
    ownership of the storage layout is explicit and no bare globals
    remain in the module body.
    """

    ONTOBDC_DIRECTORY_NAME: ClassVar[str] = ".__ontobdc__"
    STORAGE_FILE_NAME: ClassVar[str] = "storage.ttl"
    CONTEXT_FILE_NAME: ClassVar[str] = "context.ttl"
    CONTAINER_STORAGE_FILE_NAME: ClassVar[str] = "container.ttl"
    DATASET_STORAGE_FILE_NAME: ClassVar[str] = "dataset.ttl"
    CRATE_METADATA_FILE_NAME: ClassVar[str] = "ro-crate-metadata.json"
    DEFAULT_CONTEXT_LANGUAGE: ClassVar[str] = "en"
    STORAGE_IDENTIFIER: ClassVar[str] = "urn:ontobdc:storage/local"


class StorageNamespaceBootstrap:
    """Initialize and expose the storage-level ontology namespaces.

    Mirrors the initialization pattern used by the repository and
    attachment-graph adapters: the ``OntologyConfigAdapter`` is built
    once (with the project-root-unset default) and cached on the class so
    the namespace lookups run exactly once per Python process.
    """

    _ontology_adapter: ClassVar["OntologyConfigAdapter | None"] = None

    OBDC: Namespace
    CT: Namespace
    PROV: Namespace
    BASE_CONTEXT_URI: Namespace = Namespace("urn:ontobdc:context/")

    @classmethod
    def _adapter(cls) -> OntologyConfigAdapter:
        if cls._ontology_adapter is None:
            cls._ontology_adapter = OntologyConfigAdapter(
                config_adapter=UnsetProjectRootConfigDataAdapter(),
            )
        return cls._ontology_adapter

    @classmethod
    def initialize(cls) -> None:
        adapter: OntologyConfigAdapter = cls._adapter()
        cls.OBDC = adapter.get_ontology_namespace_by_prefix("obdc")
        cls.CT = adapter.get_ontology_namespace_by_prefix("ct")
        cls.PROV = adapter.get_ontology_namespace_by_prefix("prov")


StorageNamespaceBootstrap.initialize()


class StorageBootstrap:
    """Build on-disk paths, the storage graph, and the execution context graph.

    Every helper exposed in this module that used to be a top-level
    function now lives inside ``StorageBootstrap``:

    * Pure path normalization helpers (``to_extended_length_path``) and
      path builders (``get_ontobdc_directory``, ``get_storage_file_path``,
      ``get_container_storage_file_path``, …) are classmethods or
      staticmethods because they do not require instance state.
    * Path-resolution helpers that need to consult the CLI context
      (``get_init_root_path``) similarly take all their inputs as
      parameters and need no owning instance.
    * Side-effecting utilities (``ensure_ontobdc_directory``,
      ``build_storage_graph``, ``build_context_graph``) keep their full
      original behaviour but no longer rely on module globals for the
      namespace registry — they use ``StorageLayoutConstants`` and
      ``StorageNamespaceBootstrap`` explicitly.
    """

    @staticmethod
    def to_extended_length_path(path: Path) -> Path:
        """Return a Windows extended-length path form of ``path``.

        Windows rejects absolute paths longer than MAX_PATH (260 characters)
        unless they carry the extended-length prefix, which deeply nested
        container trees (e.g. under OneDrive) routinely exceed. No-op outside
        Windows and for paths that already carry the prefix.
        """
        if os.name != "nt":
            return path

        extended_prefix: str = "\\\\?\\"
        unc_prefix: str = "\\\\"

        raw_path: str = str(path)
        if raw_path.startswith(extended_prefix):
            return path
        if raw_path.startswith(unc_prefix):
            return Path(
                extended_prefix + "UNC\\" + raw_path[len(unc_prefix):]
            )
        return Path(extended_prefix + raw_path)

    @classmethod
    def get_init_root_path(
        cls,
        context: Optional[CliContextPort] = None,
        root_path: Optional[str] = None,
    ) -> Path:
        if isinstance(root_path, str) and root_path.strip():
            return Path(root_path).expanduser().resolve()

        if context is not None:
            try:
                context_root_path: str = context.root_path
                if isinstance(context_root_path, str) and context_root_path.strip():
                    return Path(context_root_path).expanduser().resolve()
            except ProjectRootDirectoryNotSetError:
                pass

        return Path.cwd().resolve()

    @classmethod
    def get_ontobdc_directory(cls, root_path: Path) -> Path:
        return root_path / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME

    @classmethod
    def get_storage_file_path(cls, root_path: Path) -> Path:
        return cls.get_ontobdc_directory(root_path) / StorageLayoutConstants.STORAGE_FILE_NAME

    @classmethod
    def get_context_file_path(cls, root_path: Path) -> Path:
        return cls.get_ontobdc_directory(root_path) / StorageLayoutConstants.CONTEXT_FILE_NAME

    @classmethod
    def get_container_storage_file_path(cls, root_path: Path) -> Path:
        return (
            cls.get_ontobdc_directory(root_path)
            / StorageLayoutConstants.CONTAINER_STORAGE_FILE_NAME
        )

    @classmethod
    def get_dataset_storage_file_path(cls, root_path: Path) -> Path:
        return (
            cls.get_ontobdc_directory(root_path)
            / StorageLayoutConstants.DATASET_STORAGE_FILE_NAME
        )

    @classmethod
    def get_container_crate_metadata_file_path(
        cls,
        container_path: Path,
    ) -> Path:
        return (
            cls.get_ontobdc_directory(container_path)
            / StorageLayoutConstants.CRATE_METADATA_FILE_NAME
        )

    @classmethod
    def ensure_ontobdc_directory(cls, root_path: Path) -> Path:
        ontobdc_directory: Path = cls.get_ontobdc_directory(root_path)
        ontobdc_directory.mkdir(parents=True, exist_ok=True)
        return ontobdc_directory

    @classmethod
    def build_storage_graph(cls, root_path: Path) -> Graph:
        graph: Graph = Graph()
        graph.bind("dcterms", DCTERMS)
        graph.bind("ct", StorageNamespaceBootstrap.CT)
        graph.bind("prov", StorageNamespaceBootstrap.PROV)
        graph.bind("xsd", XSD)
        graph.bind("obdc", StorageNamespaceBootstrap.OBDC)

        storage_reference: URIRef = URIRef(StorageLayoutConstants.STORAGE_IDENTIFIER)
        created_at: Literal = Literal(
            datetime.now(timezone.utc).isoformat(),
            datatype=XSD.dateTime,
        )
        title: Literal = Literal("The Main Storage Index", lang="en")
        description: Literal = Literal(
            f"Main storage container for project at {root_path.name or root_path.as_posix()}",
            lang="en",
        )

        graph.add((storage_reference, RDF.type, StorageNamespaceBootstrap.OBDC.DataStorage))
        graph.add(
            (
                storage_reference,
                DCTERMS.identifier,
                Literal(StorageLayoutConstants.STORAGE_IDENTIFIER),
            )
        )
        graph.add((storage_reference, DCTERMS.title, title))
        graph.add(
            (storage_reference, StorageNamespaceBootstrap.CT.creationDate, created_at)
        )
        graph.add(
            (storage_reference, StorageNamespaceBootstrap.CT.description, description)
        )
        graph.add(
            (storage_reference, PROV.atLocation, URIRef(root_path.as_uri()))
        )

        return graph

    @classmethod
    def build_context_graph(
        cls,
        root_path: Path,
        language: str = StorageLayoutConstants.DEFAULT_CONTEXT_LANGUAGE,
    ) -> Graph:
        graph: Graph = Graph()
        graph.bind("", StorageNamespaceBootstrap.BASE_CONTEXT_URI)
        graph.bind("obdc", StorageNamespaceBootstrap.OBDC)
        graph.bind("owl", OWL)

        context_reference: URIRef = StorageNamespaceBootstrap.BASE_CONTEXT_URI[
            "CurrentContext"
        ]
        graph.add(
            (context_reference, RDF.type, StorageNamespaceBootstrap.OBDC.ExecutionContext)
        )
        graph.add((context_reference, RDF.type, OWL.NamedIndividual))
        graph.add(
            (
                context_reference,
                StorageNamespaceBootstrap.OBDC.contextLanguage,
                Literal(language),
            )
        )
        graph.add(
            (
                context_reference,
                StorageNamespaceBootstrap.OBDC.projectRootLocation,
                URIRef(root_path.as_uri()),
            )
        )

        return graph


# ---------------------------------------------------------------- public
# Re-exports for callers that import from the module directly (for example
# ``from ontobdc.storage.adapter.bootstrap import get_dataset_storage_file_path``)
# instead of going through ``StorageBootstrap`` classmethod accessors.
# These names are consumed across ontobdc/context and ontobdc/storage plugin
# packages; they were historically available at module scope so we mirror
# them here right after the owning classes are defined, avoiding any
# forward-reference or circular-import timing issues during import.

ONTOBDC_DIRECTORY_NAME = StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
STORAGE_FILE_NAME = StorageLayoutConstants.STORAGE_FILE_NAME
CONTEXT_FILE_NAME = StorageLayoutConstants.CONTEXT_FILE_NAME
CONTAINER_STORAGE_FILE_NAME = StorageLayoutConstants.CONTAINER_STORAGE_FILE_NAME
DATASET_STORAGE_FILE_NAME = StorageLayoutConstants.DATASET_STORAGE_FILE_NAME
CRATE_METADATA_FILE_NAME = StorageLayoutConstants.CRATE_METADATA_FILE_NAME
DEFAULT_CONTEXT_LANGUAGE = StorageLayoutConstants.DEFAULT_CONTEXT_LANGUAGE
STORAGE_IDENTIFIER = StorageLayoutConstants.STORAGE_IDENTIFIER

OBDC = StorageNamespaceBootstrap.OBDC
CT = StorageNamespaceBootstrap.CT
PROV = StorageNamespaceBootstrap.PROV


def get_ontobdc_directory(root_path: Path) -> Path:
    return StorageBootstrap.get_ontobdc_directory(root_path)


def get_storage_file_path(root_path: Path) -> Path:
    return StorageBootstrap.get_storage_file_path(root_path)


def get_context_file_path(root_path: Path) -> Path:
    return StorageBootstrap.get_context_file_path(root_path)


def get_container_storage_file_path(root_path: Path) -> Path:
    return StorageBootstrap.get_container_storage_file_path(root_path)


def get_dataset_storage_file_path(root_path: Path) -> Path:
    return StorageBootstrap.get_dataset_storage_file_path(root_path)


def get_container_crate_metadata_file_path(container_path: Path) -> Path:
    return StorageBootstrap.get_container_crate_metadata_file_path(container_path)


def ensure_ontobdc_directory(root_path: Path) -> Path:
    return StorageBootstrap.ensure_ontobdc_directory(root_path)
