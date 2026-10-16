from typing import Any, Dict

from ontobdc.container.plugin.machine.container_remote.port import RemoteContainerProcessStatePort


class RemoteContainerProcessState(RemoteContainerProcessStatePort):
    """
    The states a remote OntoBDC Container connection passes through.

    A state is only valid while it makes sense to keep going. An address
    that cannot be downloaded, or a download that fails, is not a state of
    the connection: it is an exception, and ends the command.
    """

    UNDEFINED = "__undefined__"
    REMOTE_FILE_AVAILABLE = "__remote_file_available__"
    REMOTE_CONTAINER_REACHABLE = "__remote_container_reachable__"
    STORAGE_ROOT_RECOVERED = "__storage_root_recovered__"
    TEMP_STORAGE_ROOT_INITIALIZED = "__temp_storage_root_initialized__"
    CONTAINER_CREATED = "__container_created__"
    CONTAINER_FILES_DOWNLOADED = "__container_files_downloaded__"
    CONTAINER_REFRESHED = "__container_refreshed__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._labels,
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._descriptions,
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "RemoteContainerProcessState":
        return getattr(RemoteContainerProcessState, state.upper())

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
