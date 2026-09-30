from typing import Any, ClassVar, Dict, List
from pathlib import Path
from datetime import datetime, timezone

import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, XSD

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class CliInitStateTransitionHandler:
    """Bootstrap an OntoBDC project through the canonical init states."""

    _STATE_SEQUENCE: ClassVar[List[str]] = [
        "__ontobdc_directory_ready__",
        "__engine_ready__",
        "__storage_index_healthy__",
        "__execution_context_healthy__",
        "__config_adapter_ready__",
        "__brand_ready__",
    ]
    _DEFAULT_BRAND: ClassVar[Dict[str, str]] = {
        "name": "OntoBDC",
        "mark_svg": (
            '<svg viewBox="0 0 64 64" aria-hidden="true">'
            '<circle cx="32" cy="32" r="25" fill="none" '
            'stroke="currentColor" stroke-width="8"/>'
            '<circle cx="32" cy="32" r="7" fill="currentColor"/></svg>'
        ),
        "logotype_svg": (
            '<svg viewBox="0 0 260 64" aria-hidden="true">'
            '<circle cx="32" cy="32" r="23" fill="none" '
            'stroke="var(--onto-theme-accent, currentColor)" '
            'stroke-width="7"/>'
            '<circle cx="32" cy="32" r="6" '
            'fill="var(--onto-theme-accent, currentColor)"/>'
            '<text x="68" y="42" fill="currentColor" '
            'font-family="system-ui, sans-serif" font-size="31" '
            'font-weight="700">OntoBDC</text></svg>'
        ),
        "slogan": "Data with Brains",
    }
    _OBDC: ClassVar[Namespace] = Namespace(
        "http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#"
    )
    _CT: ClassVar[Namespace] = Namespace(
        "http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
    )
    _PROV: ClassVar[Namespace] = Namespace("http://www.w3.org/ns/prov#")
    _CONTEXT: ClassVar[Namespace] = Namespace("urn:ontobdc:context/")
    _STORAGE_IDENTIFIER: ClassVar[str] = "urn:ontobdc:storage/local"

    def __init__(
        self,
        context: CliContextPort,
        logger: LogRepositoryPort | None = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()

    def execute(self) -> CommandResponse:
        root_path: Path = Path(self._context.root_path).expanduser().resolve()
        ontobdc_directory: Path = root_path / ".__ontobdc__"
        ontobdc_directory.mkdir(parents=True, exist_ok=True)

        self._write_config(root_path, ontobdc_directory / "config.yaml")
        self._write_context(root_path, ontobdc_directory / "context.ttl")
        self._write_storage(root_path, ontobdc_directory / "storage.ttl")

        self._logger.log_notice("OntoBDC init bootstrap finished successfully.")
        return CommandResponse(
            title="Init",
            description="Bootstrap initialization executed successfully.",
            content={
                "root_path": str(root_path),
                "ontobdc_directory": str(ontobdc_directory),
                "current_state": self._STATE_SEQUENCE[-1],
                "visited_states": list(self._STATE_SEQUENCE),
            },
        )

    def _write_config(self, root_path: Path, config_file: Path) -> None:
        config: Dict[str, Any] = {}
        if config_file.is_file():
            loaded_config: Any = yaml.safe_load(
                config_file.read_text(encoding="utf-8")
            )
            if isinstance(loaded_config, dict):
                config = loaded_config

        directory: Any = config.get("directory")
        if not isinstance(directory, dict):
            directory = {}
        root: Any = directory.get("root")
        if not isinstance(root, dict):
            root = {}
        root["absolute_path"] = str(root_path)
        directory["root"] = root
        config["directory"] = directory

        engine: Any = config.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            config["engine"] = "venv"

        brand: Any = config.get("brand")
        if not isinstance(brand, dict):
            brand = {}
        brand_key: str
        brand_value: str
        for brand_key, brand_value in self._DEFAULT_BRAND.items():
            current_value: Any = brand.get(brand_key)
            if not isinstance(current_value, str) or not current_value.strip():
                brand[brand_key] = brand_value
        config["brand"] = brand

        config_file.write_text(
            yaml.safe_dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def _write_context(self, root_path: Path, context_file: Path) -> None:
        if self._is_valid_graph(context_file):
            return

        graph: Graph = Graph()
        graph.bind("", self._CONTEXT)
        graph.bind("obdc", self._OBDC)
        graph.bind("owl", OWL)
        context_reference: URIRef = self._CONTEXT["CurrentContext"]
        graph.add((context_reference, RDF.type, self._OBDC.ExecutionContext))
        graph.add((context_reference, RDF.type, OWL.NamedIndividual))
        graph.add((context_reference, self._OBDC.contextLanguage, Literal("en")))
        graph.add(
            (
                context_reference,
                self._OBDC.projectRootLocation,
                URIRef(root_path.as_uri()),
            )
        )
        graph.serialize(destination=context_file, format="turtle")

    def _write_storage(self, root_path: Path, storage_file: Path) -> None:
        if self._is_valid_graph(storage_file):
            return

        graph: Graph = Graph()
        graph.bind("dcterms", DCTERMS)
        graph.bind("ct", self._CT)
        graph.bind("prov", self._PROV)
        graph.bind("xsd", XSD)
        graph.bind("obdc", self._OBDC)
        storage_reference: URIRef = URIRef(self._STORAGE_IDENTIFIER)
        created_at: Literal = Literal(
            datetime.now(timezone.utc).isoformat(),
            datatype=XSD.dateTime,
        )
        graph.add((storage_reference, RDF.type, self._OBDC.DataStorage))
        graph.add(
            (
                storage_reference,
                DCTERMS.identifier,
                Literal(self._STORAGE_IDENTIFIER),
            )
        )
        graph.add(
            (
                storage_reference,
                DCTERMS.title,
                Literal("The Main Storage Index", lang="en"),
            )
        )
        graph.add((storage_reference, self._CT.creationDate, created_at))
        graph.add(
            (
                storage_reference,
                self._CT.description,
                Literal(
                    f"Main storage container for project at "
                    f"{root_path.name or root_path.as_posix()}",
                    lang="en",
                ),
            )
        )
        graph.add(
            (storage_reference, self._PROV.atLocation, URIRef(root_path.as_uri()))
        )
        graph.serialize(destination=storage_file, format="turtle")

    def _is_valid_graph(self, graph_file: Path) -> bool:
        if not graph_file.is_file():
            return False

        try:
            Graph().parse(graph_file, format="turtle")
        except Exception:
            return False
        return True
