from __future__ import annotations

import json
from typing import Any, ClassVar, Dict, Optional, Tuple, Type
import inspect
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import CapabilityExecutor, TransactionCapability
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

class FileOpeningStrategyFoundCapability(
    TransactionCapability,
    RootPackagesAwarePort,
):
    """Execute the open-file strategy chain and persist its audit event."""

    STATE_NAME: ClassVar[str] = "file_opening_strategy_found"
    ETL_EVENT_FILE_NAME: ClassVar[str] = f"__{STATE_NAME}__.json"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation."
            "file_opening_strategy_found"
        ),
        version="1.0.0",
        name="File Opening Strategy Found",
        description=(
            "Discover and execute the open-file responsibilities that accept "
            "the inspected file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "file", "open_file", "chain", "strategy", "etl"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                OpenFileChainSupport.PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={"properties": {}},
    )

    def __init__(self) -> None:
        self._root_packages: Tuple[str, ...] = ("ontobdc",)

    def set_root_packages(self, root_packages: Tuple[str, ...]) -> None:
        self._root_packages = root_packages or ("ontobdc",)

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Estratégia de abertura do arquivo encontrada"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        file_path: str = RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        mime_type: Optional[str] = OpenFileMetadataEvent.mime_for(
            root_path, Path(file_path)
        )
        context.set_parameter_value(OpenFileChainSupport.MIME_KEY, mime_type)

        results: Dict[str, Dict[str, object]] = self._run_mime_capability(
            context,
            mime_type,
        )
        if not results:
            results = self._run_chain(context)
        if not results:
            raise LookupError(
                "No open-file capability is registered for the file's MIME "
                "type and no open-file chain responsibility handled "
                f"«{RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)}»."
            )

        self._write_event(root_path=root_path, results=results)
        return results

    def _run_mime_capability(
        self,
        context: CliContextPort,
        mime_type: Optional[str],
    ) -> Dict[str, Dict[str, object]]:
        capability_type: Optional[Type[CapabilityPort]] = (
            self._mime_capability_type(context, mime_type)
        )
        if capability_type is None:
            return {}

        result: Dict[str, object] = CapabilityExecutor.execute(
            capability_type(),
            context,
            StrategyParamResolver(ResolverLoader(root_packages=self._root_packages)),
        )
        return {capability_type.METADATA.id: result}

    @staticmethod
    def _mime_capability_type(
        context: CliContextPort,
        mime_type: Optional[str],
    ) -> Optional[Type[CapabilityPort]]:
        capabilities_by_mime: Any = context.get_parameter_value(
            OpenFileChainSupport.CAPABILITY_BY_MIME_KEY
        )
        if capabilities_by_mime is None:
            return None
        if not isinstance(capabilities_by_mime, dict):
            raise TypeError(
                f"'{OpenFileChainSupport.CAPABILITY_BY_MIME_KEY}' must map MIME "
                f"types to capability classes; got {type(capabilities_by_mime)!r}."
            )

        if mime_type is None or mime_type not in capabilities_by_mime:
            return None

        capability_type: Any = capabilities_by_mime[mime_type]
        if not inspect.isclass(capability_type) or not issubclass(
            capability_type, CapabilityPort
        ):
            raise TypeError(
                f"'{OpenFileChainSupport.CAPABILITY_BY_MIME_KEY}' entry for "
                f"'{mime_type}' must be a capability class; got {capability_type!r}."
            )
        return capability_type

    def _run_chain(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        worker: ChainOfResponsibilityWorkerAdapter = ChainOfResponsibilityWorkerAdapter(
            support=OpenFileChainSupport,
            context=context,
            logger=NullLogRepository(),
            statechart_file_path=StatechartLocator.locate(
                "ontobdc.storage.plugin.machine.open_file",
                "standard_open_file_chain.yaml",
            ),
            root_packages=self._root_packages,
        )
        return worker.work()

    @classmethod
    def event_path(cls, root_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(root_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / "storage"
            / "open_file"
            / "file"
            / cls.ETL_EVENT_FILE_NAME
        )

    @classmethod
    def _write_event(
        cls,
        root_path: Path,
        results: Dict[str, Dict[str, object]],
    ) -> Path:
        event_path = cls.event_path(root_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        event = {
            "state": cls.STATE_NAME,
            "strategies": list(results.keys()),
            "results": results,
        }
        temporary_path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(
            json.dumps(
                event,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(event_path)
        return event_path
