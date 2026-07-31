import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml
from rdflib import Graph, Literal, Namespace, URIRef

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.adapter.util import is_valid_uri
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class EntityUriStrategy(ParameterPort, CliContextStrategyPort):
    """Resolve an entity name or URI to the canonical entity URI."""

    IFC_SCHEMA_NAMESPACE: Namespace = Namespace(
        "http://ifcowl.openbimstandards.org/IFC4#"
    )
    ENTITY_ALIAS_PREDICATE: URIRef = URIRef(
        "http://ontobdc.org/ontology/domain/ns.ttl#entityAlias"
    )
    BRASIDATACENTER_INDEX_URL: str = (
        "https://raw.githubusercontent.com/"
        "Brasidata/brasidatacenter/master/ontology/index.yaml"
    )
    BRASIDATACENTER_CACHE_PATH: Path = Path(
        ".__ontobdc__/cache/ontology/index.yaml"
    )

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.context.capability.incoming.entity",
        version="0.2.0",
        name="entity",
        description=(
            "Resolve an entity URI directly, an IFC entity name against the "
            "IFC4 schema, or an alias declared in context.ttl or Brasidatacenter."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=URIRef,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_entity_value: str = str(
            context.get_parameter_value("entity") or ""
        ).strip()
        if not raw_entity_value:
            return context

        if self._looks_like_uri(raw_entity_value):
            if not self._is_valid_entity_uri(raw_entity_value):
                raise ValueError(f"Invalid entity URI: {raw_entity_value}")

            context.set_parameter_value(
                "entity_uri",
                URIRef(raw_entity_value),
            )
            return context

        if raw_entity_value[:3].casefold() == "ifc":
            ifc_entity_name: str = self._normalize_ifc_entity_name(
                raw_entity_value
            )
            ifc_entity_uri: str = str(
                self.IFC_SCHEMA_NAMESPACE[ifc_entity_name]
            )
            if not self._is_valid_entity_uri(ifc_entity_uri):
                raise ValueError(
                    f"Could not build a valid IFC entity URI for: "
                    f"{raw_entity_value}"
                )

            context.set_parameter_value(
                "entity_uri",
                URIRef(ifc_entity_uri),
            )
            return context

        resolved_entity_value: Optional[str] = (
            self._resolve_entity_from_aliases(
                context,
                raw_entity_value,
            )
        )
        if resolved_entity_value is None:
            raise ValueError(
                f"Entity alias '{raw_entity_value}' was not found in "
                "context.ttl or Brasidatacenter ontology/index.yaml."
            )

        if not self._is_valid_entity_uri(resolved_entity_value):
            raise ValueError(
                f"Entity alias '{raw_entity_value}' resolved to an invalid URI: "
                f"{resolved_entity_value}"
            )

        context.set_parameter_value(
            "entity_uri",
            URIRef(resolved_entity_value),
        )
        return context

    def _looks_like_uri(self, value: str) -> bool:
        normalized_value: str = str(value or "").strip()
        if not normalized_value:
            return False

        return (
            "://" in normalized_value
            or normalized_value.casefold().startswith("urn:")
        )

    def _is_valid_entity_uri(self, value: str) -> bool:
        normalized_value: str = str(value or "").strip()
        if not normalized_value:
            return False

        return bool(is_valid_uri(normalized_value))

    def _normalize_ifc_entity_name(self, value: str) -> str:
        normalized_value: str = str(value or "").strip()
        suffix: str = normalized_value[3:].strip()
        if not suffix:
            raise ValueError("IFC entity name cannot be empty.")

        return f"Ifc{suffix}"

    def _resolve_entity_from_aliases(
        self,
        context: CliContextPort,
        raw_entity_value: str,
    ) -> Optional[str]:
        normalized_alias: str = self._normalize_alias(raw_entity_value)
        if not normalized_alias:
            return None

        context_match: Optional[str] = self._resolve_unique_match(
            candidates=self._collect_context_candidates(context),
            normalized_alias=normalized_alias,
            source_label="context.ttl",
            raw_entity_value=raw_entity_value,
        )
        if context_match is not None:
            return context_match

        return self._resolve_unique_match(
            candidates=self._collect_registered_candidates(context),
            normalized_alias=normalized_alias,
            source_label="Brasidatacenter ontology/index.yaml",
            raw_entity_value=raw_entity_value,
        )

    def _resolve_unique_match(
        self,
        candidates: List[Dict[str, Any]],
        normalized_alias: str,
        source_label: str,
        raw_entity_value: str,
    ) -> Optional[str]:
        matches: List[str] = []

        for candidate in candidates:
            entity_uri: str = str(
                candidate.get("entity_uri") or ""
            ).strip()
            if not entity_uri:
                continue

            aliases: List[Any] = list(candidate.get("aliases", []))
            if not any(
                self._normalize_alias(alias) == normalized_alias
                for alias in aliases
            ):
                continue

            if entity_uri not in matches:
                matches.append(entity_uri)

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            raise ValueError(
                f"Entity alias '{raw_entity_value}' is ambiguous in "
                f"{source_label}: {', '.join(sorted(matches))}"
            )

        return None

    def _collect_context_candidates(
        self,
        context: CliContextPort,
    ) -> List[Dict[str, Any]]:
        context_file_path: Path = (
            Path(str(context.root_path))
            / ".__ontobdc__"
            / "context.ttl"
        )
        if not context_file_path.exists() or not context_file_path.is_file():
            return []

        context_graph: Graph = Graph()
        context_graph.parse(str(context_file_path), format="turtle")

        candidates: List[Dict[str, Any]] = []
        for subject in set(
            context_graph.subjects(self.ENTITY_ALIAS_PREDICATE, None)
        ):
            if not isinstance(subject, URIRef):
                continue

            entity_uri: str = str(subject).strip()
            if not entity_uri:
                continue

            aliases: List[str] = [self._local_name(entity_uri)]
            for alias_object in context_graph.objects(
                subject,
                self.ENTITY_ALIAS_PREDICATE,
            ):
                alias_value: str = self._object_to_string(alias_object)
                if alias_value:
                    aliases.append(alias_value)

            candidates.append(
                {
                    "entity_uri": entity_uri,
                    "aliases": aliases,
                    "source": str(context_file_path),
                }
            )

        return candidates

    def _collect_registered_candidates(
        self,
        context: CliContextPort,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = self._load_brasidatacenter_index(context)
        entity_registry: Any = payload.get("entity", {})
        if not isinstance(entity_registry, dict):
            return []

        aliases_by_uri: Dict[str, List[str]] = {}

        domain_payload: Any
        for domain_payload in entity_registry.values():
            if not isinstance(domain_payload, dict):
                continue

            raw_aliases: Any = domain_payload.get("aliases", [])
            if isinstance(raw_aliases, dict):
                raw_aliases = [raw_aliases]
            if not isinstance(raw_aliases, list):
                continue

            alias_entry: Any
            for alias_entry in raw_aliases:
                if not isinstance(alias_entry, dict):
                    continue

                alias: Any
                entity_uri: Any
                for alias, entity_uri in alias_entry.items():
                    normalized_uri: str = str(entity_uri or "").strip()
                    normalized_alias: str = str(alias or "").strip()
                    if not normalized_uri or not normalized_alias:
                        continue

                    aliases_by_uri.setdefault(
                        normalized_uri,
                        [],
                    ).append(normalized_alias)

        return [
            {
                "entity_uri": entity_uri,
                "aliases": aliases,
                "source": self.BRASIDATACENTER_INDEX_URL,
            }
            for entity_uri, aliases in aliases_by_uri.items()
        ]

    def _load_brasidatacenter_index(
        self,
        context: CliContextPort,
    ) -> Dict[str, Any]:
        override_path_value: Any = context.get_parameter_value(
            "brasidatacenter_index_path"
        )
        override_path: Optional[Path] = None
        if isinstance(override_path_value, (str, Path)):
            normalized_override: str = str(override_path_value).strip()
            if normalized_override:
                override_path = Path(normalized_override).expanduser()

        if override_path is not None:
            if not override_path.exists() or not override_path.is_file():
                raise FileNotFoundError(
                    f"Brasidatacenter index file not found: {override_path}"
                )
            return self._parse_yaml_mapping(
                override_path.read_text(encoding="utf-8"),
                str(override_path),
            )

        cache_path: Path = (
            Path(str(context.root_path))
            / self.BRASIDATACENTER_CACHE_PATH
        )

        try:
            request = Request(
                self.BRASIDATACENTER_INDEX_URL,
                headers={
                    "Accept": "application/yaml, text/yaml, text/plain",
                    "User-Agent": "OntoBDC",
                },
            )
            with urlopen(request, timeout=30) as response:
                content: str = response.read().decode("utf-8")

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content, encoding="utf-8")
            return self._parse_yaml_mapping(
                content,
                self.BRASIDATACENTER_INDEX_URL,
            )
        except (OSError, TimeoutError, URLError) as exc:
            if cache_path.exists() and cache_path.is_file():
                return self._parse_yaml_mapping(
                    cache_path.read_text(encoding="utf-8"),
                    str(cache_path),
                )

            raise RuntimeError(
                "Could not load Brasidatacenter ontology/index.yaml "
                "and no local cache is available."
            ) from exc

    def _parse_yaml_mapping(
        self,
        content: str,
        source: str,
    ) -> Dict[str, Any]:
        try:
            payload: Any = yaml.safe_load(content) or {}
        except yaml.YAMLError as exc:
            raise ValueError(
                f"Invalid Brasidatacenter YAML in {source}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"Brasidatacenter YAML root must be a mapping: {source}"
            )

        return payload

    def _normalize_alias(self, value: Any) -> str:
        normalized_value: str = unicodedata.normalize(
            "NFKD",
            str(value or "").strip(),
        )
        ascii_value: str = normalized_value.encode(
            "ascii",
            "ignore",
        ).decode("ascii")
        return re.sub(
            r"[^a-z0-9]+",
            "",
            ascii_value.casefold(),
        )

    def _local_name(self, value: str) -> str:
        normalized_value: str = str(value or "").strip()
        if "#" in normalized_value:
            return normalized_value.rsplit("#", 1)[-1].strip()

        return normalized_value.rstrip("/").rsplit("/", 1)[-1].strip()

    def _object_to_string(self, obj: Any) -> str:
        if isinstance(obj, Literal):
            return str(obj.toPython()).strip()

        return str(obj).strip()
