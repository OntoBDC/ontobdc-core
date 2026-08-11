"""Provisional view-generation operations not yet formalized by OntoBDC.

HARDCODED is the temporary consolidation state for view-generation
operations that still live outside the official publication and dashboard
flow. It is deliberately a holding area: once an operation receives an
official adapter, capability, data contract, and tests, that operation must
leave this module.

Operations currently exclusive to this capability:

* read views/public.yaml as the page configuration;
* render template/index.html.jinja with Jinja2 StrictUndefined;
* render inline bold markup and line breaks from YAML;
* discover project.ttl below .__ontobdc__/__infobim__;
* extract IfcSite.RefLatitude and IfcSite.RefLongitude;
* convert IfcCompoundPlaneAngleMeasure values to decimal coordinates,
  including RDF collections, IFC hasContents/hasNext linked lists, and
  degrees/minutes/seconds/millionths;
* write the coordinates to
  .__ontobdc__/asset/infobim-view/js/project_runtime_data.js;
* count indexed files from ro-crate-metadata.json, including semantic
  recognition of file entities;
* present the project path as the relative value ./; and
* optionally resolve the project root from INFOBIM_PROJECT_ROOT.

The official flow already performs equivalent operations for generating
index.html, reading project identity and description, counting indexed files,
formatting the generation date, handling relative local navigation, writing
files atomically, and publishing dashboard assets. Those equivalents must
not be treated as reasons to duplicate additional behavior here.

The remaining functional delta is therefore YAML/Jinja configuration, IFC
coordinate extraction, and generation of project_runtime_data.js. The other
code in this module is retained only where it supports those provisional
operations or preserves the currently approved output.
"""


from __future__ import annotations

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.domain.machine.state import ContainerViewProcessState

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import unquote, urlparse

METADATA_DIRECTORY = ".__ontobdc__"
RO_CRATE_FILENAME = "ro-crate-metadata.json"
CONTAINER_ONTOLOGY_FILENAME = "container.ttl"
PROJECT_ROOT_ENVIRONMENT_VARIABLE = "INFOBIM_PROJECT_ROOT"
PROV_AT_LOCATION_URI = "http://www.w3.org/ns/prov#atLocation"
IFC_REF_LATITUDE_LOCAL_NAME = "refLatitude_IfcSite"
IFC_REF_LONGITUDE_LOCAL_NAME = "refLongitude_IfcSite"

_AT_LOCATION_PATTERN = re.compile(
    rf"(?:prov:atLocation|<{re.escape(PROV_AT_LOCATION_URI)}>)\s+"
    r"(?:<(?P<uri>[^>]+)>|\"(?P<literal>(?:\\.|[^\"])*)\")",
    re.IGNORECASE | re.MULTILINE,
)


class ProjectInformationError(RuntimeError):
    """Raised when generated project information cannot be resolved."""


def resolve_project_root(default_root: Path) -> Path:
    configured_root = os.environ.get(PROJECT_ROOT_ENVIRONMENT_VARIABLE)
    root = Path(configured_root).expanduser() if configured_root else default_root
    return root.resolve()


def count_indexed_files(default_root: Path) -> int:
    """Count file resources indexed by the project's RO-Crate metadata."""
    project_root = resolve_project_root(default_root)
    crate_file = _required_metadata_file(project_root, RO_CRATE_FILENAME)

    try:
        crate_data = json.loads(crate_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectInformationError(
            f"Não foi possível ler o RO-Crate: {crate_file}"
        ) from exc

    graph = crate_data.get("@graph")
    if not isinstance(graph, list):
        raise ProjectInformationError(
            f"RO-Crate sem @graph válido: {crate_file}"
        )

    entities = [entity for entity in graph if isinstance(entity, dict)]
    root_dataset = next(
        (entity for entity in entities if entity.get("@id") in {"./", "."}),
        None,
    )

    if root_dataset is not None:
        part_ids = set(_reference_ids(root_dataset.get("hasPart")))
        indexed_parts = {
            resource_id
            for resource_id in part_ids
            if _is_local_file_identifier(resource_id)
        }
        if indexed_parts:
            return len(indexed_parts)

    indexed_entities = {
        str(entity.get("@id", "")).strip()
        for entity in entities
        if _is_file_entity(entity)
    }
    return len(indexed_entities)


def project_path_from_ontology(default_root: Path) -> str:
    """Read the project path from prov:atLocation in container.ttl."""
    project_root = resolve_project_root(default_root)
    ontology_file = _required_metadata_file(
        project_root,
        CONTAINER_ONTOLOGY_FILENAME,
    )

    try:
        ontology_text = ontology_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectInformationError(
            f"Não foi possível ler a ontologia: {ontology_file}"
        ) from exc

    match = _AT_LOCATION_PATTERN.search(ontology_text)
    if match is None:
        raise ProjectInformationError(
            f"prov:atLocation não encontrado em {ontology_file}"
        )

    raw_location = match.group("uri") or _decode_turtle_literal(
        match.group("literal") or ""
    )
    if not raw_location:
        raise ProjectInformationError(
            f"prov:atLocation vazio em {ontology_file}"
        )

    return _display_path(raw_location)


def project_coordinates_from_ifc(default_root: Path) -> dict[str, float] | None:
    """Resolve WGS84 coordinates from IfcSite.RefLatitude/RefLongitude."""
    project_root = resolve_project_root(default_root)
    ontology_files = tuple(_project_ontology_files(project_root))
    if not ontology_files:
        return None

    for ontology_file in ontology_files:
        coordinates = _coordinates_from_ifc_ontology(ontology_file)
        if coordinates is not None:
            return coordinates

    return None


def _project_ontology_files(project_root: Path) -> Iterator[Path]:
    for ontology_file in sorted(project_root.rglob("project.ttl")):
        if ontology_file.parent.name != "__infobim__":
            continue
        if ontology_file.parent.parent.name != METADATA_DIRECTORY:
            continue
        if ontology_file.is_file():
            yield ontology_file


def _coordinates_from_ifc_ontology(
    ontology_file: Path,
) -> dict[str, float] | None:
    try:
        from rdflib import Graph
    except ImportError as exc:
        raise ProjectInformationError(
            "rdflib é necessário para ler IfcSite.RefLatitude/RefLongitude."
        ) from exc

    graph = Graph()
    try:
        graph.parse(ontology_file, format="turtle")
    except Exception as exc:
        raise ProjectInformationError(
            f"Não foi possível ler as coordenadas IFC em {ontology_file}"
        ) from exc

    for site, latitude_node in _subject_objects_by_predicate_name(
        graph,
        IFC_REF_LATITUDE_LOCAL_NAME,
    ):
        longitude_node = _first_object_by_predicate_name(
            graph,
            site,
            IFC_REF_LONGITUDE_LOCAL_NAME,
        )
        if longitude_node is None:
            continue

        latitude = _compound_plane_angle_to_decimal(graph, latitude_node)
        longitude = _compound_plane_angle_to_decimal(graph, longitude_node)
        if latitude is None or longitude is None:
            continue
        if not -90 <= latitude <= 90:
            continue
        if not -180 <= longitude <= 180:
            continue

        return {
            "latitude": latitude,
            "longitude": longitude,
        }

    return None


def _subject_objects_by_predicate_name(
    graph: Any,
    predicate_name: str,
) -> Iterator[tuple[Any, Any]]:
    for subject, predicate, value in graph:
        if _local_name(predicate) == predicate_name:
            yield subject, value


def _first_object_by_predicate_name(
    graph: Any,
    subject: Any,
    predicate_name: str,
) -> Any | None:
    for predicate, value in graph.predicate_objects(subject):
        if _local_name(predicate) == predicate_name:
            return value
    return None


def _compound_plane_angle_to_decimal(graph: Any, node: Any) -> float | None:
    components = _compound_plane_angle_components(graph, node)
    if not components:
        return None
    if len(components) == 1:
        return components[0]

    degrees = components[0]
    sign = -1.0 if degrees < 0 else 1.0
    minutes = abs(components[1]) if len(components) > 1 else 0.0
    seconds = abs(components[2]) if len(components) > 2 else 0.0
    millionths = abs(components[3]) if len(components) > 3 else 0.0
    return sign * (
        abs(degrees)
        + minutes / 60.0
        + seconds / 3600.0
        + millionths / 3_600_000_000.0
    )


def _compound_plane_angle_components(graph: Any, node: Any) -> list[float]:
    direct_value = _numeric_value(graph, node)
    if direct_value is not None:
        return [direct_value]

    rdf_components = _rdf_collection_components(graph, node)
    if rdf_components:
        return rdf_components

    linked_components = _linked_list_components(graph, node)
    if linked_components:
        return linked_components

    return _numbers_from_lexical_value(str(node))


def _rdf_collection_components(graph: Any, node: Any) -> list[float]:
    try:
        from rdflib.namespace import RDF
    except ImportError:
        return []

    values: list[float] = []
    current = node
    visited: set[Any] = set()
    while current != RDF.nil and current not in visited:
        visited.add(current)
        item = graph.value(current, RDF.first)
        if item is None:
            return []
        numeric = _numeric_value(graph, item)
        if numeric is None:
            return []
        values.append(numeric)
        current = graph.value(current, RDF.rest)
        if current is None:
            return []
    return values


def _linked_list_components(graph: Any, node: Any) -> list[float]:
    values: list[float] = []
    current = node
    visited: set[Any] = set()
    while current is not None and current not in visited:
        visited.add(current)
        item = _first_object_by_predicate_name(graph, current, "hasContents")
        if item is None:
            break
        numeric = _numeric_value(graph, item)
        if numeric is None:
            return []
        values.append(numeric)
        current = _first_object_by_predicate_name(graph, current, "hasNext")
    return values


def _numeric_value(graph: Any, node: Any) -> float | None:
    try:
        from rdflib import Literal
    except ImportError:
        return None

    if isinstance(node, Literal):
        try:
            return float(node.toPython())
        except (TypeError, ValueError):
            numbers = _numbers_from_lexical_value(str(node))
            return numbers[0] if len(numbers) == 1 else None

    accepted_predicates = {
        "hasInteger",
        "hasDouble",
        "hasDecimal",
        "hasReal",
        "hasValue",
    }
    for predicate, value in graph.predicate_objects(node):
        if _local_name(predicate) not in accepted_predicates:
            continue
        numeric = _numeric_value(graph, value)
        if numeric is not None:
            return numeric
    return None


def _numbers_from_lexical_value(value: str) -> list[float]:
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?", value)
    try:
        return [float(match) for match in matches]
    except ValueError:
        return []


def _local_name(value: Any) -> str:
    text = str(value)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _required_metadata_file(project_root: Path, filename: str) -> Path:
    metadata_file = project_root / METADATA_DIRECTORY / filename
    if metadata_file.is_file():
        return metadata_file

    raise ProjectInformationError(
        f"Metadado não encontrado: {metadata_file}. "
        f"Defina {PROJECT_ROOT_ENVIRONMENT_VARIABLE} para a raiz do projeto, "
        "quando necessário."
    )


def _reference_ids(raw_value: Any) -> Iterable[str]:
    values = raw_value if isinstance(raw_value, list) else [raw_value]
    for value in values:
        if isinstance(value, dict):
            resource_id = value.get("@id")
        else:
            resource_id = value
        if isinstance(resource_id, str) and resource_id.strip():
            yield resource_id.strip()


def _entity_types(entity: dict[str, Any]) -> set[str]:
    raw_types = entity.get("@type")
    values = raw_types if isinstance(raw_types, list) else [raw_types]
    return {
        str(value).rsplit("/", 1)[-1].rsplit("#", 1)[-1].lower()
        for value in values
        if value
    }


def _is_file_entity(entity: dict[str, Any]) -> bool:
    resource_id = str(entity.get("@id", "")).strip()
    if not _is_local_file_identifier(resource_id):
        return False

    entity_types = _entity_types(entity)
    file_types = {
        "file",
        "mediaobject",
        "digitaldocument",
        "textdigitaldocument",
        "spreadsheetdigitaldocument",
        "presentationdigitaldocument",
        "imageobject",
        "audioobject",
        "videoobject",
        "softwaresourcecode",
    }
    if entity_types.intersection(file_types):
        return True

    return bool(Path(urlparse(resource_id).path).suffix)


def _is_local_file_identifier(resource_id: str) -> bool:
    normalized = resource_id.strip()
    if normalized in {
        "",
        ".",
        "./",
        RO_CRATE_FILENAME,
        f"./{RO_CRATE_FILENAME}",
    }:
        return False
    if normalized.startswith("#") or normalized.endswith("/"):
        return False

    parsed = urlparse(normalized)
    if parsed.scheme in {"http", "https", "urn", "mailto"}:
        return False
    return True


def _decode_turtle_literal(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def _display_path(raw_location: str) -> str:
    parsed = urlparse(raw_location)
    if parsed.scheme.lower() != "file":
        return unquote(raw_location)

    decoded_path = unquote(parsed.path)
    if parsed.netloc:
        return f"//{parsed.netloc}{decoded_path}"

    if re.match(r"^/[A-Za-z]:/", decoded_path):
        return decoded_path[1:].replace("/", "\\")

    return decoded_path or raw_location


import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, cast

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
    from markupsafe import Markup, escape
except ImportError as exc:
    missing = exc.name or "dependency"
    raise SystemExit(
        f"Missing {missing}. Install dependencies with: "
        "python -m pip install jinja2 pyyaml rdflib"
    ) from exc

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "template"
VIEW_FILE = ROOT / "views" / "public.yaml"
OUTPUT_FILE = ROOT / "index.html"
PROJECT_RUNTIME_DATA_FILE = (
    ROOT
    / ".__ontobdc__"
    / "asset"
    / "infobim-view"
    / "js"
    / "project_runtime_data.js"
)
INLINE_STRONG_PATTERN = re.compile(r"(\*\*|__)(.+?)\1")
LOCAL_VIEW_ACTION_PREFIXES = ("view/", "./view/")
MONTHS_PT_BR = (
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def render_inline_markup(raw_text: str) -> Markup:
    escaped_text: str = str(escape(raw_text))
    formatted_text: str = INLINE_STRONG_PATTERN.sub(r"<strong>\2</strong>", escaped_text)
    formatted_text = formatted_text.replace("\n", "<br>\n")
    return Markup(formatted_text)


def transform_view_value(raw_value: Any) -> Any:
    if isinstance(raw_value, str):
        return render_inline_markup(raw_value)
    if isinstance(raw_value, list):
        return [transform_view_value(item) for item in raw_value]
    if isinstance(raw_value, dict):
        return {
            key: transform_view_value(value)
            for key, value in raw_value.items()
        }
    return raw_value


def prepare_view_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    return cast(Dict[str, Any], transform_view_value(raw_data))


def generation_date() -> str:
    current = datetime.now().astimezone()
    return f"{current.day} de {MONTHS_PT_BR[current.month]} de {current.year}"


def generated_project_value(
    label: str,
    resolver: Callable[[Path], Any],
) -> Any:
    try:
        return resolver(ROOT)
    except ProjectInformationError as exc:
        print(f"Warning: {label}: {exc}", file=sys.stderr)
        return "Não disponível"


def generated_project_coordinates() -> dict[str, float] | None:
    try:
        return project_coordinates_from_ifc(ROOT)
    except ProjectInformationError as exc:
        print(f"Warning: project coordinates: {exc}", file=sys.stderr)
        return None


def enrich_project_information(raw_data: Dict[str, Any]) -> None:
    project = raw_data.setdefault("project", {})
    raw_fields = project.setdefault("fields", [])
    if not isinstance(raw_fields, list):
        raise TypeError("project.fields must be a list")

    generated_labels = {"Path", "Arquivos indexados"}
    fields = [
        field
        for field in raw_fields
        if not (
            isinstance(field, dict)
            and field.get("label") in generated_labels
        )
    ]

    project_path = "./"
    indexed_files = generated_project_value(
        "indexed files",
        count_indexed_files,
    )

    fields.extend(
        [
            {"label": "Path", "value": project_path},
            {"label": "Arquivos indexados", "value": indexed_files},
        ]
    )
    project["fields"] = fields
    project["path"] = project_path
    project["location"] = generated_project_coordinates()


def local_view_navigation_script() -> str:
    prefixes = ", ".join(repr(prefix) for prefix in LOCAL_VIEW_ACTION_PREFIXES)
    return f"""  <script>
    (function () {{
      const prefixes = [{prefixes}];
      document.querySelectorAll('.menubar-item[data-action]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const action = String(button.dataset.action || '').trim();
          if (prefixes.some((prefix) => action.startsWith(prefix))) {{
            window.location.href = action;
          }}
        }});
      }});
    }}());
  </script>
"""


def inject_before_closing_body(html: str, fragment: str) -> str:
    closing_body = "</body>"
    if closing_body not in html:
        raise ValueError("Rendered dashboard does not contain a closing body tag.")
    return html.replace(closing_body, fragment + closing_body, 1)


def inject_local_view_navigation(html: str) -> str:
    return inject_before_closing_body(html, local_view_navigation_script())


def serialize_runtime_script(variable_name: str, payload: Any) -> str:
    return (
        f"window.{variable_name} = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n"
    )


def write_runtime_script(path: Path, variable_name: str, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        serialize_runtime_script(variable_name, payload),
        encoding="utf-8",
    )


def write_project_runtime_data(location: dict[str, float] | None) -> None:
    write_runtime_script(
        PROJECT_RUNTIME_DATA_FILE,
        "infoBimProjectRuntimeData",
        {"location": location},
    )


def _bind_container_root(container_root: Path) -> None:
    global ROOT
    global TEMPLATE_DIR
    global VIEW_FILE
    global OUTPUT_FILE
    global PROJECT_RUNTIME_DATA_FILE

    ROOT = container_root.expanduser().resolve()
    TEMPLATE_DIR = ROOT / "template"
    VIEW_FILE = ROOT / "views" / "public.yaml"
    OUTPUT_FILE = ROOT / "index.html"
    PROJECT_RUNTIME_DATA_FILE = (
        ROOT
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
        / "js"
        / "project_runtime_data.js"
    )


def _generate_hardcoded_dashboard() -> int:
    if not VIEW_FILE.is_file():
        print(f"View not found: {VIEW_FILE}", file=sys.stderr)
        return 1

    raw_data: Dict[str, Any] = cast(
        Dict[str, Any],
        yaml.safe_load(VIEW_FILE.read_text(encoding="utf-8")) or {},
    )
    enrich_project_information(raw_data)
    raw_data["generation"] = {"date": generation_date()}
    data: Dict[str, Any] = prepare_view_data(raw_data)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("index.html.jinja").render(**data)
    html = inject_local_view_navigation(html)
    OUTPUT_FILE.write_text(html.rstrip() + "\n", encoding="utf-8")
    write_project_runtime_data(raw_data["project"].get("location"))

    print(f"Generated {OUTPUT_FILE.relative_to(ROOT)} from {VIEW_FILE.relative_to(ROOT)}")
    print(f"Generated {PROJECT_RUNTIME_DATA_FILE.relative_to(ROOT)}")
    return 0

class HardcodedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "hardcoded"
        ),
        version="1.0.0",
        name="Hardcoded",
        description=(
            "Execute view-generation operations that have not yet been formalized."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "container", "hardcoded", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerViewProcessState.HARDCODED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerViewProcessState.HARDCODED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_container_path = context.get_parameter_value("container_path")
        container_path = Path(str(raw_container_path or "")).expanduser()
        if not str(raw_container_path or "").strip():
            raise ValueError("The container path was not resolved.")
        container_path = container_path.resolve()
        if not container_path.is_dir():
            raise ValueError(
                f"Container path is not an accessible directory: {container_path}"
            )

        _bind_container_root(container_path)
        result = _generate_hardcoded_dashboard()
        if result != 0:
            raise RuntimeError(
                f"Hardcoded dashboard generation failed with status {result}."
            )

        return {
            "resulting_state": ContainerViewProcessState.HARDCODED,
            "container_path": str(container_path),
            "index_path": str(OUTPUT_FILE),
            "index_uri": OUTPUT_FILE.as_uri(),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        try:
            raw_container_path = context.get_parameter_value("container_path")
            if not str(raw_container_path or "").strip():
                return False
            container_path = Path(str(raw_container_path)).expanduser().resolve()
            index_path = container_path / "index.html"
            if not index_path.is_file():
                return False
            document = index_path.read_text(encoding="utf-8")
            return (
                "InfoBIM Dashboard" in document
                and 'id="work-stream-jsonld"' not in document
                and "window.infoBimWorkStreamData" not in document
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return False
