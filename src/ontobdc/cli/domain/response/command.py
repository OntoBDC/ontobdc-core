
import json
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass, field, fields, is_dataclass


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
class ExceptionCommandResponse(CommandResponse):
    title: str = "OntoBDC Run Exception"
    description: str = "Command execution failed."
    content: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ListCommandResponse(CommandResponse):
    content: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WelcomeCommandResponse(CommandResponse):
    title: str = "InfoBIM Welcome"
    description: str = "Display the InfoBIM welcome experience."
    content: Dict[str, Any] = field(default_factory=dict)
