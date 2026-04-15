
from typing import Dict, Any
from ontobdc.cli.init import log as print_log, message_box
from ontobdc.core.adapter.storage import EntityStorageAdapter, EntityDataStorageAdapter


def create_entity(unique_name: str) -> None:
    if EntityStorageAdapter.exists(unique_name):
        message_box("GRAY", "OntoBDC", "Entity Exists", f"The entity {unique_name} already exists.")
        return

    print_log("INFO", f"Creating entity {unique_name}...")
    EntityStorageAdapter.create(unique_name)
    message_box("GREEN", "Success", "Entity Created", f"The entity {unique_name} has been created successfully.")


def entity_data() -> Dict[str, Any]:
    return EntityDataStorageAdapter.list()