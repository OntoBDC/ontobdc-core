
from typing import List
from pydantic import BaseModel, Field, ConfigDict
from ontobdc.cli.domain.port.context import CliContextPort


class CliCommandRequest(BaseModel):
    """
    Normalized representation of a CLI command request.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    logical_component: str = Field(description="The logical component targeted by the command.")
    component_action: str = Field(description="The action to perform on the component.")
    command_args: List[str] = Field(default_factory=list, description="Raw CLI arguments.")
    context: CliContextPort = Field(description="CLI context port instance.")
