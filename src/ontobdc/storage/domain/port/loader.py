from abc import abstractmethod
from typing import List, Type

from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.storage.domain.port.typification import FileTypificationStrategyPort


class FileTypificationLoaderPort(PluginLoaderPort):
    """
    Contract for file typification strategy loaders.
    """
    @abstractmethod
    def get_all(self, resource: str = "typification") -> List[Type["FileTypificationStrategyPort"]]:
        """
        Retrieve every file typification strategy shipped by the plugins.
        """
        ...
