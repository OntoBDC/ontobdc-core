
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class CapabilityMetadata(BaseModel):
    """
    Data Transfer Object (DTO) containing metadata information for a capability plugin.
    This includes definitions like its schema, required parameters, and supported languages.
    """
    id: str
    version: str
    name: str
    description: str
    author: List[str]
    tags: Any = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)
    require: Dict[str, List[str]] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    raises: List[Dict[str, Any]] = Field(default_factory=list)
