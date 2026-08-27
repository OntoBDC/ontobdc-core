from typing import ClassVar, List


class A3SupportedLanguages:
    """Languages the a3 assistant currently recognizes.

    Mirrors the ``supported_languages`` convention already declared per
    capability elsewhere in the codebase (e.g. ``ContainerCleanedCapability
    .METADATA.supported_languages``) and, initially, the same language set
    InfoBIM's a3 LLM-suggestion pipeline already targets.
    """

    _LANGUAGES: ClassVar[List[str]] = ["en", "pt-br"]

    @classmethod
    def list(cls) -> List[str]:
        return list(cls._LANGUAGES)

    @classmethod
    def supports(cls, language: str) -> bool:
        return str(language or "").strip().lower() in cls._LANGUAGES
