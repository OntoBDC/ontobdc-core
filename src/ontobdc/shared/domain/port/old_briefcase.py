
from pathlib import Path
from rdflib import Graph
from typing import Dict, Any
from abc import ABC, abstractmethod
from ontobdc.shared.domain.model.entity import EntityMetadata
from ontobdc.shared.domain.port.repository import RemoteRepositoryPort



class BriefcaseEntryFilePackagerPort(ABC):
    """
    Port responsible for packaging an OntoBDC Briefcase into a distributable format.
    """
    @abstractmethod
    def package(self, entry_file: Path, output_file: Path) -> None:
        """
        Packages a specific entry file (e.g., dataset.ttl) into the output file.
        """
        ...


class RemoteBriefcaseRepositoryPort(RemoteRepositoryPort, ABC):
    """
    Base repository port for a remote briefcase.
    A briefcase is an abstraction that can represent either a single Dataset or a Container of datasets.
    """
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """
        The capabilities exposed by the briefcase.
        """
        ...

    @property
    @abstractmethod
    def entities(self) -> Dict[str, EntityMetadata]:
        """
        The entities provided by the briefcase.
        """
        ...
