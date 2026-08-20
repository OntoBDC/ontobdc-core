
import os
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional
from ontobdc.shared.adapter.util import to_camel_case
from rdflib import Graph, Literal, Namespace, URIRef, RDF
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter

BASE_URI: Namespace = Namespace("urn:ontobdc:context/")


class CliContextAdapter(CliContextPort):
    """
    Adapter for the CLI context, handling arguments, parameter resolution, and state persistence via RDF graph.
    """

    # Runtime-only parameters that MUST NEVER be persisted on disk inside
    # ``context.ttl``.  These values only make sense for the current CLI
    # invocation: they control verbosity, logging, UI chrome, execution
    # targeting etc. and must not leak into the shared container state that
    # survives across runs.  Any transient CLI flag added in the future
    # should be appended here so the persistence layer automatically ignores
    # it without further code changes.
    TRANSIENT_PARAMETER_KEYS: FrozenSet[str] = frozenset({
        "log_level",
        "verbose",
        "quiet",
        "no_color",
        "force",
        "non_interactive",
        "capability_id",
        "raw_args",
    })

    def __init__(self, argv: List[str] = [], root_dir: str = None):
        self._raw_argv = argv

        self._config_adapter: ConfigDataPort = self._make_config_data_adapter(root_dir)

        self._unprocessed_args = argv[1:]
        self._context_individual: Optional[URIRef] = None

        self._resolved_parameters: Dict[str, Any] = {}
        self._context_file: Optional[Path] = None
        try:
            self._context_file = self._config_adapter.config_dir / "context.ttl"
        except ProjectRootDirectoryNotSetError:
            pass

        self._graph: Graph = Graph()
        try:
            self._load()
        except (FileNotFoundError, PermissionError):
            pass

        if self._context_individual is None:
            self._context_individual = URIRef(BASE_URI["execution"])
            self._graph.add((self._context_individual, RDF.type, OBDC.ExecutionContext))

    @property
    def language(self) -> Optional[str]:
        """
        Returns the language of the context.
        Defaults to the system's language.
        :param fallback: The fallback language if the system's language is not available.
        :return: The language of the context, or the fallback if not available.
        """
        language = self.get_parameter_value("context_language")
        if language:
            return language

        return None

    @property
    def raw_args(self) -> List[str]:
        """
        Gets the raw arguments passed to the CLI.
        """
        return self._raw_argv

    @property
    def unprocessed_args(self) -> List[str]:
        """
        Gets the list of arguments that have not yet been processed.
        """
        return self._unprocessed_args

    @property
    def is_capability_targeted(self) -> bool:
        """
        Checks if a specific capability is targeted in the current context.
        """
        return self.target_capability_id is not None

    @property
    def target_capability_id(self) -> str | None:
        """
        Gets the ID of the targeted capability, if any.
        """
        return self.get_parameter_value("capability_id")

    @property
    def root_path(self) -> str:
        """
        Returns the root path of the repository.
        """
        try:
            cfg = self._config_adapter.all or {}
        except ProjectRootDirectoryNotSetError:
            return os.getcwd()
        directory = cfg.get("directory") or {}
        root = directory.get("root") or {}
        absolute_path = root.get("absolute_path")
        if absolute_path:
            return absolute_path

        return os.getcwd()

    def get_individual(self, class_key: str) -> URIRef:
        """
        Returns the value of a parameter.
        """
        pascal_case_key: str = to_pascal_case(class_key)
        prop_uri: URIRef = OBDC[pascal_case_key]
        for s, _, o in self._graph:
            if s == prop_uri:
                return URIRef(o)

        return None

    def set_parameter_value(self, param_key: str, param_value: Any) -> None:
        """
        Sets the value of a parameter.

        Transient parameters (see :attr:`TRANSIENT_PARAMETER_KEYS`) are only
        kept in process memory so they remain available to the current CLI
        invocation via :meth:`get_parameter_value`, but are NEVER written
        into the on-disk ``context.ttl``.  Persistent parameters continue to
        be serialized through the RDF graph exactly as before.
        """
        camel_case_key: str = to_camel_case(param_key)

        # Ensure any pre-existing value for this parameter is dropped from
        # the graph before we decide whether the *new* value is persisted or
        # transient.  Without this, a persistent bytes/stale value left by
        # an older version would survive forever on disk even after the
        # caller supplied a fresh transient (or just different) value, and
        # rdflib's turtle serializer would then emit both side-by-side on
        # the same predicate, producing syntactically broken output such as
        # a trailing ``;\`` escape or literal ``b'...'`` bytes reprs.
        prop_uri: URIRef = OBDC[camel_case_key]
        if self._context_individual is not None:
            self._graph.remove((self._context_individual, prop_uri, None))

        if param_key in self.TRANSIENT_PARAMETER_KEYS:
            self._resolved_parameters[camel_case_key] = param_value
            self._save()
            return

        if isinstance(param_value, bytes):
            try:
                decoded_value: str = param_value.decode("utf-8")
            except (AttributeError, UnicodeDecodeError):
                decoded_value = param_value.decode("utf-8", errors="replace")
            param_value = Literal(decoded_value)

        elif isinstance(param_value, str):
            param_value = Literal(param_value)

        elif isinstance(param_value, (int, float)):
            param_value = Literal(param_value)

        elif isinstance(param_value, bool):
            param_value = Literal(param_value)

        elif isinstance(param_value, URIRef):
            param_value = param_value

        elif isinstance(param_value, object):
            self._resolved_parameters[camel_case_key] = param_value
            self._save()
            return

        else:
            raise ValueError(f"Invalid parameter value type: {type(param_value)}")

        self._graph.add((self._context_individual, prop_uri, param_value))

        self._save()

    def get_parameter_value(self, param_key: str) -> Optional[Any]:
        """
        Returns the value of a parameter.
        """
        camel_case_key: str = to_camel_case(param_key)
        if camel_case_key in self._resolved_parameters.keys():
            return self._resolved_parameters[camel_case_key]

        prop_uri: URIRef = OBDC[camel_case_key]
        for s, p, o in self._graph:
            if s == self._context_individual and p == prop_uri:
                if isinstance(o, Literal):
                    return o.toPython()

                if isinstance(o, URIRef):
                    return URIRef(o)

                return str(o)

        return None

    def delete_parameter(self, param_key: str) -> None:
        """
        Deletes a parameter from the context.
        """
        camel_case_key: str = to_camel_case(param_key)
        self._resolved_parameters.pop(camel_case_key, None)

        prop_uri: URIRef = OBDC[camel_case_key]
        if self._context_individual is not None:
            self._graph.remove((self._context_individual, prop_uri, None))
            self._save()

    def has_parameter(self, param_key: str) -> bool:
        """
        Returns True if the parameter is set in the context.
        """
        camel_case_key: str = to_camel_case(param_key)
        if camel_case_key in self._resolved_parameters.keys():
            return True

        prop_uri: URIRef = OBDC[camel_case_key]
        for s, p, o in self._graph:
            if s == self._context_individual and p == prop_uri:
                return True

        return False

    def clear_parameters(self, param_keys: List[str]) -> None:
        """
        Clears multiple parameters from the unprocessed arguments list.
        """
        for param_key in param_keys:
            if param_key in self._unprocessed_args:
                self._unprocessed_args.remove(param_key)

    def reload(self) -> None:
        """
        Reloads the context from the file.
        """
        self._load()

    def _load(self) -> None:
        """
        Loads the context graph from the context file.

        Any transient parameter left over from older OntoBDC versions is
        actively purged after deserialization so the persisted state never
        leaks runtime-only values (log level, verbosity flags …) between
        separate CLI invocations.
        """
        if self._context_file is None:
            return

        self._graph.parse(self._context_file.as_uri(), format="turtle")
        for s in self._graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            self._context_individual = s
            break

        if self._context_individual is None:
            return

        for transient_key in self.TRANSIENT_PARAMETER_KEYS:
            prop_uri = OBDC[to_camel_case(transient_key)]
            self._graph.remove((self._context_individual, prop_uri, None))

        if self._context_file is not None:
            self._graph.serialize(destination=self._context_file, format="turtle")

    def _save(self) -> None:
        """
        Saves the graph back to the context file.
        """
        if self._context_file is None:
            return

        self._graph.serialize(destination=self._context_file, format="turtle")

    @classmethod
    def _is_valid_root_dir(cls, root_dir: Optional[str] = None) -> bool:
        if not isinstance(root_dir, str):
            return False

        root_dir_path: Path = Path(root_dir)
        return root_dir_path.exists() and root_dir_path.is_dir()

    @classmethod
    def _make_config_data_adapter(cls, root_dir: Optional[str] = None) -> ConfigDataPort:
        try:
            if cls._is_valid_root_dir(root_dir):
                return ConfigDataAdapter(root_dir)

            return ConfigDataAdapter()

        except ProjectRootDirectoryNotSetError:
            pass

        return UnsetProjectRootConfigDataAdapter()

config_adapter = CliContextAdapter._make_config_data_adapter()
ontology_adapter = OntologyConfigAdapter(config_adapter)

OBDC: Namespace = ontology_adapter.get_ontology_namespace_by_prefix("obdc")
