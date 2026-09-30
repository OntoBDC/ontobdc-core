import traceback
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.facade.adapter.logger import ActiveLogRepositoryBroker
from ontobdc.shared.domain.port.capability import (
    CapabilityPort,
    PersisterCapabilityPort,
    TransactionCapabilityPort,
    TransformationCapabilityPort,
)


class CapabilityLoggingSupport:
    """
    Logging applied around a side-effecting capability run.

    A capability author supplies the wording through
    ``CapabilityMetadata.log_message``, a two-level dictionary keyed by
    message key and then by language. Only the keys the plugins actually
    declare are read: ``info`` for a successful run and ``debug_entry``
    before one starts, plus ``debug_exception`` as the documented way to
    describe a failure. Anything not declared falls back to a generated
    line, so a run is never silent for lack of wording.

    Emission goes through the project's own logging API: the repository
    decides the threshold and ``InlineLogFormatter`` decides the colors, the
    level icon and how arguments are rendered. Nothing here formats a
    terminal line or filters by level.

    The class is stateless and never instantiated.
    """

    DEFAULT_LANGUAGE: ClassVar[str] = "en"
    ENTRY_MESSAGE_KEY: ClassVar[str] = "debug_entry"
    SUCCESS_MESSAGE_KEY: ClassVar[str] = "info"
    EXCEPTION_MESSAGE_KEY: ClassVar[str] = "debug_exception"
    TRACEBACK_TAIL_FRAMES: ClassVar[int] = 3
    REPORTED_OUTPUT_KEYS: ClassVar[int] = 8

    @classmethod
    def log_entry(cls, capability: CapabilityPort, context: CliContextPort) -> None:
        """
        Log, at DEBUG level, that a capability is about to run.
        """
        repository: Optional[LogRepositoryPort] = cls._repository(capability)
        if repository is None:
            return

        declared_message: Optional[str] = cls._declared_message(
            capability,
            context,
            cls.ENTRY_MESSAGE_KEY,
        )
        if declared_message is not None:
            repository.log_debug(declared_message)
            return

        repository.log_debug(
            f"{cls._family_name(capability)} capability started.",
            f"capability={type(capability).__name__}",
            f"id={cls._capability_id(capability)}",
        )

    @classmethod
    def log_success(
        cls,
        capability: CapabilityPort,
        context: CliContextPort,
        result: Dict[str, Any],
    ) -> None:
        """
        Log, at INFO level, that a capability run succeeded.
        """
        repository: Optional[LogRepositoryPort] = cls._repository(capability)
        if repository is None:
            return

        declared_message: Optional[str] = cls._declared_message(
            capability,
            context,
            cls.SUCCESS_MESSAGE_KEY,
        )
        if declared_message is not None:
            repository.log_info(declared_message)
            return

        repository.log_info(
            f"{cls._family_name(capability)} capability completed successfully.",
            f"capability={type(capability).__name__}",
            f"id={cls._capability_id(capability)}",
            f"outputs=[{', '.join(cls._output_keys(result))}]",
        )

    @classmethod
    def log_exception(
        cls,
        capability: CapabilityPort,
        context: CliContextPort,
        error: BaseException,
    ) -> None:
        """
        Log, at DEBUG level, an exception raised by a capability run.

        The exception is only reported here; reporting it as a failure stays
        with the caller, which re-raises it.
        """
        repository: Optional[LogRepositoryPort] = cls._repository(capability)
        if repository is None:
            return

        declared_message: Optional[str] = cls._declared_message(
            capability,
            context,
            cls.EXCEPTION_MESSAGE_KEY,
        )
        if declared_message is not None:
            repository.log_debug(declared_message)
            return

        repository.log_debug(
            f"{cls._family_name(capability)} capability raised "
            f"{type(error).__name__}: {error}",
            f"capability={type(capability).__name__}",
            f"id={cls._capability_id(capability)}",
            f"traceback={cls._traceback_tail(error)!r}",
        )

    @staticmethod
    def _repository(capability: CapabilityPort) -> Optional[LogRepositoryPort]:
        """
        Return the repository to log through, or None to stay silent.

        The broker holds the repository the CLI entry point built with the
        user's own threshold, and already declines to hold a null one. A
        capability run outside the CLI falls back to the log strategy a
        LoggerAwarePort caller injected into it.
        """
        active_repository: Optional[Any] = ActiveLogRepositoryBroker.instance().get()
        if active_repository is not None:
            return active_repository

        log_strategy: Optional[Any] = getattr(capability, "log_strategy", None)

        return getattr(log_strategy, "log_repository", None)

    @classmethod
    def _declared_message(
        cls,
        capability: CapabilityPort,
        context: CliContextPort,
        message_key: str,
    ) -> Optional[str]:
        """
        Return the wording the capability declares for the given key.

        The context language is preferred and English is the fallback, so a
        plugin translating only part of its messages still logs.
        """
        log_message: Any = getattr(
            getattr(capability, "metadata", None),
            "log_message",
            None,
        )
        if not isinstance(log_message, dict):
            return None

        messages_by_language: Any = log_message.get(message_key)
        if not isinstance(messages_by_language, dict):
            return None

        language: str
        for language in (cls._context_language(context), cls.DEFAULT_LANGUAGE):
            declared: Any = messages_by_language.get(language)
            if isinstance(declared, str) and declared.strip():
                return declared

        return None

    @classmethod
    def _context_language(cls, context: CliContextPort) -> str:
        """
        Return the language of the context, defaulting to English.
        """
        language: Optional[str] = context.language
        if language is None or not language.strip():
            return cls.DEFAULT_LANGUAGE

        return language.strip()

    @staticmethod
    def _family_name(capability: CapabilityPort) -> str:
        """
        Name the capability family, which tells a reader what ran.
        """
        if isinstance(capability, PersisterCapabilityPort):
            return "Persister"

        if isinstance(capability, TransactionCapabilityPort):
            return "Transaction"

        if isinstance(capability, TransformationCapabilityPort):
            return "Transformation"

        return "Capability"

    @staticmethod
    def _capability_id(capability: CapabilityPort) -> str:
        """
        Return the declared capability id, or the class name when absent.
        """
        capability_id: Any = getattr(
            getattr(capability, "metadata", None),
            "id",
            None,
        )
        if isinstance(capability_id, str) and capability_id.strip():
            return capability_id

        return type(capability).__name__

    @classmethod
    def _output_keys(cls, result: Dict[str, Any]) -> List[str]:
        """
        Return the first output keys of a run, for a line that stays short.
        """
        if not isinstance(result, dict):
            return []

        return sorted(str(key) for key in result)[:cls.REPORTED_OUTPUT_KEYS]

    @classmethod
    def _traceback_tail(cls, error: BaseException) -> str:
        """
        Return the last frames of the traceback of the given exception.
        """
        frames: List[str] = traceback.format_exception(
            type(error),
            error,
            error.__traceback__,
        )

        return "".join(frames[-cls.TRACEBACK_TAIL_FRAMES:])
