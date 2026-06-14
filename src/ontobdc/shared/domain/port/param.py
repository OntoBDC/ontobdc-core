
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, List


class ParameterPort(ABC):
    @property
    def metadata(self) -> 'ParameterMetadata':
        ...