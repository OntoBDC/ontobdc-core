from typing import Any, Dict, List, Optional

from ontobdc.storage.domain.port.loader import FileTypificationLoaderPort
from ontobdc.storage.domain.port.typification import FileTypificationStrategyPort


class FileTypificationEvaluator:
    """
    Runs every discovered typification strategy against a file and
    collects each one's evaluation, keyed by the strategy's own URI.

    No strategy is selected over another: this class runs all of them and
    hands back every opinion, so a later stage can weigh disagreeing
    evaluations instead of having one decided for it here.
    """

    def __init__(self, loader: FileTypificationLoaderPort) -> None:
        self._loader: FileTypificationLoaderPort = loader
        self._strategies: Optional[List[FileTypificationStrategyPort]] = None

    def evaluate(self, source_path: str, mime: Optional[str]) -> Dict[str, Any]:
        """
        Return every discovered strategy's evaluation, keyed by its URI.
        """
        # strategy: FileTypificationStrategyPort
        return {
            strategy.uri: strategy.evaluate(source_path, mime)
            for strategy in self._available_strategies()
        }

    def _available_strategies(self) -> List[FileTypificationStrategyPort]:
        """
        Instantiate the discovered strategies once per evaluator.
        """
        if self._strategies is None:
            self._strategies = [
                strategy_type()
                for strategy_type in self._loader.get_all()
            ]

        return self._strategies
