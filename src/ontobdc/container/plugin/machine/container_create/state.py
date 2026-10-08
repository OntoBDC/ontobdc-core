from typing import Any, Dict

# The dataset creation states moved to the dataset_create machine; these names
# stay importable from here.
from ontobdc.container.plugin.machine.dataset_create.port import (  # noqa: F401
    DatasetCreateProcessStatePort,
)
from ontobdc.container.plugin.machine.dataset_create.state import (  # noqa: F401
    DatasetCreateProcessState,
)
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateProcessStatePort,
)


class ContainerCreateProcessState(ContainerCreateProcessStatePort):
    """
    Enum representing the possible states of the storage container creation process.
    """

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    DIRECTORY_READY = "__directory_ready__"
    CONTAINER_METADATA_READY = "__container_metadata_ready__"
    CONTAINER_STORAGE_INDEX_READY = "__container_storage_index_ready__"
    CONTAINER_MANIFEST_SYNCED = "__container_manifest_synced__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_labels", {}),
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_descriptions", {}),
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "ContainerCreateProcessState":
        return getattr(ContainerCreateProcessState, state.upper())

    @staticmethod
    def _normalize_presentation_metadata(value: Any) -> Dict[str, str]:
        if isinstance(value, str):
            return {"en": value}
        if not isinstance(value, dict):
            return {}

        return {
            str(language).strip().lower().replace("_", "-"): str(text)
            for language, text in value.items()
            if str(language).strip() and text is not None
        }

    @staticmethod
    def _localized_presentation_metadata(
        values: Dict[str, str],
        lang: str,
        default: str,
    ) -> str:
        normalized_lang: str = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))
