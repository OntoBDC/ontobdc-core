
from typing import List
from abc import ABC, abstractmethod
from ontobdc.cli.domain.port.logger import LogRepositoryPort


class CliCommandHealthPort(ABC):
    """
    Port for checking the health of the CLI.
    """
    @abstractmethod
    def check(self, args: List[str], logger: LogRepositoryPort) -> bool:
        ...
