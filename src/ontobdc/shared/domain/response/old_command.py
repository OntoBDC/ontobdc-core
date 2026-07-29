
import json
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class CommandResponse:
    title: str
    description: str
    content: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "content": self._serialize_response_value(self.content),
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def _serialize_response_value(self, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            serialized_dataclass: Dict[str, Any] = {}
            for dataclass_field in fields(value):
                serialized_dataclass[dataclass_field.name] = self._serialize_response_value(
                    getattr(value, dataclass_field.name)
                )
            return serialized_dataclass

        if isinstance(value, dict):
            serialized_dict: Dict[str, Any] = {}
            for key, item in value.items():
                serialized_dict[str(key)] = self._serialize_response_value(item)
            return serialized_dict

        if isinstance(value, (list, tuple, set)):
            return [self._serialize_response_value(item) for item in value]

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")

        if hasattr(value, "to_dict") and callable(value.to_dict):
            return self._serialize_response_value(value.to_dict())

        if hasattr(value, "to_json") and callable(value.to_json):
            return self._serialize_response_value(value.to_json())

        return value


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


@dataclass
class AutomatedTestCommandResponse(CommandResponse):
    """Response specific for automated tests execution."""
    pass


@dataclass
class SingleHtmlContentCommandResponse(CommandResponse):
    content: Dict[str, Any] = field(init=False, default_factory=dict)
    source_path: str = ""
    content_title: str = ""
    content_description: str = ""
    language: str = ""
    raw: str = ""
    items: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "content": {
                "source_path": self.source_path,
                "title": self.content_title,
                "description": self.content_description,
                "language": self.language,
                "raw": self.raw,
                "items": self.items,
            },
        }
