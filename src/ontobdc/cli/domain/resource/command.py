
import json
from typing import Any, Dict, List
from dataclasses import asdict, dataclass, field


@dataclass
class CommandResponse:
    title: str
    description: str
    content: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class HelpCommandResponse(CommandResponse):
    content: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class EnableCommandResponse(CommandResponse):
    success: bool = False


@dataclass
class ListCommandResponse(CommandResponse):
    content: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExceptionCommandResponse(CommandResponse):
    title: str = "OntoBDC Run"
    description: str = "Command execution failed."
    content: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportCommandResponse(CommandResponse):
    """Report command response."""
    pass


@dataclass
class CheckFailCommandResponse(CommandResponse):
    """Check fail command response."""
    pass

