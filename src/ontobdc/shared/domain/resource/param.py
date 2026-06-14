
from typing import Any, List
from dataclasses import dataclass, field
from ontobdc.shared.domain.port.param import ParameterPort


@dataclass
class ParameterMetadata:
    id: str
    version: str
    name: str
    description: str
    author: str
    python_type: type
    tags: Any = field(default_factory=list)
    supported_languages: List[str] = field(default_factory=list)


class Parameter(ParameterPort):
    METADATA: ParameterMetadata

    @property
    def metadata(self) -> 'ParameterMetadata':
        return self.METADATA

        