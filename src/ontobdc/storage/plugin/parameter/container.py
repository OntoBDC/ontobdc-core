import os
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.cli.domain.port.context import (
    CliContextPort,
    CliContextStrategyPort,
    PromptChoiceAwarePort,
)
from ontobdc.cli.domain.port.logger import (
    LoggerAwarePort,
    LogStrategyContainerPort,
)
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.old_repository import LoadedStorageGraphPort
from ontobdc.shared.domain.port.parameter import ParameterPort
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort


OBDC = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")


class ContainerIdStrategy(
    ParameterPort,
    CliContextStrategyPort,
    PromptChoiceAwarePort,
    LoggerAwarePort,
):
    """Resolve supported container selectors to a registered ID and path."""

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.storage.capability.incoming.container",
        version="0.12.0",
        name="container_id",
        description=(
            "Resolve --container-id, --container, or the current working "
            "directory to a registered OntoBDC container."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=ContainerRepositoryPort,
    )

    def __init__(self) -> None:
        self._log_strategy: Optional[LogStrategyContainerPort] = None
        self._prompt_choice: Optional[Callable] = None

    def set_log_strategy(
        self,
        log_strategy: LogStrategyContainerPort,
    ) -> None:
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: Callable) -> None:
        self._prompt_choice = prompt_choice

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        return self._log_strategy

    def execute(self, context: CliContextPort) -> CliContextPort:
        root_path = getattr(context, "root_path", None)
        registered = tuple(self._registered_containers(root_path))
        raw_args = getattr(context, "raw_args", None)

        if isinstance(raw_args, list):
            if "--container-id" in raw_args:
                explicit_id = self._context_value(context, "container_id")
                if explicit_id is not None:
                    match = self._find_by_id(explicit_id, registered)
                    if match is not None:
                        self._bind(context, *match)
                    else:
                        self._clear(context)
                return context

            if "--container" in raw_args:
                selector = self._context_value(context, "container")
                if selector is not None:
                    match = self._find_by_id(selector, registered)
                    if match is None:
                        match = self._find_by_path(selector, registered)
                    if match is not None:
                        self._bind(context, *match)
                    else:
                        self._clear(context)
                return context

            match = self._resolve_container_for_current_directory(
                Path(os.getcwd()),
                registered,
            )
            if match is not None:
                self._bind(context, *match)
            return context

        # Programmatic contexts do not expose raw CLI arguments. Preserve
        # support for values injected directly by callers.
        explicit_id = self._context_value(context, "container_id")
        if explicit_id is not None:
            match = self._find_by_id(explicit_id, registered)
            if match is not None:
                self._bind(context, *match)
            else:
                self._clear(context)
            return context

        generic_selector = self._context_value(context, "container")
        if generic_selector is not None:
            match = self._find_by_id(generic_selector, registered)
            if match is None:
                match = self._find_by_path(generic_selector, registered)
            if match is not None:
                self._bind(context, *match)
            else:
                self._clear(context)
            return context

        match = self._resolve_container_for_current_directory(
            Path(os.getcwd()),
            registered,
        )
        if match is not None:
            self._bind(context, *match)

        return context

    @classmethod
    def _resolve_container_for_current_directory(
        cls,
        current_directory: Path,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path]]:
        """Pick the most specific container for an implicit invocation.

        When the caller points at a filesystem location (typically the CWD)
        without any explicit selector, resolution is:

        1. Walk **upwards** from the current directory looking for any
           on-disk container metadata (``.__ontobdc__/container.ttl``).
           This captures containers that exist locally on the filesystem
           but are not yet (or no longer) registered in the storage index.

        2. Match the current directory against every registered container
           path, including ancestor containers that would otherwise shadow
           a more specific local directory.

        3. Merge the two lists and return the container with the deepest
           path (most parts), which is always the most specific match.
        """
        candidates: List[Tuple[str, Path]] = []

        on_disk = cls._find_from_current_container_from_root(current_directory)
        if on_disk is not None:
            candidates.append(on_disk)

        registered_match = cls._find_by_path(current_directory, registered)
        if registered_match is not None:
            candidates.append(registered_match)

        if not candidates:
            return None

        return max(candidates, key=lambda item: len(item[1].parts))

    @classmethod
    def _find_from_current_container_from_root(
        cls,
        starting_path: Path,
    ) -> Optional[Tuple[str, Path]]:
        """Variant of :meth:`_find_from_current_container` that accepts an
        arbitrary starting directory instead of hard-coding ``os.getcwd()``.
        """
        current_path = starting_path.expanduser().resolve()

        for candidate in (current_path, *current_path.parents):
            container_file = candidate / ".__ontobdc__" / "container.ttl"
            if not container_file.is_file():
                continue

            graph = Graph()
            graph.parse(str(container_file), format="turtle")
            subjects = [
                subject
                for subject in graph.subjects(
                    RDF.type,
                    OBDC.DataContainer,
                )
                if isinstance(subject, URIRef)
            ]
            if len(subjects) != 1:
                raise ValueError(
                    "Container metadata must describe exactly one "
                    f"DataContainer: {container_file}"
                )

            subject = subjects[0]
            identifier = graph.value(subject, DCTERMS.identifier)
            container_id = str(identifier or subject).strip()
            if not container_id:
                raise ValueError(
                    f"Container identifier not found: {container_file}"
                )
            return container_id, candidate.resolve()

        return None

    @staticmethod
    def _find_from_current_container() -> Optional[Tuple[str, Path]]:
        return ContainerIdStrategy._find_from_current_container_from_root(
            Path(os.getcwd()),
        )

    @staticmethod
    def _context_value(
        context: CliContextPort,
        name: str,
    ) -> Optional[str]:
        if not context.has_parameter(name):
            return None
        value = context.get_parameter_value(name)
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _registered_containers(
        root_path: Optional[str] = None,
    ) -> Iterable[Tuple[str, Path]]:
        try:
            storage_file = get_storage_file(root_path)
        except Exception:
            return ()

        if not os.path.isfile(storage_file):
            return ()

        try:
            storage_graph: LoadedStorageGraphPort = LoadedStorageGraph(
                storage_file
            )
            return tuple(
                (
                    str(subject),
                    Path(container_config_dir)
                    .expanduser()
                    .parent
                    .resolve(),
                )
                for subject, container_config_dir, _ in storage_graph.containers
            )
        except Exception:
            return ()

    @staticmethod
    def _find_by_id(
        container_id: str,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path]]:
        normalized_id = container_id.strip()
        for registered_id, container_path in registered:
            if registered_id == normalized_id:
                return registered_id, container_path
        return None

    @classmethod
    def _find_by_path(
        cls,
        selector: object,
        registered: Iterable[Tuple[str, Path]],
    ) -> Optional[Tuple[str, Path]]:
        candidate = cls._resolve_path(selector)
        # Must actually exist — otherwise any non-path selector resolves relative to cwd and spuriously matches the current container.
        if candidate is None or not candidate.exists():
            return None

        matches = []
        for registered_id, container_path in registered:
            if (
                candidate == container_path
                or candidate.is_relative_to(container_path)
            ):
                matches.append((registered_id, container_path))

        if not matches:
            return None

        return max(matches, key=lambda item: len(item[1].parts))

    @staticmethod
    def _resolve_path(selector: object) -> Optional[Path]:
        try:
            candidate = Path(str(selector)).expanduser()
            if not candidate.is_absolute():
                candidate = Path(os.getcwd()) / candidate
            return candidate.resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None

    @staticmethod
    def _bind(
        context: CliContextPort,
        container_id: str,
        container_path: Path,
    ) -> None:
        context.set_parameter_value("container_id", container_id)
        context.set_parameter_value("container_path", str(container_path))

    @staticmethod
    def _clear(context: CliContextPort) -> None:
        """Drop a stale container_id/container_path rather than leaving an unmatched explicit selector silently falling back to whatever was previously resolved."""
        context.delete_parameter("container_id")
        context.delete_parameter("container_path")

    @classmethod
    def _infer_container_id_from_current_path(cls) -> Optional[str]:
        """Retain the helper used by callers outside the strategy pipeline."""
        match = cls._find_by_path(
            Path(os.getcwd()),
            cls._registered_containers(),
        )
        return match[0] if match is not None else None
