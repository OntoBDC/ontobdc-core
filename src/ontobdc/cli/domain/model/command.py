from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CliCommandMetadata:
    id: str
    logical_component: str
    description: str = ""
    usage: str = ""
    arguments: List[Dict[str, Any]] = None
    depends_on: List[str] | str = "DEFAULT"

    def __post_init__(self) -> None:
        if self.arguments is None:
            self.arguments = []

        if self.depends_on == "DEFAULT":
            self.depends_on = ["cli.is_root_dir_set"]
        elif self.depends_on is None:
            self.depends_on = []
