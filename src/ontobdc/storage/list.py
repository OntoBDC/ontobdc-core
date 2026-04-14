
import os
import sys
import json

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

    filter_path = None
    if len(sys.argv) > 1 and sys.argv[1]:
        filter_path = os.path.abspath(sys.argv[1])

    try:
        from rdflib import Graph
        from rdflib.namespace import RDF
    except Exception:
        sys.stdout.write("[]")
        return 0

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

    items: list[dict] = []
    for s in set(g.subjects()):
        props: dict[str, list[dict]] = {}
        for p, o in g.predicate_objects(subject=s):
            key = str(p)
            props.setdefault(key, [])
            if hasattr(o, "datatype") or hasattr(o, "language"):
                props[key].append(
                    {
                        "type": "literal",
                        "value": str(o),
                        "datatype": str(getattr(o, "datatype", "")) if getattr(o, "datatype", None) else None,
                        "lang": getattr(o, "language", None),
                    }
                )
            else:
                props[key].append({"type": "uri", "value": str(o)})

        types = [str(o) for o in g.objects(subject=s, predicate=RDF.type)]
        items.append({"id": str(s), "types": types, "properties": props})

    if filter_path:
        filtered: list[dict] = []
        for item in items:
            for values in item.get("properties", {}).values():
                for v in values:
                    vv = v.get("value") if isinstance(v, dict) else None
                    if isinstance(vv, str) and os.path.abspath(vv) == filter_path:
                        filtered.append(item)
                        values = None
                        break
                if values is None:
                    break
        items = filtered

    sys.stdout.write(json.dumps(items, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
