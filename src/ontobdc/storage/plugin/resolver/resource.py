from pathlib import Path
from typing import Optional

from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.storage.adapter.resource import LocalFileResource
from ontobdc.storage.domain.port.resource import FileResourcePort


class ResourceParamResolver:
    def resolve(self, context: CliContextPort, _uri: str, prop: str) -> None:
        resource_value: Optional[object] = context.get_parameter_value(prop)
        if isinstance(resource_value, FileResourcePort):
            return

        if not isinstance(resource_value, str) or not resource_value.strip():
            return

        resource_path: Path = Path(resource_value.strip())
        if not resource_path.is_absolute():
            resource_path = Path(context.root_path) / resource_path

        file_resource: LocalFileResource = LocalFileResource(resource_path)
        if not file_resource.exists():
            return

        context.set_parameter_value(prop, file_resource)
