from pathlib import Path
from typing import ClassVar, Dict, Optional, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.shared.adapter.mime_capability import MimeCapabilityMap
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent


class MimeChainExecution:
    """
    Run what a request declares for the MIME type of its file.

    The capability the context maps to the MIME type runs directly. When it
    maps none, the chain of responsibilities runs. A file nobody handles is
    a ``LookupError``. The result is what the capabilities that did the work
    returned, by capability id.
    """

    @staticmethod
    def execute(
        context: CliContextPort,
        support: Type,
        capability_by_mime_key: str,
        chain_package: str,
        chain_file: str,
        root_packages: Tuple[str, ...],
        failure: str,
    ) -> Dict[str, Dict[str, object]]:
        file_path: str = RequiredParameter.of(context, support.PATH_KEY)
        mime_type: Optional[str] = OpenFileMetadataEvent.mime_for(
            OpenFileMetadataEvent.container_of(Path(file_path)),
            Path(file_path),
        )
        context.set_parameter_value(support.MIME_KEY, mime_type)

        results: Dict[str, Dict[str, object]] = MimeChainExecution._run_mime_capability(
            context, capability_by_mime_key, mime_type, root_packages
        )
        if not results:
            worker: ChainOfResponsibilityWorkerAdapter = (
                ChainOfResponsibilityWorkerAdapter(
                    support=support,
                    context=context,
                    logger=NullLogRepository(),
                    statechart_file_path=StatechartLocator.locate(
                        chain_package, chain_file
                    ),
                    root_packages=root_packages,
                )
            )
            results = worker.work()
        if not results:
            raise LookupError(f"{failure} «{file_path}».")
        return results

    @staticmethod
    def _run_mime_capability(
        context: CliContextPort,
        key: str,
        mime_type: Optional[str],
        root_packages: Tuple[str, ...],
    ) -> Dict[str, Dict[str, object]]:
        capability_type: Optional[Type[CapabilityPort]] = (
            MimeCapabilityMap.capability_type(context, key, mime_type)
        )
        if capability_type is None:
            return {}

        result: Dict[str, object] = CapabilityExecutor.execute(
            capability_type(),
            context,
            StrategyParamResolver(ResolverLoader(root_packages=root_packages)),
        )
        return {capability_type.METADATA.id: result}
