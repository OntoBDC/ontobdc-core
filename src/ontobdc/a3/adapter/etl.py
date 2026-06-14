
from pathlib import Path
import concurrent.futures
from urllib.parse import urlparse
from typing import Optional, TypedDict
from ontobdc.a3.adapter.worker import StateWorkerAdapter
from ontobdc.a3.adapter.resource import RawTextResourceAdapter
from ontobdc.storage.adapter.resource import LocalFileResource
from ontobdc.storage.domain.port.resource import FileResourcePort
from ontobdc.a3.adapter.repository import A3LogLocalDirectoryRepository
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort, DatasetRepositoryPort


class A3EtlStartResult(TypedDict):
    status: str
    source: str
    resource_location: str
    package_path: str
    dataset_id: str
    container_id: str
    worker_result: str


class _IncomingResourceFactory:
    def __init__(self, root_path: str):
        self._root_path = Path(root_path)

    def create(self, source: str) -> FileResourcePort:
        if self._is_url(source):
            raise NotImplementedError("URL resources are not supported yet.")

        source_path = self._resolve_source_path(source)
        resource = LocalFileResource(source_path)
        if not resource.exists():
            raise FileNotFoundError(f"Resource not found: {source_path}")

        return resource

    def _resolve_source_path(self, source: str) -> Path:
        source_path = Path(source).expanduser()
        if source_path.is_absolute():
            return source_path

        return self._root_path / source_path

    @staticmethod
    def _is_url(source: str) -> bool:
        parsed = urlparse(source.strip())
        return parsed.scheme in {"http", "https"}


class A3EtlStarterAdapter:
    """
    Prepares the incoming source, stages the raw package and starts the worker.
    """
    def start(self, source: str, root_path: str) -> A3EtlStartResult:
        resource: FileResourcePort = _IncomingResourceFactory(root_path).create(source)
        raw_text: str = self._load_raw_text(resource)
        dataset: DatasetRepositoryPort = self._get_target_dataset(resource)
        container: Optional[ContainerRepositoryPort] = dataset.container
        if container is None:
            raise ValueError(f"Dataset '{dataset.id}' is not associated with a container.")

        raw_resource: RawTextResourceAdapter = RawTextResourceAdapter(raw_text)
        raw_resource.write(dataset)
        package_path: Path = raw_resource.path.parent
        worker_result: str = self._start_worker(package_path)

        result: A3EtlStartResult = {
            "status": "completed",
            "source": source,
            "resource_location": str(resource.path),
            "package_path": str(package_path),
            "dataset_id": dataset.id,
            "container_id": container.id,
            "worker_result": worker_result,
        }
        return result

    def _load_raw_text(self, resource: FileResourcePort) -> str:
        if not resource.is_text():
            raise NotImplementedError("Only text files are supported.")

        return resource.path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _get_target_dataset(resource: FileResourcePort) -> DatasetRepositoryPort:
        dataset: Optional[DatasetRepositoryPort] = resource.dataset
        if dataset is not None:
            return dataset

        raise ValueError(
            f"Incoming resource '{resource.path}' is not inside a registered dataset."
        )

    @staticmethod
    def _start_worker(package_path: Path) -> str:
        log_repository: A3LogLocalDirectoryRepository = A3LogLocalDirectoryRepository()
        worker: StateWorkerAdapter = StateWorkerAdapter(log_repository, package_path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker.work)
            try:
                return future.result()
            except Exception as exc:
                raise RuntimeError(f"Worker '{worker.name}' generated an exception: {exc}") from exc
