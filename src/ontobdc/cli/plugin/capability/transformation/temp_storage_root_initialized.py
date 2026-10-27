import os
import tempfile
from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.adapter.context import IsolatedCliContextAdapter
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_ontobdc_directory_ready.check import (
    main as check_ontobdc_directory_ready,
)
from ontobdc.cli.plugin.machine.init.machine import CliInitStateTransitionHandler
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class TempStorageRootInitializedCapability(TransactionCapability):
    """
    Initializes a temporary storage root when no real one was recovered.

    A fresh, isolated directory is created and bootstrapped by running the
    same ``--init`` machine a real storage root goes through, so the rest
    of the machine can still run without an enclosing OntoBDC container.
    """

    STORAGE_ROOT_KEY: ClassVar[str] = "storage_root"
    TEMP_PREFIX: ClassVar[str] = "ontobdc-remote-"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.cli.plugin.capability.transformation.target."
            "temp_storage_root_initialized"
        ),
        version="1.0.0",
        name="Temp Storage Root Initialized",
        description="Initialize a temporary storage root when no real one was recovered.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "storage", "root", "temp"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "A temporary storage root was initialized.",
            },
            "debug_entry": {
                "en": "Initializing a temporary storage root.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Temp Storage Root Initialized"

    def description(self, lang: str = "en") -> str:
        return "Initialize a temporary storage root when no real one was recovered."

    def is_satisfied(self, context: CliContextPort) -> bool:
        storage_root: Any = context.get_parameter_value(self.STORAGE_ROOT_KEY)
        if not isinstance(storage_root, str) or not storage_root.strip():
            return False

        root_path: Path = Path(storage_root)
        if not self._is_temp_root(root_path):
            return False

        return check_ontobdc_directory_ready(root_path=str(root_path)) == 0

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        temp_root: Path = Path(tempfile.mkdtemp(prefix=self.TEMP_PREFIX))
        previous_cwd: str = os.getcwd()
        os.chdir(temp_root)
        try:
            # A brand new directory has no config.yaml yet, so the context
            # must discover the root itself (falling back to this now
            # current directory) rather than being pointed at it directly:
            # the adapter requires an existing config.yaml when a root_dir
            # is given explicitly.
            init_context: CliContextPort = IsolatedCliContextAdapter([])
            CliInitStateTransitionHandler(context=init_context).execute()
        finally:
            os.chdir(previous_cwd)

        context.set_parameter_value(self.STORAGE_ROOT_KEY, str(temp_root))
        return {
            "storage_root": str(temp_root),
        }

    @classmethod
    def _is_temp_root(cls, root_path: Path) -> bool:
        temp_dir: Path = Path(tempfile.gettempdir()).resolve()
        resolved: Path = root_path.expanduser().resolve()
        return resolved.parent == temp_dir and resolved.name.startswith(cls.TEMP_PREFIX)
