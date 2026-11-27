from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_storage_index_healthy.check import main as check_storage_index_healthy
from ontobdc.cli.plugin.check.is_storage_index_healthy.hotfix import main as hotfix_storage_index_healthy
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class StorageHotfixedCapability(TransactionCapability):
    """
    Makes sure the storage index is healthy, and repairs it when it is not. A healthy index is left as it is:
    the repair builds the index again, and would drop the containers it registers.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.job.plugin.capability.transformation.target.storage_hotfixed",
        version="1.0.0",
        name="Storage Hotfixed",
        description="Make sure the storage index is healthy, and repair it when it is not.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["job", "storage", "hotfix"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The storage index is healthy."},
            "debug_entry": {"en": "Checking the storage index."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return JobCreateProcessState.STORAGE_HOTFIXED.label(lang)

    def description(self, lang: str = "en") -> str:
        return JobCreateProcessState.STORAGE_HOTFIXED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: str = str(Path(context.root_path).expanduser().resolve())
        repaired: bool = check_storage_index_healthy(root_path=root_path) != 0
        if repaired:
            if hotfix_storage_index_healthy(root_path=root_path) != 0:
                raise RuntimeError(f"The storage index of {root_path} could not be repaired.")
            if check_storage_index_healthy(root_path=root_path) != 0:
                raise RuntimeError(f"The storage index of {root_path} is still not healthy after the repair.")

        return {"resulting_state": JobCreateProcessState.STORAGE_HOTFIXED, "repaired": repaired}
