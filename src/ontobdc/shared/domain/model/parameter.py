
from typing import Any, List
from pydantic import BaseModel, Field
from ontobdc.shared.domain.port.parameter import ParameterPort


class ParameterMetadata(BaseModel, ParameterPort):
    id: str
    version: str
    name: str
    description: str
    author: List[str]
    python_type: type
    tags: Any = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)


class Parameter(ParameterPort):
    METADATA: ParameterMetadata

    @property
    def metadata(self) -> 'ParameterMetadata':
        return self.METADATA

        
