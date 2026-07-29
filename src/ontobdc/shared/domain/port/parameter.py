
from abc import ABC


class ParameterPort(ABC):
    @property
    def metadata(self) -> 'ParameterMetadata':
        ...