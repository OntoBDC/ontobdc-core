
import os
from rdflib import Graph, Literal, Namespace, URIRef, RDF
from typing import List, Dict, Any, Optional
from ontobdc.shared.adapter.util import to_camel_case, to_pascal_case
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix

OBDC: Namespace = get_ontology_by_prefix("obdc")
BASE_URI: Namespace = Namespace("urn:ontobdc:context/")


class CliContextAdapter(CliContextPort):
    def __init__(self, argv: List[str] = []):
        self._raw_argv = argv
        self._unprocessed_args = argv[1:]
        self._context_individual: Optional[URIRef] = None

        self._resolved_parameters: Dict[str, Any] = {}

        from ontobdc.cli import get_config_dir
        self._context_file: str = os.path.join(get_config_dir(), "context.ttl")

        self._graph: Graph = Graph()
        try:
            self._load()
        except FileNotFoundError:
            pass

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
        return self._raw_argv

    @property
    def unprocessed_args(self) -> List[str]:
        return self._unprocessed_args

    @property
    def is_capability_targeted(self) -> bool:
        return self.target_capability_id is not None

    @property
    def target_capability_id(self) -> str | None:
        return self.get_parameter_value("capability_id")

    @property
    def root_path(self) -> str:
        """
        Returns the root path of the repository.
        """
        from ontobdc.cli import config_data

        cfg = config_data() or {}
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
        """
        camel_case_key: str = to_camel_case(param_key)
        prop_uri: URIRef = OBDC[camel_case_key]

        if isinstance(param_value, str):
            param_value = Literal(param_value)

        elif isinstance(param_value, (int, float)):
            param_value = Literal(param_value)

        elif isinstance(param_value, bool):
            param_value = Literal(param_value)

        elif isinstance(param_value, URIRef):
            param_value = param_value

        elif isinstance(param_value, object):
            self._resolved_parameters[to_camel_case(param_key)] = param_value
            return

        else:
            raise ValueError(f"Invalid parameter value type: {type(param_value)}")

        # Remove existing value
        self._graph.remove((self._context_individual, prop_uri, None))
        # Add new value
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
        for param_key in param_keys:
            if param_key in self._unprocessed_args:
                self._unprocessed_args.remove(param_key)

    def reload(self) -> None:
        """
        Reloads the context from the file.
        """
        self._load()

    def _load(self) -> None:
        self._graph.parse(self._context_file, format="turtle")
        for s in self._graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            self._context_individual = s
            break

    def _save(self) -> None:
        """
        Saves the graph back to the context file.
        """
        self._graph.serialize(destination=self._context_file, format="turtle")
