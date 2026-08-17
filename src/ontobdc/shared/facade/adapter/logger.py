from typing import Any, Optional

__all__ = [
    "ActiveLogRepositoryBroker",
    "NullLogRepository",
    "clear_active_log_repository",
    "get_active_log_repository",
    "set_active_log_repository",
]


def __getattr__(name: str) -> Any:
    """Lazy module-level attribute resolver (PEP 562).

    Preserves the **original public contract** of this facade module
    (which used to eagerly re-export ``NullLogRepository`` from
    ``ontobdc.cli.adapter.logger`` on behalf of plugin modules)
    **without** introducing a circular import between
    ``shared.facade.adapter.logger`` and ``ontobdc.cli.__init__`` the
    moment this module is loaded first.

    External callers (storage plugin commands, *etc.*) that do::

        from ontobdc.shared.facade.adapter.logger import NullLogRepository

    will land here lazily.  At that point the CLI module graph is
    already initialised enough that the sub-import is always safe; the
    only circularity that existed was a module-load-time cycle triggered
    by importing *from the top of this file* while ``ontobdc.cli`` was
    itself being imported (because ``cli/__init__.py`` imports this
    module to reach ``set_active_log_repository``).
    """
    if name == "NullLogRepository":
        from ontobdc.cli.adapter.logger import (  # noqa: WPS433
            NullLogRepository as _NullLogRepository,
        )
        globals()["NullLogRepository"] = _NullLogRepository
        return _NullLogRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ActiveLogRepositoryBroker:
    """Singleton broker that exposes the currently active
    cross-cutting logger-like repository to components outside the
    direct dependency-injection chain.

    **Why this exists.**

    Several pipeline components (most notably every state-machine handler
    in ``storage``, ``view``, ``context`` and ``cli``) instantiate and
    execute capability objects via :class:`CapabilityExecutor` without
    propagating the rich logger they themselves hold in ``self._logger``.
    The executor therefore has no way to reach the *actual* active
    logger (the one already configured with the user's ``--log-level
    <LEVEL>`` threshold through the CLI orchestrator) without either:

    a) modifying every ``perform_state_transition()`` call-site across
       four separate state-machine modules (invasive, high regression
       risk), or
    b) falling back to a freshly-built standard logger with a default
       ``NOTICE`` threshold, which silently discards INFO-level messages
       (the very thing the user explicitly requested to see).

    This broker is deliberately **minimal**: it holds a single optional
    reference to the active logger-like repository, populated by
    :mod:`ontobdc.cli.__init__` immediately after the CLI entry-point
    builds its concrete logger, and cleared back to ``None`` before the
    process exits.  Components that need to emit cross-cutting logs
    (such as the capability executor) consult the broker first and
    fall back gracefully when no active repository has been registered.

    **Usage contract.**

    * Callers MUST treat the broker as optional.  :meth:`get` returns
      ``None`` whenever no broker has been registered yet, which must
      not break any execution path.
    * The broker is **thread-hostile on purpose**: the OntoBDC CLI and
      state machines are single-threaded, so a plain module-level
      singleton is sufficient and keeps the implementation auditable.
    * Setting the same repository instance multiple times in a row is
      a no-op; clearing explicitly with :meth:`clear` is allowed.

    **Circular-import safety.**

    The broker lives in the ``shared`` layer and therefore must never
    eagerly import concrete classes from ``cli`` at module-load time.
    The ``NullLogRepository`` check used by :meth:`set` is therefore
    performed lazily via class-name string comparison plus a late
    ``isinstance`` check attempted only once we know the ``cli``
    sub-module is already initialised.  This avoids the otherwise
    unavoidable cycle ``shared.facade.adapter.logger -> cli -> shared``
    triggered when :mod:`ontobdc.cli.__init__` is loaded first.
    """

    _instance: Optional["ActiveLogRepositoryBroker"] = None

    def __init__(self) -> None:
        self._active: Optional[Any] = None

    @classmethod
    def instance(cls) -> "ActiveLogRepositoryBroker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _is_null_log_repository(repository: Any) -> bool:
        """Lazy ``NullLogRepository`` detection.

        Avoids any eager import of ``ontobdc.cli.*`` so this module stays
        importable from anywhere without pulling the full CLI dependency
        chain or creating a cycle.
        """
        if repository is None:
            return True
        cls_name: str = getattr(type(repository), "__name__", "")
        if cls_name != "NullLogRepository":
            return False
        module_name: str = getattr(type(repository), "__module__", "")
        if "logger" not in module_name or "cli" not in module_name:
            # Another "NullLogRepository" exists somewhere else; treat
            # it conservatively as a real logger and let the broker
            # hold the reference.
            return False
        try:
            from ontobdc.cli.adapter.logger import NullLogRepository as _NullLogRepo  # noqa: WPS433
        except Exception:
            # Module not importable (e.g. import-error mid-cycle).  Fall
            # back to the class-name + module-name heuristic which was
            # already validated above.
            return True
        return isinstance(repository, _NullLogRepo)

    def set(self, repository: Optional[Any]) -> None:
        if self._is_null_log_repository(repository):
            self._active = None
            return
        self._active = repository

    def get(self) -> Optional[Any]:
        return self._active

    def clear(self) -> None:
        self._active = None


def get_active_log_repository() -> Optional[Any]:
    """Convenience module-level alias for
    :meth:`ActiveLogRepositoryBroker.instance().get`.

    Returns the currently active logger repository registered by the
    CLI entry-point, or ``None`` when no broker is active (the typical
    case for pure programmatic use outside the ``ontobdc`` CLI
    process).
    """
    return ActiveLogRepositoryBroker.instance().get()


def set_active_log_repository(repository: Optional[Any]) -> None:
    """Convenience module-level alias for
    :meth:`ActiveLogRepositoryBroker.instance().set`.
    """
    ActiveLogRepositoryBroker.instance().set(repository)


def clear_active_log_repository() -> None:
    """Convenience module-level alias for
    :meth:`ActiveLogRepositoryBroker.instance().clear`.
    """
    ActiveLogRepositoryBroker.instance().clear()
