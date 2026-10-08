from __future__ import annotations

import json
from typing import ClassVar, Dict, Optional, Tuple, Type
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.mime_capability import MimeCapabilityMap
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import CapabilityExecutor, TransactionCapability
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

class FileOpeningStrategyFoundCapability(
    TransactionCapability,
    RootPackagesAwarePort,
):
    """Select and execute an opening strategy, then persist its audit event.

    The MIME type comes from the requested file's metadata extraction ETL
    event. Selection prioritizes the class registered for that MIME type
    in the context; when no registration matches, it delegates to the
    opening chain's statechart. Configured root packages scope plugin and
    resolver discovery for these execution paths.

    A nonempty outer results dictionary allows the
    ``file_opening_strategy_found`` event to be written. This records that
    a strategy ran; it does not guarantee that a viewer opened the file
    or that each result reported success. Dependency errors propagate.
    """

    STATE_NAME: ClassVar[str] = "file_opening_strategy_found"
    ETL_EVENT_FILE_NAME: ClassVar[str] = f"__{STATE_NAME}__.json"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation."
            "file_opening_strategy_found"
        ),
        version="1.0.0",
        name="File Opening Strategy Found",
        description=(
            "Discover and execute the open-file responsibilities that accept "
            "the inspected file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "file", "open_file", "chain", "strategy", "etl"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                OpenFileChainSupport.PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={"properties": {}},
    )

    def __init__(self) -> None:
        """Initialize the discovery scope with the ``ontobdc`` package.

        Store ``("ontobdc",)`` in ``_root_packages`` for subsequent executions.
        This does not load plugins, read metadata, or execute the chain.
        ``set_root_packages`` can replace the discovery scope.
        """
        self._root_packages: Tuple[str, ...] = ("ontobdc",)

    def set_root_packages(self, root_packages: Tuple[str, ...]) -> None:
        """Configure the packages searched during plugin discovery.

        Args:
            root_packages: Tuple of importable package names. A nonempty tuple
                is stored unchanged; an empty tuple restores the default
                scope, ``("ontobdc",)``.

        The change affects MIME-route resolvers and chain responsibility
        discovery on subsequent calls. This method neither validates package
        availability nor performs discovery.
        """
        self._root_packages = root_packages or ("ontobdc",)

    def label(self, lang: str = "en") -> str:
        """Return the presentation label for the requested language.

        Args:
            lang: Language code. Comparison is case-insensitive, but does not
                strip whitespace or recognize other codes as equivalents of
                ``pt-br``.

        Returns:
            The Portuguese label for ``pt-br``; otherwise, the name declared
            in ``metadata.name``, which is currently English.
        """
        if lang.lower() == "pt-br":
            return "Estratégia de abertura do arquivo encontrada"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        """Return the description declared in the capability metadata.

        Args:
            lang: Retained to satisfy the presentation interface. Its value
                is not used by this implementation.

        Returns:
            ``metadata.description`` without translation or transformation,
            regardless of the requested language.
        """
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        """Execute the requested opening and persist its audit event.

        Read ``file_open_path`` as a required, whitespace-trimmed string.
        Resolve the storage root through the bootstrap: use the context's
        configured root when available, otherwise the current directory.
        Then read the metadata ETL event, which must reference the same
        resolved file path and declare the expected state. Do not infer the
        MIME type again from the extension.

        Store the retrieved MIME type, including ``None``, in the shared
        context under ``file_open_mime``. Try the capability registered for
        that MIME type, and use the chain only when this route returns an
        empty outer dictionary. An exception in the first route does not
        trigger the second. A nonempty outer result is accepted without
        examining inner fields such as ``handled`` or ``error``.

        Args:
            context: Request context containing the required file path,
                root information, and optional MIME-to-class registry.
                Strategies receive this context and may modify it.

        Returns:
            Results keyed by the identifier of each executed capability,
            after the audit event has been written.

        Raises:
            ValueError: The required path is missing or unusable, or the
                metadata event has an incompatible state, file, or MIME type.
            TypeError: The MIME registry or selected registered class is invalid.
            LookupError: Neither execution route produced results.
            OSError: Reading metadata or writing the audit event failed.

        JSON parsing errors, missing event keys, discovery failures,
        parameter resolution errors, and strategy exceptions also propagate.
        A failure before persistence does not remove the previous event.
        A persistence failure does not undo strategy effects already applied.
        """
        file_path: str = RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)
        container_path: Path = OpenFileMetadataEvent.container_of(Path(file_path))
        mime_type: Optional[str] = OpenFileMetadataEvent.mime_for(
            container_path, Path(file_path)
        )
        context.set_parameter_value(OpenFileChainSupport.MIME_KEY, mime_type)

        results: Dict[str, Dict[str, object]] = self._run_mime_capability(
            context,
            mime_type,
        )

        if not results:
            results = self._run_chain(context)

        if not results:
            raise LookupError(
                "No open-file capability is registered for the file's MIME "
                "type and no open-file chain responsibility handled "
                f"«{RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)}»."
            )

        self._write_event(container_path=container_path, results=results)
        return results

    def _run_mime_capability(
        self,
        context: CliContextPort,
        mime_type: Optional[str],
    ) -> Dict[str, Dict[str, object]]:
        """Execute the class registered for the MIME type, if one exists.

        Args:
            context: Context used to select the class and execute its instance.
                The executor may resolve and modify its parameters.
            mime_type: MIME type from the metadata event, or ``None`` when
                that event did not identify a type.

        Returns:
            ``{}`` when no class applies. Otherwise, a dictionary containing
            one entry that maps the class's ``METADATA.id`` to the executor's
            result. This entry exists even if the inner result is empty or
            reports failure.

        Instantiate the selected class without arguments. ``CapabilityExecutor``
        resolves inputs, checks their contracts, and executes the instance,
        using a ``StrategyParamResolver`` whose plugins are discovered under
        ``_root_packages``. The MIME-associated class comes from the context
        registry, not from that loader. Validation, construction, resolution,
        and execution exceptions propagate; this method does not run the chain.
        """
        capability_type: Optional[Type[CapabilityPort]] = (
            MimeCapabilityMap.capability_type(
                context,
                OpenFileChainSupport.CAPABILITY_BY_MIME_KEY,
                mime_type,
            )
        )

        if capability_type is None:
            return {}

        result: Dict[str, object] = CapabilityExecutor.execute(
            capability_type(),
            context,
            StrategyParamResolver(ResolverLoader(root_packages=self._root_packages)),
        )
        return {capability_type.METADATA.id: result}

    @staticmethod
    def _mime_capability_type(
        context: CliContextPort,
        mime_type: Optional[str],
    ) -> Optional[Type[CapabilityPort]]:
        """Validate the MIME registry and select a class without instantiating it.

        Args:
            context: Context optionally containing ``open_file_capability``,
                a dictionary mapping MIME types to capability classes.
            mime_type: Registry key matched exactly. No normalization,
                MIME-family matching, or wildcard matching is performed.

        Returns:
            ``None`` when the registry is absent, the MIME type is ``None``,
            or the registry has no matching key; otherwise, the class
            associated with the supplied MIME type.

        Raises:
            TypeError: An existing registry is not a dictionary, or the
                selected entry is not a class inheriting from ``CapabilityPort``.

        Validate the registry's type before checking whether the MIME type
        is known. Only the selected entry is validated; other entries are not
        inspected. Do not modify the context, discover plugins, or verify
        whether the class can be constructed or can open the file.
        """
        capabilities_by_mime: Any = context.get_parameter_value(
            OpenFileChainSupport.CAPABILITY_BY_MIME_KEY
        )
        if capabilities_by_mime is None:
            return None
        if not isinstance(capabilities_by_mime, dict):
            raise TypeError(
                f"'{OpenFileChainSupport.CAPABILITY_BY_MIME_KEY}' must map MIME "
                f"types to capability classes; got {type(capabilities_by_mime)!r}."
            )

        if mime_type is None or mime_type not in capabilities_by_mime:
            return None

        capability_type: Any = capabilities_by_mime[mime_type]
        if not inspect.isclass(capability_type) or not issubclass(
            capability_type, CapabilityPort
        ):
            raise TypeError(
                f"'{OpenFileChainSupport.CAPABILITY_BY_MIME_KEY}' entry for "
                f"'{mime_type}' must be a capability class; got {capability_type!r}."
            )
        return capability_type

    def _run_chain(self, context: CliContextPort) -> Dict[str, Dict[str, object]]:
        """Delegate opening to the chain declared in the standard statechart.

        Args:
            context: Context shared with chain responsibilities, including
                the file path and the MIME type already retrieved.

        Returns:
            The dictionary returned by ``worker.work()``, keyed by executed
            responsibility IDs. It may be empty; the caller decides whether
            missing results are acceptable.

        Construct a fresh worker with the ``OpenFileChainSupport`` contract,
        a ``NullLogRepository``, and the configured root packages. Locate
        ``standard_open_file_chain.yaml`` in the ``open_file`` machine package.
        The YAML controls states, guards, and actions; the worker discovers
        classes, evaluates their conditions, and executes the requested
        responsibilities. This method does not imply a fixed execution order
        or that exactly one responsibility runs.

        Statechart lookup, reading, and interpretation errors, missing
        responsibilities, and execution failures propagate. The worker also
        rejects a chain that stops without completing every region. This
        method does not write the aggregate audit event.
        """
        worker: ChainOfResponsibilityWorkerAdapter = ChainOfResponsibilityWorkerAdapter(
            support=OpenFileChainSupport,
            context=context,
            logger=NullLogRepository(),
            statechart_file_path=StatechartLocator.locate(
                "ontobdc.storage.plugin.machine.open_file",
                "standard_open_file_chain.yaml",
            ),
            root_packages=self._root_packages,
        )
        return worker.work()

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        """Compute the ETL event destination without accessing the filesystem.

        Args:
            container_path: Container used as the base path. This method does
                not expand or resolve it, or check whether it exists.

        Returns:
            A path under ``.__ontobdc__/<ETL directory>/storage/open_file/file``
            using the filename declared by ``cls.ETL_EVENT_FILE_NAME``. In
            this class, it is ``__file_opening_strategy_found__.json``.

        The ETL directory name comes from ``EtlDirectoryContract.DIRECTORY_NAME``.
        No directories or files are created. Because the filename is read
        from ``cls``, subclasses can change it through their event filename
        constant.
        """
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / "storage"
            / "open_file"
            / "file"
            / cls.ETL_EVENT_FILE_NAME
        )

    @classmethod
    def _write_event(
        cls,
        container_path: Path,
        results: Dict[str, Dict[str, object]],
    ) -> Path:
        """Write the aggregate event and replace the destination file.

        Args:
            container_path: Container passed to ``event_path`` to determine
                the destination.
            results: Results keyed by strategy identifiers. This method
                neither checks success nor modifies this dictionary.

        Returns:
            The final file path after replacement with the temporary file.

        Create the necessary parent directories and construct an object with
        ``state`` set to ``cls.STATE_NAME``, ``strategies`` containing the
        keys of ``results`` in insertion order, and ``results`` containing the
        complete results. Serialize as UTF-8 with two-space indentation,
        sorted object keys, preserved Unicode characters, and a trailing
        newline. Values not directly JSON-serializable are converted with
        ``str``; this textual representation may lose their original type.

        First write ``.<event filename>.tmp`` in the same directory, then use
        ``Path.replace`` to replace the existing destination. Replacement
        avoids exposing partially written JSON in the final file, but this
        method provides no locking, per-call temporary filenames, or
        ``fsync``. Concurrent calls share the temporary path, and a failure
        may leave it on disk. The file represents the latest write, not an
        append-only event history.

        Raises:
            OSError: Directory creation, writing, or replacement failed.
            ValueError: Serialization failed, for example due to a circular
                reference.

        Other serialization errors also propagate. There is no temporary-file
        cleanup on failure or rollback of strategy effects.
        """
        event_path = cls.event_path(container_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        event = {
            "state": cls.STATE_NAME,
            "strategies": list(results.keys()),
            "results": results,
        }
        temporary_path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(
            json.dumps(
                event,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(event_path)
        return event_path
