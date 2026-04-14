
import os
import sys
import json
from typing import Any, Dict
from ontobdc.storage.adapter.icdd import ICDDIndexAdapter
from rdflib import Graph
from ontobdc.core.adapter.entity import EntityStorageAdapter


def main() -> int:
    entity_list: Dict[str, Any] = {}

    try:
        from ontobdc.cli import get_config_dir
    except Exception:
        sys.stdout.write(json.dumps(entity_list.values(), indent=4))
        return 0

    config_dir = get_config_dir()
    if not config_dir:
        sys.stdout.write(json.dumps(entity_list.values(), indent=4))
        return 0

    raw_data: Dict[str, Any] = {}

    try:
        entity_config_graph: Graph = EntityStorageAdapter.entity_config()
        entity_config: Dict[str, Any] = json.loads(entity_config_graph.serialize(format="json-ld"))

        for entity in entity_config:
            raw_data[entity['@id']] = {
                'id': entity['@id'],
                'title': entity[str(EntityStorageAdapter.DCTERMS.title)][0]['@value'],
                'is_entity': str(ICDDIndexAdapter.CT.Linkset) in entity['@type'],
            }

            if str(EntityStorageAdapter.DCTERMS.description) in entity.keys():
                raw_data[entity['@id']]['description'] = entity[str(EntityStorageAdapter.DCTERMS.description)][0]['@value']

        for entity in entity_config:
            if raw_data[entity['@id']]['is_entity'] and str(ICDDIndexAdapter.CT.containedInContainer) in entity.keys():
                entity_package = entity[str(ICDDIndexAdapter.CT.containedInContainer)][0]
                raw_data[entity['@id']]['package'] = {'title': raw_data[entity_package['@id']]['title']}

        for code, entity in raw_data.items():
            if entity['is_entity']:
                entity_list[code] = entity.copy()
                del(entity_list[code]['is_entity'])

    except FileNotFoundError:
        sys.stdout.write(json.dumps(entity_list.values(), indent=4))
        return 0
    except Exception as e:
        print(e)
        sys.stdout.write(json.dumps(entity_list.values(), indent=4))
        return 0

    # sys.stdout.write(json.dumps(entity_config, indent=4))
    sys.stdout.write(json.dumps(list(entity_list.values()), indent=4))


if __name__ == "__main__":
    raise SystemExit(main())

