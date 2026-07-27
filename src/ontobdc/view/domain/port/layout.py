
from typing import Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class MessageBoxLayoutData:
    title_type: str
    color: str
    title: str
    partial: str
    content: str
    subtitle: Optional[str] = None
    footer: Optional[str] = None


class MessageBoxLayoutRendererPort(ABC):
    @abstractmethod
    def render(self, layout_data: MessageBoxLayoutData) -> str:
        ...
