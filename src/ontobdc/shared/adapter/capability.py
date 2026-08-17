
from abc import abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import re
import traceback

from ontobdc.shared.adapter.terminal_color import GRAY, RESET
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.facade.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import DynamicParamResolverAdapter
from ontobdc.shared.domain.port.resolver import DynamicParamResolverPort
from ontobdc.shared.domain.port.capability import TransactionCapabilityPort, CapabilityPort, QueryCapabilityPort, TransformationCapabilityPort


class CapabilityLoggingSupport:
    """Static namespace for the optional INFO-logging behaviour applied to
    successful side-effecting capabilities.

    **Why a class.**  AGENTS.md Rule #18 strictly forbids top-level free
    functions inside adapter/domain/entry-point modules.  Everything that
    would otherwise be a module-level helper lives here as a
    :func:`staticmethod` callable; the class itself is stateless and
    never instantiated.  External callers (currently only
    :class:`CapabilityExecutor`) reach through the class body directly.
    """

    # ------------------------------------------------------------------
    # Logger method extraction (uses the REAL, project-wide log API)
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_info_logger(repo: Any) -> Optional[Callable[[str], None]]:
        """Return a 1-arg ``fn(message)`` callable that writes an INFO line
        using the project's official logging API.

        The helper honours the **actual** contract exposed by
        :class:`LogRepositoryPort` and its implementations
        (:class:`BaseLoggerAdapter` and every subclass under
        ``cli/adapter/logger.py``).  Resolution order:

        1. ``repository.log_info(message)`` — convenience wrapper defined
           directly on :class:`BaseLoggerAdapter`; preferred because it
           preserves any log-queue batching performed by the concrete
           adapter.
        2. ``repository.log(LogLevel.INFORMATIONAL, message)`` — the
           canonical abstract-method signature from :class:`LogRepositoryPort`.
           This branch works for **every** compliant implementation
           including ones that skip the convenience helpers entirely.

        **Final threshold guarantee.**  When the repository exposes a
        ``set_log_level`` method we ensure at call-time that the
        threshold stored on *repo* is at most ``INFORMATIONAL``.  This
        protects against subtle bugs where a correctly-configured logger
        reference stored on the broker or handler was reset / cloned /
        reconstructed without its user-supplied threshold.  The check
        only runs once per (repo, wrapper) pair.
        """
        if repo is None:
            return None

        try:
            from ontobdc.cli.domain.model.logger import LogLevel as _LL
            _INFO_LEVEL: Any = _LL.INFORMATIONAL
            _DEBUG_LEVEL: Any = _LL.DEBUG
        except Exception:
            _INFO_LEVEL = None
            _DEBUG_LEVEL = None

        _set_level: Any = getattr(repo, "set_log_level", None)
        if callable(_set_level) and _DEBUG_LEVEL is not None:
            try:
                _set_level(_DEBUG_LEVEL)
            except Exception:
                pass

        via_info: Any = getattr(repo, "log_info", None)
        if callable(via_info) and _INFO_LEVEL is not None:
            _threshold_poke: Any = getattr(repo, "set_log_level", None)
            if callable(_threshold_poke):
                try:
                    _threshold_poke(_INFO_LEVEL)
                except Exception:
                    pass

            def _info_1(message: str) -> None:
                try:
                    via_info(message)
                except Exception:
                    return None
            return _info_1

        via_log: Any = getattr(repo, "log", None)
        if callable(via_log) and _INFO_LEVEL is not None:
            level: Any = _INFO_LEVEL
            _ensure = getattr(repo, "set_log_level", None)
            if callable(_ensure):
                try:
                    _ensure(level)
                except Exception:
                    pass

            def _info_2(message: str) -> None:
                try:
                    via_log(level, message)
                except Exception:
                    return None
            return _info_2

        return None

    # ------------------------------------------------------------------
    # Multi-channel logger resolver (ordered by quality)
    # ------------------------------------------------------------------
    @staticmethod
    def _lazy_get_logger(
        capability: "Capability",
        context: Optional[CliContextPort] = None,
    ) -> Optional[Callable[[str], None]]:
        """Resolve an INFO-level logger for a successful capability run.

        See class-level docstring for architectural motivation.  The
        resolver scans five channels in descending order of quality.
        Every branch is guarded so that missing logging infrastructure
        can **never** break a capability run — the method simply falls
        back to the next channel and finally returns ``None`` (silent
        skip, matching the pre-existing behaviour before this feature
        was introduced).

        Resolution order:

        0. **CLI-activated global broker** — fast-path for the
           ``ontobdc`` CLI entry-point.  The CLI ``main()`` registers
           the concrete logger instance right after building it via
           :mod:`ontobdc.shared.facade.adapter.logger`.  This returns
           the *exact* logger already configured with the user's
           ``--log-level`` threshold — no fallback guessing required.
        1. **CLI orchestrator path** — ``capability._log_strategy.log_repository``
           populated by :class:`LoggerAwarePort`-aware command runs.
        2. **State-machine handler back-reference** — handlers store
           ``self._logger``; when the executor only receives the
           handler's context object we walk ``_owner / _handler / _parent
           / _machine`` attributes looking for a logger-bearing owner.
        3. **Context / capability bag attributes** — ``_logger``,
           ``log_repository`` or ``logger`` set directly on the context
           or capability by programmatic users.
        4. **StandardConsoleLogger fallback** — only reached when no
           higher-quality channel fired (pure programmatic usage with
           no orchestrator).  The freshly-built fallback has its
           threshold lowered once to ``INFORMATIONAL`` so INFO messages
           are not dropped by the default ``NOTICE`` threshold.
        """
        # --- Channel 0: CLI broker ---
        try:
            from ontobdc.shared.facade.adapter.logger import (
                get_active_log_repository as _broker_get,
            )
        except Exception:
            _broker_get = None  # type: ignore[assignment]
        if _broker_get is not None:
            try:
                broker_repo: Any = _broker_get()
            except Exception:
                broker_repo = None
            if broker_repo is not None:
                via_broker: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_info_logger(broker_repo)
                )
                if via_broker is not None:
                    return via_broker

        # --- Channel 1: capability._log_strategy ---
        log_strategy: Any = getattr(capability, "_log_strategy", None)
        if log_strategy is not None:
            log_repository: Any = getattr(log_strategy, "log_repository", None)
            if log_repository is not None:
                direct: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_info_logger(log_repository)
                )
                if direct is not None:
                    return direct

        # --- Channel 2: state-machine owner chain ---
        if context is not None:
            visited: Set[int] = set()
            stack: List[Any] = [context]
            owner_attrs: Tuple[str, ...] = ("_owner", "_handler", "_parent", "_machine")
            while stack:
                obj: Any = stack.pop(0)
                obj_id: int = id(obj)
                if obj_id in visited:
                    continue
                visited.add(obj_id)
                candidate: Any = getattr(obj, "_logger", None)
                if candidate is not None:
                    via_handler: Optional[Callable[[str], None]] = (
                        CapabilityLoggingSupport._extract_info_logger(candidate)
                    )
                    if via_handler is not None:
                        return via_handler
                for attr in owner_attrs:
                    neighbour: Any = getattr(obj, attr, None)
                    if neighbour is not None and id(neighbour) not in visited:
                        stack.append(neighbour)

            # Context-level bag attributes (checked after owner walk so
            # owner-borne loggers win — they carry the correct threshold).
            for attr in ("_logger", "log_repository", "logger"):
                bag_value: Any = getattr(context, attr, None)
                if bag_value is not None:
                    via_bag: Optional[Callable[[str], None]] = (
                        CapabilityLoggingSupport._extract_info_logger(bag_value)
                    )
                    if via_bag is not None:
                        return via_bag

        # --- Channel 3: capability-instance bag attributes ---
        for attr in ("_logger", "log_repository", "logger"):
            cap_value: Any = getattr(capability, attr, None)
            if cap_value is not None:
                via_cap: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_info_logger(cap_value)
                )
                if via_cap is not None:
                    return via_cap

        # --- Channel 4: StandardConsoleLogger fallback ---
        try:
            from ontobdc.cli.adapter.logger import StandardConsoleLogger as _SCL
        except Exception:
            return None
        try:
            fallback_logger: Any = _SCL()
        except Exception:
            return None
        try:
            from ontobdc.cli.domain.model.logger import LogLevel as _FallbackLL
            set_level: Any = getattr(fallback_logger, "set_log_level", None)
            if callable(set_level):
                set_level(_FallbackLL.INFORMATIONAL)
        except Exception:
            pass  # threshold might still be NOTICE — best-effort only
        return CapabilityLoggingSupport._extract_info_logger(fallback_logger)

    # ------------------------------------------------------------------
    # Happy-path INFO emitter
    # ------------------------------------------------------------------
    @staticmethod
    def _log_capability_success(
        capability: "Capability",
        context: CliContextPort,
        result: Dict[str, Any],
    ) -> None:
        """Emit an INFO log when a side-effecting capability succeeds.

        Side-effecting = :class:`TransformationCapabilityPort` **or**
        :class:`TransactionCapabilityPort`.  :class:`QueryCapabilityPort`
        runs are deliberately silent (read-only, deterministic, would
        otherwise drown the output in multi-lookup pipelines).

        Message source, in preference order:

        1. ``capability.metadata.log_message["info"][context.language]``
           — capability-specific, language-specific content supplied by
           the plugin author.  Format declared on :class:`CapabilityMetadata`
           as ``Dict[str, Dict[str, str]]`` (outer key = log level, inner
           key = language tag).
        2. ``capability.metadata.log_message["info"]["en"]`` — same
           plugin-supplied dictionary but falling back to English when
           the current context language has no entry.
        3. The generic built-in template below — final guaranteed
           fallback that always produces a message so the log line is
           never empty / suppressed.

        This helper is called **only** after ``capability.execute(context)``
        has returned without raising.  Any exception from the capability
        deliberately bypasses this helper so that failure reporting
        remains the exclusive responsibility of the existing machinery
        (exception channels, state-machine retries, hotfix logs).
        """
        logger_fn: Optional[Callable[[str], None]] = (
            CapabilityLoggingSupport._lazy_get_logger(capability, context)
        )
        if logger_fn is None:
            return

        capability_id: str = str(
            getattr(getattr(capability, "metadata", None), "id", None)
            or capability.__class__.__name__
        )
        class_name: str = capability.__class__.__name__
        family_name: str
        if isinstance(capability, TransactionCapabilityPort):
            family_name = "Transaction"
        elif isinstance(capability, TransformationCapabilityPort):
            family_name = "Transformation"
        else:
            family_name = "Capability"

        result_keys: List[str] = []
        if isinstance(result, dict):
            result_keys = sorted(
                str(key) for key, _ in list(result.items())[:8]
            )

        metadata_log_message: Any = getattr(
            getattr(capability, "metadata", None), "log_message", None
        )
        if not isinstance(metadata_log_message, dict):
            metadata_log_message = {}
        info_bucket: Any = metadata_log_message.get("info")
        if not isinstance(info_bucket, dict):
            info_bucket = {}

        # Resolve the currently-active language via the context contract.
        # CliContextPort declares ``language`` as a property that returns
        # the configured language or None; we always fall back to "en"
        # so the dictionary lookups below always have at least one
        # deterministic key to try.
        context_language: Optional[str] = None
        try:
            language_property: Any = getattr(type(context), "language", None)
            if isinstance(language_property, property):
                getter: Any = language_property.fget
                if getter is not None:
                    try:
                        if (
                            "fallback" in getter.__code__.co_varnames
                            and getter.__code__.co_argcount >= 2
                        ):
                            context_language = getter(context, fallback="en")
                        else:
                            context_language = getter(context)
                    except Exception:
                        context_language = None
        except Exception:
            context_language = None

        if context_language is None or not isinstance(context_language, str):
            context_language = "en"

        normalized_language: str = str(context_language).strip() or "en"

        message: Optional[str] = None
        if normalized_language in info_bucket:
            raw_val: Any = info_bucket[normalized_language]
            if isinstance(raw_val, str) and raw_val.strip():
                message = raw_val
        if message is None and "en" in info_bucket:
            raw_fallback_en: Any = info_bucket["en"]
            if isinstance(raw_fallback_en, str) and raw_fallback_en.strip():
                message = raw_fallback_en

        # Final guaranteed fallback: the generic built-in template.
        if message is None:
            parts: List[str] = [
                f"{family_name} capability completed successfully.",
                f" Capability: {class_name}.",
                f" Id: {capability_id}.",
            ]
            if result_keys:
                parts.append(f" Output keys: [{', '.join(result_keys)}].")
            if isinstance(result, dict) and len(result) > 8:
                parts.append(f" Total outputs: {len(result)}.")
            message = "".join(parts)

        try:
            logger_fn(message)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # DEBUG-level extraction (identical structure; different threshold)
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_debug_logger(repo: Any) -> Optional[Callable[[str], None]]:
        """Return a 1-arg ``fn(message)`` callable that writes a DEBUG line.

        Mirrors :meth:`_extract_info_logger` exactly but uses the
        DEBUG-level contract:
        1. ``repository.log_debug(message)`` convenience on
           :class:`BaseLoggerAdapter`
        2. ``repository.log(LogLevel.DEBUG, message)`` canonical port.
        """
        if repo is None:
            return None

        try:
            from ontobdc.cli.domain.model.logger import LogLevel as _LL
            _DEBUG_LEVEL: Any = _LL.DEBUG
        except Exception:
            _DEBUG_LEVEL = None

        _set_level: Any = getattr(repo, "set_log_level", None)
        if callable(_set_level) and _DEBUG_LEVEL is not None:
            try:
                _set_level(_DEBUG_LEVEL)
            except Exception:
                pass

        via_debug: Any = getattr(repo, "log_debug", None)
        if callable(via_debug) and _DEBUG_LEVEL is not None:
            def _debug_1(message: str) -> None:
                try:
                    via_debug(message)
                except Exception:
                    return None
            return _debug_1

        via_log: Any = getattr(repo, "log", None)
        if callable(via_log) and _DEBUG_LEVEL is not None:
            level: Any = _DEBUG_LEVEL
            def _debug_2(message: str) -> None:
                try:
                    via_log(level, message)
                except Exception:
                    return None
            return _debug_2

        return None

    @staticmethod
    def _lazy_get_debug_logger(
        capability: "Capability",
        context: Optional[CliContextPort] = None,
    ) -> Optional[Callable[[str], None]]:
        """Resolve a DEBUG-level logger (same 5 channels as INFO logger)."""
        # Channel 0: CLI broker
        try:
            from ontobdc.shared.facade.adapter.logger import (
                get_active_log_repository as _broker_get,
            )
        except Exception:
            _broker_get = None  # type: ignore[assignment]
        if _broker_get is not None:
            try:
                broker_repo: Any = _broker_get()
            except Exception:
                broker_repo = None
            if broker_repo is not None:
                via_broker: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_debug_logger(broker_repo)
                )
                if via_broker is not None:
                    return via_broker

        # Channel 1: capability._log_strategy
        log_strategy: Any = getattr(capability, "_log_strategy", None)
        if log_strategy is not None:
            log_repository: Any = getattr(log_strategy, "log_repository", None)
            if log_repository is not None:
                direct: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_debug_logger(log_repository)
                )
                if direct is not None:
                    return direct

        # Channel 2: state-machine owner chain
        if context is not None:
            visited: Set[int] = set()
            stack: List[Any] = [context]
            owner_attrs: Tuple[str, ...] = ("_owner", "_handler", "_parent", "_machine")
            while stack:
                obj: Any = stack.pop(0)
                obj_id: int = id(obj)
                if obj_id in visited:
                    continue
                visited.add(obj_id)
                candidate: Any = getattr(obj, "_logger", None)
                if candidate is not None:
                    via_handler: Optional[Callable[[str], None]] = (
                        CapabilityLoggingSupport._extract_debug_logger(candidate)
                    )
                    if via_handler is not None:
                        return via_handler
                for attr in owner_attrs:
                    neighbour: Any = getattr(obj, attr, None)
                    if neighbour is not None and id(neighbour) not in visited:
                        stack.append(neighbour)

            for attr in ("_logger", "log_repository", "logger"):
                bag_value: Any = getattr(context, attr, None)
                if bag_value is not None:
                    via_bag: Optional[Callable[[str], None]] = (
                        CapabilityLoggingSupport._extract_debug_logger(bag_value)
                    )
                    if via_bag is not None:
                        return via_bag

        # Channel 3: capability-instance bag attributes
        for attr in ("_logger", "log_repository", "logger"):
            cap_value: Any = getattr(capability, attr, None)
            if cap_value is not None:
                via_cap: Optional[Callable[[str], None]] = (
                    CapabilityLoggingSupport._extract_debug_logger(cap_value)
                )
                if via_cap is not None:
                    return via_cap

        # Channel 4: StandardConsoleLogger fallback
        try:
            from ontobdc.cli.adapter.logger import StandardConsoleLogger as _SCL
        except Exception:
            return None
        try:
            fallback_logger: Any = _SCL()
        except Exception:
            return None
        try:
            from ontobdc.cli.domain.model.logger import LogLevel as _FallbackLL
            set_level: Any = getattr(fallback_logger, "set_log_level", None)
            if callable(set_level):
                set_level(_FallbackLL.DEBUG)
        except Exception:
            pass
        return CapabilityLoggingSupport._extract_debug_logger(fallback_logger)

    # ------------------------------------------------------------------
    # DEBUG emitters (entry + exception) — fine-grained metadata keys
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_context_language(context: CliContextPort) -> str:
        """Return the current context language, defaulting to ``"en"``.

        Shared helper used by both INFO and DEBUG emitters because the
        :class:`CliContextPort` ``language`` getter has two compatible
        signatures in flight (``property`` with 0 args on the adapter
        vs. ``def language(self, fallback=None)`` declared on the port).
        """
        try:
            language_property: Any = getattr(type(context), "language", None)
            if isinstance(language_property, property):
                getter: Any = language_property.fget
                if getter is not None:
                    try:
                        if (
                            "fallback" in getter.__code__.co_varnames
                            and getter.__code__.co_argcount >= 2
                        ):
                            resolved: Any = getter(context, fallback="en")
                        else:
                            resolved = getter(context)
                    except Exception:
                        resolved = None
                    if isinstance(resolved, str) and resolved.strip():
                        return resolved.strip()
        except Exception:
            pass
        return "en"

    @staticmethod
    def _pascal_to_snake_case(name: str) -> str:
        """Convert a PascalCase / CamelCase identifier to ``snake_case``.

        Handles both the simple case (``ValueError`` → ``value_error``) and
        runs of capital letters for acronyms (``HTTPError`` →
        ``http_error``, ``IOError`` → ``io_error``).  Used to map the
        Python exception class name (CamelCase) onto the per-exception
        debug metadata key: ``log_message["debug_value_error"][lang]``.
        """
        if not isinstance(name, str) or not name:
            return "exception"
        # Dual-pattern regex (industry standard for acronym-safe case conversion):
        # 1. (?<=[a-z0-9])(?=[A-Z])   — lowercase|digit → uppercase boundary
        #    (ValueError → Value_Error)
        # 2. (?<=[A-Z])(?=[A-Z][a-z]) — uppercase → uppercase-followed-by-lowercase
        #    (splits acronym runs before the next capitalised word:
        #     HTTPError → HTTP_Error, IOError → IO_Error,
        #     MyCustomXYZException → My_Custom_XYZ_Exception)
        intermediate: str = re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name
        )
        # 2) Split on underscores, lowercase each token, rejoin.
        tokens: List[str] = [t.lower() for t in intermediate.split("_") if t]
        return "_".join(tokens) if tokens else "exception"

    @staticmethod
    def _log_capability_debug_entry(
        capability: "Capability",
        context: CliContextPort,
    ) -> None:
        """Log a DEBUG line before ``capability.execute(context)`` runs.

        Contract (same structure as INFO, different metadata key):
        1. ``metadata.log_message["debug_entry"][context.language]``
        2. ``metadata.log_message["debug_entry"]["en"]``
        3. Guaranteed structured fallback with class, id, context params.
        """
        logger_fn: Optional[Callable[[str], None]] = (
            CapabilityLoggingSupport._lazy_get_debug_logger(capability, context)
        )
        if logger_fn is None:
            return

        class_name: str = capability.__class__.__name__
        capability_id: str = str(
            getattr(getattr(capability, "metadata", None), "id", None)
            or class_name
        )

        # --- Metadata resolution: key "debug_entry" (not generic "debug") ---
        metadata_log_message: Any = getattr(
            getattr(capability, "metadata", None), "log_message", None
        )
        if not isinstance(metadata_log_message, dict):
            metadata_log_message = {}
        debug_bucket: Any = metadata_log_message.get("debug_entry")
        if not isinstance(debug_bucket, dict):
            debug_bucket = {}

        normalized_language: str = (
            CapabilityLoggingSupport._resolve_context_language(context)
        )

        message: Optional[str] = None
        if normalized_language in debug_bucket:
            raw_val: Any = debug_bucket[normalized_language]
            if isinstance(raw_val, str) and raw_val.strip():
                message = raw_val
        if message is None and "en" in debug_bucket:
            raw_fallback_en: Any = debug_bucket["en"]
            if isinstance(raw_fallback_en, str) and raw_fallback_en.strip():
                message = raw_fallback_en

        # --- Final generic fallback (always produces a line) ---
        if message is None:
            param_keys: List[str] = []
            for method_name in ("list_parameters", "parameter_names"):
                list_fn: Any = getattr(context, method_name, None)
                if callable(list_fn):
                    try:
                        raw: Any = list_fn()
                    except Exception:
                        raw = None
                    if isinstance(raw, (list, tuple, set)):
                        param_keys = [str(k) for k in list(raw)[:12]]
                        break
            if not param_keys:
                for method_name in ("parameter_list",):
                    list_fn = getattr(context, method_name, None)
                    if callable(list_fn):
                        try:
                            raw = list_fn()
                        except Exception:
                            raw = None
                        if isinstance(raw, (list, tuple, set)):
                            param_keys = [str(k) for k in list(raw)[:12]]
                            break
            if not param_keys:
                for candidate in (
                    "container_id",
                    "container_path",
                    "dataset_id",
                    "language",
                    "target_state",
                    "surface_path",
                    "project_path",
                    "ifc_path",
                ):
                    has_parameter_fn: Any = getattr(context, "has_parameter", None)
                    if callable(has_parameter_fn):
                        try:
                            if has_parameter_fn(candidate):
                                if candidate not in param_keys:
                                    param_keys.append(candidate)
                        except Exception:
                            pass
                    if len(param_keys) >= 10:
                        break
            joined_keys: str = ", ".join(param_keys) if param_keys else "<none>"
            message = (
                f"[DEBUG CAPABILITY ENTRY] "
                f"class={class_name} "
                f"id={capability_id} "
                f"context_parameters=[{joined_keys}]"
            )

        try:
            prefixed_message: str = (
                f"{GRAY}[STARTED]"
                f"{RESET} {message}"
            )
            logger_fn(prefixed_message)
        except Exception:
            return None

    @staticmethod
    def _log_capability_debug_exception(
        capability: "Capability",
        context: CliContextPort,
        exc: BaseException,
    ) -> None:
        """Log a DEBUG (never ERROR) line for a raised exception.

        Lookup chain for the user message inside ``metadata.log_message``:
        1. ``debug_<exception_name_snake_case>[context.language]``  (ex:
           ``debug_value_error["pt-BR"]``)
        2. ``debug_<exception_name_snake_case>["en"]``
        3. ``debug_exception[context.language]``  (generic, any exception)
        4. ``debug_exception["en"]``
        5. **Guaranteed default:** the exception's own message,
           ``str(exc)``, prefixed with class/id/exc_type metadata and
           a 3-frame traceback tail.

        The exception is **never** suppressed; callers ``raise`` after
        invoking this helper.
        """
        logger_fn: Optional[Callable[[str], None]] = (
            CapabilityLoggingSupport._lazy_get_debug_logger(capability, context)
        )
        if logger_fn is None:
            return

        class_name: str = capability.__class__.__name__
        capability_id: str = str(
            getattr(getattr(capability, "metadata", None), "id", None)
            or class_name
        )
        exc_type_name: str = type(exc).__name__
        exc_snake: str = CapabilityLoggingSupport._pascal_to_snake_case(exc_type_name)
        exc_msg: str = str(exc)
        tb_lines: List[str] = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_short: str = "".join(tb_lines[-3:]) if tb_lines else "<no traceback>"

        # --- Metadata resolution (specific exc → generic exc fallback) ---
        metadata_log_message: Any = getattr(
            getattr(capability, "metadata", None), "log_message", None
        )
        if not isinstance(metadata_log_message, dict):
            metadata_log_message = {}
        normalized_language: str = (
            CapabilityLoggingSupport._resolve_context_language(context)
        )

        specific_key: str = f"debug_{exc_snake}"
        generic_key: str = "debug_exception"

        candidate_keys: List[Tuple[str, str]] = [
            (specific_key, normalized_language),
            (specific_key, "en"),
            (generic_key, normalized_language),
            (generic_key, "en"),
        ]

        message: Optional[str] = None
        for bucket_key, lang in candidate_keys:
            bucket: Any = metadata_log_message.get(bucket_key)
            if not isinstance(bucket, dict):
                continue
            raw_val: Any = bucket.get(lang)
            if isinstance(raw_val, str) and raw_val.strip():
                message = raw_val
                break

        # --- Guaranteed default: the exception's OWN message ---
        if message is None:
            default_body: str = exc_msg if exc_msg.strip() else exc_type_name
            message = (
                f"[DEBUG CAPABILITY EXCEPTION] "
                f"class={class_name} "
                f"id={capability_id} "
                f"exc_type={exc_type_name} "
                f"message={default_body!r} "
                f"traceback_tail={tb_short!r}"
            )

        try:
            logger_fn(message)
        except Exception:
            return None


class Capability(CapabilityPort):
    METADATA: CapabilityMetadata

    @property
    def metadata(self) -> CapabilityMetadata:
        return self.METADATA

    def tags(self, lang: str = "en") -> List[str]:
        """
        Returns the tags in the specified language.
        """
        if isinstance(self.metadata.tags, dict):
            return self.metadata.tags.get(lang, self.metadata.tags.get("en", []))
        return self.metadata.tags

    def check_inputs(self, context: CliContextPort) -> None:
        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            required = spec.get("required", False)
            if required and not context.has_parameter(prop):
                raise ValueError(f"Missing required input: {prop}")
            
            if context.has_parameter(prop):
                input_value = context.get_parameter_value(prop)
                prop_type = spec.get("type", None)
                
                if prop_type:
                    valid = True
                    if isinstance(prop_type, type):
                        if not isinstance(input_value, prop_type):
                            valid = False
                    elif prop_type == "integer":
                        if not isinstance(input_value, int):
                            valid = False
                    elif prop_type == "string":
                        if not isinstance(input_value, str):
                            valid = False
                    elif prop_type == "boolean":
                        if not isinstance(input_value, bool):
                            valid = False

                    if not valid:
                        raise ValueError(f"Input {prop} has type {type(input_value)}, expected {prop_type}") 

                # Check verification strategies
                for check in spec.get("check", []):
                    strategy = check
                    if isinstance(strategy, type):
                        strategy = strategy()

                    if not strategy.verify(prop, input_value, context):
                        raise ValueError(f"Input {prop} failed verification strategy {strategy.__class__.__name__}")

    def resolve_inputs(self, context: CliContextPort) -> None:
        """
        Resolve the inputs of the capability.
        """
        resolver: DynamicParamResolverPort = DynamicParamResolverAdapter()

        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            prop_uri: str = spec.get("uri", None)

            if not isinstance(prop_uri, str) or not prop_uri.strip():
                continue

            resolver.resolve(context, prop_uri, prop)

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None

    @abstractmethod
    def label(self, lang: str = "en") -> str:
        """
        Returns the label of the capability in the specified language.
        :param lang: The language to use.
        :return: The label of the capability in the specified language.
        """
        ...

    @abstractmethod
    def description(self, lang: str = "en") -> str:
        """
        Returns the description of the capability in the specified language.
        :param lang: The language to use.
        :return: The description of the capability in the specified language.
        """
        ...

    def __str__(self) -> str:
        return f"{self.metadata.id}"

    def __repr__(self) -> str:
        return f"{self.metadata.id}"


class QueryCapability(Capability, QueryCapabilityPort):
    pass


class TransformationCapability(Capability, TransformationCapabilityPort):
    pass


class TransactionCapability(Capability, TransactionCapabilityPort):
    pass


class CapabilityExecutor:
    @staticmethod
    def execute(capability: Capability, context: CliContextPort) -> Dict[str, Any]:
        """
        Execute the given capability with the provided context.

        :param capability: The capability to execute.
        :param context: The context to pass to the capability.
        :return: The output of the capability execution.
        """
        if isinstance(capability, CapabilityPort):
            capability.resolve_inputs(context)

            capability.check_inputs(context)

        # Debug entry trace (only for side-effecting capability families,
        # matching the families logged on success).  Uses the same metadata
        # resolution contract as INFO: log_message["debug"][lang] first.
        side_effecting: bool = (
            isinstance(capability, TransformationCapabilityPort)
            or isinstance(capability, TransactionCapabilityPort)
        )
        if side_effecting:
            CapabilityLoggingSupport._log_capability_debug_entry(capability, context)

        try:
            result: Dict[str, Any] = capability.execute(context)
        except BaseException as exc:
            if side_effecting:
                CapabilityLoggingSupport._log_capability_debug_exception(
                    capability, context, exc
                )
            raise

        if side_effecting:
            CapabilityLoggingSupport._log_capability_success(capability, context, result)

        return result
