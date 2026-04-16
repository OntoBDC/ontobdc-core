
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any
from ontobdc.cli import get_root_dir
from ontobdc.storage.adapter.icdd import ICDDIndexAdapter
from rdflib import PROV, Graph, RDF, DCTERMS
from ontobdc.storage import has_storage_index
from ontobdc.storage.adapter.storage import StorageIndexAdapter


def main() -> int:
    try:
        from ontobdc.cli import get_config_dir
    except Exception:
        sys.stdout.write("[]")
        return 0

    config_dir = get_config_dir()
    if not config_dir:
        sys.stdout.write("[]")
        return 0

    if not has_storage_index():
        sys.stdout.write("[]")
        return 0

    storage_rdf = os.path.join(config_dir, StorageIndexAdapter.INDEX_FILE)

    g = Graph()
    parsed = False
    for fmt in (None, "xml", "turtle", "nt", "n3", "trig"):
        try:
            g.parse(storage_rdf, format=fmt)
            parsed = True
            break
        except Exception:
            continue

    if not parsed:
        sys.stdout.write("[]")
        return 0

    filter_uri = None
    if len(sys.argv) > 1 and sys.argv[1]:
        filter_path = os.path.abspath(sys.argv[1])
        filter_uri = Path(filter_path).resolve().as_uri()

    ct = ICDDIndexAdapter.CT
    containers = list(g.subjects(RDF.type, ct.ContainerDescription))
    default_container = containers[0] if containers else None

    items: Dict[str, Dict[str, Any]] = {}
    for dataset in set(g.subjects(predicate=PROV.atLocation)):
        locations = list(g.objects(dataset, PROV.atLocation))
        if not locations:
            continue
        location = locations[0]
        if filter_uri and str(location) != filter_uri:
            continue

        container = None
        container_refs = list(g.objects(dataset, DCTERMS.isPartOf))
        if container_refs:
            container = container_refs[0]
        if container is None:
            container = default_container

        container_key = str(container) if container is not None else "None"

        container_title = None
        if container is not None:
            titles = list(g.objects(container, DCTERMS.title))
            if titles:
                container_title = str(titles[0])

        dataset_title = None
        titles = list(g.objects(dataset, DCTERMS.title))
        if titles:
            dataset_title = str(titles[0])

        location_str = str(location)
        items.setdefault(container_key, {})
        items[container_key][str(dataset)] = {
            "container": {"@id": container_key, "title": container_title or "The Main Storage Index"},
            "title": dataset_title or "",
            "location": f"[~root_dir~]{location_str.split(get_root_dir())[-1]}",
        }

    sys.stdout.write(json.dumps(list(items.values()), ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
