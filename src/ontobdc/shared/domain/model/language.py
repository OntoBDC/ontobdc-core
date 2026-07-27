
from typing import Optional
from pydantic import BaseModel, Field


class LanguageResource(BaseModel):
    """
    Data model representing a language resource available in the OntoBDC application.
    """
    id: str = Field(description="The unique identifier for the language")
    name: str = Field(description="The display name of the language package")
    description: Optional[str] = Field(default=None, description="An optional description of the language")
