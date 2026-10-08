from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_execution_context_healthy.check import main as check_execution_context_healthy
from ontobdc.cli.plugin.check.is_execution_context_healthy.hotfix import main as hotfix_execution_context_healthy
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ExecutionContextHealthyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.execution_context_healthy",
        version="1.0.0",
        name="Execution Context Healthy",
        description="Ensure that context.ttl describes the execution context.",
        author=["TRAE"],
        tags=['cli', 'init', 'context'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "Context.ttl was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing context.ttl to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.EXECUTION_CONTEXT_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.EXECUTION_CONTEXT_HEALTHY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_execution_context_healthy,
            hotfix_execution_context_healthy,
            root_path,
            "context.ttl",
        )
        return {
            "resulting_state": CliInitProcessState.EXECUTION_CONTEXT_HEALTHY,
            "context_file": str(StorageBootstrap.get_context_file_path(root_path)),
        }
