from abc import ABC, abstractmethod
from typing import List


class CommandSuggestionPort(ABC):
    """
    Port for finding the commands closest to what a user typed.
    """

    @abstractmethod
    def suggest(self, command_args: List[str]) -> List[str]:
        """
        Return the commands closest to the given arguments, best first.

        Empty when nothing is close enough to be worth showing: a wrong
        guess costs the reader more than no guess at all.
        """
        ...
