from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_ontobdc_directory_ready.check import (
    main as check_ontobdc_directory_ready,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class StorageRootRecoveredCapability(TransactionCapability):
    """
    Recovers the storage root the current execution runs under.

    A root already recovered by another capability (a temporary one, say)
    and left in the ``storage_root`` context parameter is trusted as-is.
    Otherwise the root is where a ``.__ontobdc__`` directory marks the
    container, found by walking up from the current directory. There is
    nothing to repair here: a missing root is not created, only reported.
    """

    STORAGE_ROOT_KEY: ClassVar[str] = "storage_root"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.storage_root_recovered",
        version="1.0.0",
        name="Storage Root Recovered",
        description="Recover the storage root the current execution runs under.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "storage", "root"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The storage root was recovered.",
            },
            "debug_entry": {
                "en": "Recovering the storage root.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Storage Root Recovered"

    def description(self, lang: str = "en") -> str:
        return "Recover the storage root the current execution runs under."

    def is_satisfied(self, context: CliContextPort) -> bool:
        root_path: Path = self._resolve_root_path(context)
        return check_ontobdc_directory_ready(root_path=str(root_path)) == 0

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = self._resolve_root_path(context)
        if check_ontobdc_directory_ready(root_path=str(root_path)) != 0:
            raise ValueError(f"No storage root was found from '{root_path}'.")

        context.set_parameter_value(self.STORAGE_ROOT_KEY, str(root_path))
        return {
            "storage_root": str(root_path),
        }

    @classmethod
    def _resolve_root_path(cls, context: CliContextPort) -> Path:
        existing: Any = context.get_parameter_value(cls.STORAGE_ROOT_KEY)
        if isinstance(existing, str) and existing.strip():
            return Path(existing)

        return StorageBootstrap.get_init_root_path(context=context)
