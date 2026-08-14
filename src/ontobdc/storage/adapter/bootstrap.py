from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import os

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, XSD, Namespace

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError

ONTOBDC_DIRECTORY_NAME: str = ".__ontobdc__"
STORAGE_FILE_NAME: str = "storage.ttl"
CONTEXT_FILE_NAME: str = "context.ttl"
CONTAINER_STORAGE_FILE_NAME: str = "container.ttl"
DATASET_STORAGE_FILE_NAME: str = "dataset.ttl"
CRATE_METADATA_FILE_NAME: str = "ro-crate-metadata.json"
DEFAULT_CONTEXT_LANGUAGE: str = "en"
STORAGE_IDENTIFIER: str = "urn:ontobdc:storage/local"

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)

OBDC: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")
CT: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
PROV: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("prov")
BASE_CONTEXT_URI: Namespace = Namespace("urn:ontobdc:context/")


def to_extended_length_path(path: Path) -> Path:
    """Return a Windows extended-length path form of ``path``.

    Windows rejects absolute paths longer than MAX_PATH (260 characters)
    unless they carry the extended-length prefix, which deeply nested
    container trees (e.g. under OneDrive) routinely exceed. No-op outside
    Windows and for paths that already carry the prefix.
    """
    if os.name != "nt":
        return path

    extended_prefix = "\\\\?\\"
    unc_prefix = "\\\\"

    raw_path: str = str(path)
    if raw_path.startswith(extended_prefix):
        return path
    if raw_path.startswith(unc_prefix):
        return Path(extended_prefix + "UNC\\" + raw_path[len(unc_prefix):])
    return Path(extended_prefix + raw_path)


def get_init_root_path(
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


def get_ontobdc_directory(root_path: Path) -> Path:
    return root_path / ONTOBDC_DIRECTORY_NAME


def get_storage_file_path(root_path: Path) -> Path:
    return get_ontobdc_directory(root_path) / STORAGE_FILE_NAME


def get_context_file_path(root_path: Path) -> Path:
    return get_ontobdc_directory(root_path) / CONTEXT_FILE_NAME


def get_container_storage_file_path(root_path: Path) -> Path:
    return get_ontobdc_directory(root_path) / CONTAINER_STORAGE_FILE_NAME


def get_dataset_storage_file_path(root_path: Path) -> Path:
    return get_ontobdc_directory(root_path) / DATASET_STORAGE_FILE_NAME


def get_container_crate_metadata_file_path(container_path: Path) -> Path:
    return get_ontobdc_directory(container_path) / CRATE_METADATA_FILE_NAME


def ensure_ontobdc_directory(root_path: Path) -> Path:
    ontobdc_directory: Path = get_ontobdc_directory(root_path)
    ontobdc_directory.mkdir(parents=True, exist_ok=True)
    return ontobdc_directory


def build_storage_graph(root_path: Path) -> Graph:
    graph: Graph = Graph()
    graph.bind("dcterms", DCTERMS)
    graph.bind("ct", CT)
    graph.bind("prov", PROV)
    graph.bind("xsd", XSD)
    graph.bind("obdc", OBDC)

    storage_reference: URIRef = URIRef(STORAGE_IDENTIFIER)
    created_at: Literal = Literal(
        datetime.now(timezone.utc).isoformat(),
        datatype=XSD.dateTime,
    )
    title: Literal = Literal("The Main Storage Index", lang="en")
    description: Literal = Literal(
        f"Main storage container for project at {root_path.name or root_path.as_posix()}",
        lang="en",
    )

    graph.add((storage_reference, RDF.type, OBDC.DataStorage))
    graph.add((storage_reference, DCTERMS.identifier, Literal(STORAGE_IDENTIFIER)))
    graph.add((storage_reference, DCTERMS.title, title))
    graph.add((storage_reference, CT.creationDate, created_at))
    graph.add((storage_reference, CT.description, description))
    graph.add((storage_reference, PROV.atLocation, URIRef(root_path.as_uri())))

    return graph


def build_context_graph(
    root_path: Path,
    language: str = DEFAULT_CONTEXT_LANGUAGE,
) -> Graph:
    graph: Graph = Graph()
    graph.bind("", BASE_CONTEXT_URI)
    graph.bind("obdc", OBDC)
    graph.bind("owl", OWL)

    context_reference: URIRef = BASE_CONTEXT_URI["CurrentContext"]
    graph.add((context_reference, RDF.type, OBDC.ExecutionContext))
    graph.add((context_reference, RDF.type, OWL.NamedIndividual))
    graph.add((context_reference, OBDC.contextLanguage, Literal(language)))
    graph.add((context_reference, OBDC.projectRootLocation, URIRef(root_path.as_uri())))

    return graph
