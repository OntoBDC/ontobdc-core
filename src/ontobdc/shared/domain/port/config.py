
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from ontobdc.shared.domain.resource.base import BaseResource


class ConfigDataPort(ABC):
    @property
    @abstractmethod
    def path(self) -> Path:
        ...

    @property
    @abstractmethod
    def all(self) -> Optional[Dict[str, Any]]:
        ...

    @property
    @abstractmethod
    def available_languages(self) -> List[BaseResource]:
        ...
