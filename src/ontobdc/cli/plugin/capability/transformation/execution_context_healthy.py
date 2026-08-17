from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.plugin.check.has_valid_context.check import main as check_execution_context
from ontobdc.context.plugin.check.has_valid_context.hotfix import main as hotfix_execution_context
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

class ExecutionContextHealthyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.execution_context_healthy",
        version="1.0.0",
        name="Execution Context Healthy",
        description="Ensure that context.ttl exists and conforms to the CLI init checks.",
        author=["TRAE"],
        tags=["cli", "init", "context"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Execution context file was validated against the CLI "
                    "initialization contract; no issues were detected."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the execution context file against the CLI "
                    "initialization contract."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Execution Context Healthy"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the context.ttl bootstrap context."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = StorageBootstrap.get_init_root_path(context=context)
        if check_execution_context(root_path=str(root_path)) != 0:
            if hotfix_execution_context(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix context.ttl during CLI init.")

        if check_execution_context(root_path=str(root_path)) != 0:
            raise ValueError("context.ttl is still invalid after the CLI init hotfix.")

        return {
            "resulting_state": CliInitProcessState.EXECUTION_CONTEXT_HEALTHY,
            "context_file": str(StorageBootstrap.get_context_file_path(root_path)),
        }
