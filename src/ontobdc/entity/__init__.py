
from typing import Dict, Any, List
from ontobdc.core.domain.resource.entity import Entity
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.adapter.contex import CliContextResolver
from ontobdc.cli.init import log as print_log, message_box
from ontobdc.core.adapter.storage import EntityStorageAdapter
from ontobdc.core.domain.resource.data import EntityDataContainer
from ontobdc.core.adapter.entity import EntityFileRepositoryAdapter

CYAN='\033[0;36m'
RESET='\033[0m'


def create_entity(unique_name: str) -> None:
    if EntityStorageAdapter.exists(unique_name):
        message_box("GRAY", "OntoBDC", "Entity Exists", f"The entity {unique_name} already exists.")
        return

    print_log("INFO", f"Creating entity {unique_name}...")
    EntityStorageAdapter.create(unique_name)
    message_box("GREEN", "Success", "Entity Created", f"The entity {unique_name} has been created successfully.")


def entity_data(unique_name: str, *keys: str) -> List[Dict[str, Any]]:
    entity: Entity = EntityStorageAdapter.get(unique_name)

    resolver: CliContextResolver = CliContextResolver()
    context: CliContextPort = resolver.resolve(["entity_data", *keys])
    repo_param: Dict[str, Any] = context.get_parameter("repository")
    if not repo_param or "value" not in repo_param:
        raise ValueError(f"Parameter 'repository' not found.")

    repo_param["value"] = EntityFileRepositoryAdapter(entity)
    context.add_parameter("repository", repo_param)

    container: EntityDataContainer = EntityDataContainer(entity, context)

    if context.unprocessed_args:
        print("")
        unknown_args = " ".join(context.unprocessed_args)
        print_log('WARN', f"The following arguments were not recognized and may be ignored: {CYAN}{unknown_args}{RESET}")

    return list(container.data.values())
