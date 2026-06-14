
import os
from typing import List
from pathlib import Path
from datetime import datetime
from ontobdc.cli import get_config_dir
from ontobdc.shared.adapter.machine import LocalStatechartRepository
from ontobdc.shared.domain.port.logger import LogLevelPort, LogRepositoryPort
from ontobdc.storage.domain.port.repository import LocalRepositoryPort


class A3LocalStatechartRepository(LocalStatechartRepository):
    """
    Repository to load the A3 ETL statechart from the local filesystem.
    """

    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "domain", "machine", "standard_a3_extraction.yaml")
        super().__init__(filepath)


class A3LogLocalDirectoryRepository(LogRepositoryPort):
    """
    Repository adapter to store logs locally for the A3 pipeline.
    """

    def __init__(self):
        log_dir: str = os.path.join(get_config_dir(), "log", "a3")
        os.makedirs(log_dir, exist_ok=True)
        self._log_dir: Path = Path(log_dir)

    def log(self, level: LogLevelPort, message: str) -> None:
        date_str: str = datetime.now().strftime("%Y-%m-%d")
        log_file: Path = self._log_dir / f"a3_pipeline_{date_str}.log"
        timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as file_handle:
            file_handle.write(f"[{timestamp}] <{level.value}> {message}\n")


class TransformableDataPackageRepository(LocalRepositoryPort):
    """
    Repository adapter to store state packages locally for the A3 pipeline.
    """

    def __init__(self, package_path: Path):
        self._package_path: Path = package_path

    @property
    def path(self) -> Path:
        return self._package_path

    def list_file(self) -> List[Path]:
        return [file_path for file_path in self._package_path.iterdir() if file_path.is_file()]

    def list_package(self) -> List[Path]:
        return [package_path for package_path in self._package_path.iterdir() if package_path.is_dir()]
