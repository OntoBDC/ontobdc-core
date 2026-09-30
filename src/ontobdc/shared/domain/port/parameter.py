from abc import ABC

from ontobdc.shared.domain.model.parameter import ParameterMetadata


class ParameterPort(ABC):
    @property
    def metadata(self) -> 'ParameterMetadata':
        ...