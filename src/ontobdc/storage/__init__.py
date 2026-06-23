
import os
from rdflib import Graph
from ontobdc.shared.adapter.config import ConfigDataAdapter


EMPTY_STORAGE_GRAPH: str = """
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ct: <https://standards.iso.org/iso/21597/-1/ed-1/en/Container#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
"""

STORAGE_URN_PREFIX = "urn:ontobdc:storage/"

STORAGE_RDF_BASE_URI: str = f"{STORAGE_URN_PREFIX}local/"

CRATE_METADATA_FILE = "ro-crate-metadata.json"

def is_enabled() -> bool:
    """
    Checks if all dependencies defined in the 'storage' extra 
    of pyproject.toml are installed and storage file is valid.
    """
    # if not is_extra_enabled("storage"):
    #     return False

    if not is_storage_file_valid():
        return False

    return True

def get_storage_file() -> str:
    return str(ConfigDataAdapter().config_dir / "storage.ttl")

def is_storage_file_valid() -> bool:
    if not os.path.exists(get_storage_file()):
        return False

    if not os.path.isfile(get_storage_file()):
        return False

    if not os.path.getsize(get_storage_file()):
        return False

    try:
        g = Graph()
        g.parse(get_storage_file(), format="turtle")
        return True
    except Exception:
        return False
