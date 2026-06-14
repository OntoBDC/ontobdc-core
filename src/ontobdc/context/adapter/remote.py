
import shutil
import inspect
import requests
from pathlib import Path
from frictionless import Package
from urllib.parse import urlparse, ParseResult
from typing import Dict, Any, Optional, Type, List
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.storage.domain.port.dataset import RemoteDatasetCapabilityPort, RemoteDatasetCapabilityVisitorPort, RemoteDatasetRepositoryPort, EntityQueryCapabilityVisitablePort
from ontobdc.context.domain.port.remote import LinksetDatapackageResourcePort
from ontobdc.context.domain.resource.remote import RemoteCapabilityMetadata
from ontobdc.shared.domain.resource.capability import CapabilityExecutor, Capability, QueryCapability


class LinksetDatapackageResource(LinksetDatapackageResourcePort):
    def __init__(self, dataset_url: str):
        self._dataset_url: str = dataset_url
        self._datapackage_url: str = self._get_datapackage_url()
        self._datapackage: Dict[str, Any] = self._load_datapackage()
        self._datapackage_object: Package = Package(self._datapackage, basepath=self._dataset_url)

    def _get_datapackage_url(self) -> str:
        parsed_url: ParseResult = urlparse(self._dataset_url)
        path: Path = Path(parsed_url.path)
        new_path: Path = path.parent / "linkset" / "datapackage.json"
        return parsed_url._replace(path=str(new_path)).geturl()

    def _load_datapackage(self) -> Dict[str, Any]:
        response: requests.Response = requests.get(self._datapackage_url)
        response.raise_for_status()
        return response.json()

    @property
    def url(self) -> str:
        return self._datapackage_url

    def get_resource_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = self._datapackage.get("resources", [])
        for resource in resources:
            if resource.get("name") == name:
                resource["content"] = self._datapackage_object.get_resource(name)
                return resource

        return None
        
    def get_all_resources(self) -> List[Dict[str, Any]]:
        return self._datapackage.get("resources", [])


class RemoteCommandRunAdapter:
    """
    Adapter for running remote capabilities from a dataset.
    Downloads the capability code to a temporary directory and executes it.
    """

    @classmethod
    def execute(cls, context: CliContextPort, dataset: RemoteDatasetRepositoryPort, capability_metadata: RemoteCapabilityMetadata) -> Dict[str, Any]:
        """
        Execute a remote capability using the context parameters.

        Required context parameters:
        - remote_dataset: RemoteDatasetRepositoryPort instance
        - capability_metadata: RemoteCapabilityMetadata instance
        """
        capability_id: str = capability_metadata.identifier

        try:
            try:
                capability_module: Any = dataset.load_capability(capability_id)

                # Step 3: Find and instantiate the capability class
                capability_class: Type[Capability] = cls._find_capability_class(capability_module, capability_id)
                capability_instance: Capability
                if issubclass(capability_class, RemoteDatasetCapabilityPort):
                    capability_instance = capability_class(dataset)
                else:
                    capability_instance = capability_class()

                if issubclass(capability_class, QueryCapability) or isinstance(capability_instance, EntityQueryCapabilityVisitablePort):
                    from ontobdc.context.adapter.visitor import EntityQueryCapabilityVisitor
                    visitor = EntityQueryCapabilityVisitor(dataset)
                    capability_instance.accept(visitor)

                # Step 4: Execute the capability
                result: Dict[str, Any] = CapabilityExecutor.execute(capability_instance, context)

                return result

            finally:
                # Clean up temporary directory
                shutil.rmtree(Path(capability_module.__file__).parent, ignore_errors=True)

        except Exception as e:
            raise RuntimeError(f"Failed to execute remote capability: {str(e)}") from e

    @classmethod
    def _find_capability_class(cls, module: Any, capability_id: str) -> Type[Capability]:
        """
        Find a Capability class in a module that matches the capability ID.
        """
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, "METADATA"):
                metadata: Any = obj.METADATA
                if hasattr(metadata, "id") and metadata.id == capability_id:
                    if issubclass(obj, Capability):
                        return obj
        
        raise ValueError(f"No Capability class found for id '{capability_id}' in module")


class RemoteDatasetCapability(RemoteDatasetCapabilityPort):
    """
    RemoteDatasetCapabilityPort implementation.
    """
    def __init__(self, remote_dataset_repo: RemoteDatasetRepositoryPort):
        self._gifts: Dict[str, List[Dict[str, Any]]] = {}
        self._remote_dataset_repo: RemoteDatasetRepositoryPort = remote_dataset_repo

    @property
    def remote_dataset_repo(self) -> RemoteDatasetRepositoryPort:
        return self._remote_dataset_repo

    @property
    def gifts(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._gifts

    def accept_gift(self, name: str, data: List[Dict[str, Any]]):
        """
        Receive the queried data from the visitor/host.
        """
        self._gifts[name] = data

    def accept(self, visitor: RemoteDatasetCapabilityVisitorPort) -> Any:
        return visitor.visit(self)

