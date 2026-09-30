from typing import Any, List, Type

from pydantic import BaseModel, Field


class ParameterMetadata(BaseModel):
    """
    Metadata describing a context parameter strategy.
    """

    id: str
    version: str
    name: str
    description: str
    author: List[str]
    python_type: Type[Any]
    tags: List[str] = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)
