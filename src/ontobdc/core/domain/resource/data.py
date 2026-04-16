
from typing import Any, Dict, Optional
from ontobdc.core.domain.resource.entity import Entity
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.core.domain.port.entity import EntityRepositoryPort


class EntityDataContainer:
    def __init__(self, entity: Entity, context: CliContextPort):
        self._entity: Entity = entity
        self._context: CliContextPort = context
        self._data: Dict[str, Dict[str, Any]] = None
        self._local_repository: EntityRepositoryPort = context.get_parameter_value("repository")
        # self._capability: Dict[str, Dict[str, Any]] = {
        #     "list"
        # }

    @property
    def data(self) -> Dict[str, Dict[str, Any]]:
        if self._data is None:
            self._data = self._local_repository.get_all()

        print(__file__)
        print(self._data)
        print(self._local_repository.path)
        print(self._local_repository)

        return self._data or {}


