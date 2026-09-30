from abc import ABC, abstractmethod
from typing import List


class Widget(ABC):
    """A unit of content that materializes itself at a given PresentationSurface width.

    A Widget knows nothing about position, siblings, or borders — only how to
    turn itself into lines of text given the number of columns it was granted.
    """

    @abstractmethod
    def render(self, available_columns: int) -> List[str]:
        ...
