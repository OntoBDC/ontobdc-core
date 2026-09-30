from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Optional


class FileTypificationStrategyPort(ABC):
    """
    One typification strategy for a family of files.

    Every discovered strategy evaluates every file; none of them is
    selected over the others. A strategy with nothing useful to say about
    a file still answers, at its own low score, so a later stage sees the
    full set of opinions and weighs them, instead of one strategy silently
    vetoing the rest.
    """

    TYPE_KEY: ClassVar[str] = "type"
    SCORE_KEY: ClassVar[str] = "score"

    @property
    @abstractmethod
    def uri(self) -> str:
        """
        Stable identifier for this strategy, keying its evaluation.
        """
        ...

    @abstractmethod
    def evaluate(self, source_path: str, mime: Optional[str]) -> Dict[str, Any]:
        """
        Return this strategy's typing of the file, as
        ``{TYPE_KEY: ..., SCORE_KEY: ...}``.
        """
        ...
