from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class ShaclViolation:
    """One result a SHACL validation reported, as its report states it."""

    focus_node: Optional[str]
    shape: Optional[str]
    path: Optional[str]
    constraint: Optional[str]
    message: Optional[str]

    def describe(self) -> str:
        return (
            f"focus node {self.focus_node}; shape {self.shape}; "
            f"path {self.path}; constraint {self.constraint}; "
            f"message {self.message}"
        )


@dataclass(frozen=True)
class ShaclValidationReport:
    """Whether a data graph conforms to a shapes graph, and why not."""

    conforms: bool
    violations: Tuple[ShaclViolation, ...]
    text: str
