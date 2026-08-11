from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.domain.machine.state import ContainerViewProcessState
from ontobdc.view.plugin.capability.facades_serialized import (
    FACADES_JSONLD_RELATIVE_PATH,
    FacadesSerializedCapability,
    resolve_container_path,
)


ENTITY_DIRECTORY_BY_TYPE = {
    "WorkStream": "work_stream",
    "IfcWorkSchedule": "ifc_work_schedule",
}
TEMPLATE_FILENAME_BY_ENTITY_DIRECTORY = {
    "work_stream": "work_stream.html.jinja",
    "ifc_work_schedule": "ifc_work_schedule.html.jinja",
}
TEMPLATE_RELATIVE_PATH = Path("template")
VIEW_OUTPUT_RELATIVE_PATH = Path("view")


def _entity_type_name(value: Any) -> str:
    entity_type = str(value or "").strip().rstrip("/#")
    return entity_type.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def dataset_entity_instances(
    container_path: Path,
) -> Tuple[Dict[str, Any], ...]:
    """Read supported dataset entities from their canonical data packages."""
    instances = []
    for datapackage_path in sorted(
        container_path.glob("*/.__ontobdc__/datapackage.json")
    ):
        try:
            package = json.loads(datapackage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Invalid dataset data package: {datapackage_path}"
            ) from exc

        data_entity = package.get("dataEntity")
        if not isinstance(data_entity, dict):
            continue
        entity_type = _entity_type_name(data_entity.get("type"))
        entity_directory = ENTITY_DIRECTORY_BY_TYPE.get(entity_type)
        if entity_directory is None:
            continue

        identifier = str(data_entity.get("identifier") or "").strip()
        entity_id = str(data_entity.get("id") or "").strip()
        if not identifier:
            raise ValueError(
                f"Dataset entity identifier not found: {datapackage_path}"
            )
        instances.append(
            {
                "dataset_path": datapackage_path.parent.parent,
                "dataset_description": str(package.get("description") or ""),
                "dataset_name": datapackage_path.parent.parent.name,
                "dataset_title": str(package.get("title") or ""),
                "entity_directory": entity_directory,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "identifier": identifier,
            }
        )
    return tuple(instances)


def dataset_entity_view_plan(
    container_path: Path,
) -> Tuple[Dict[str, Any], ...]:
    """Bind each real dataset entity to its canonical template and target."""
    plan = []
    for instance in dataset_entity_instances(container_path):
        entity_directory = instance["entity_directory"]
        template_filename = TEMPLATE_FILENAME_BY_ENTITY_DIRECTORY[
            entity_directory
        ]
        template_path = (
            container_path / TEMPLATE_RELATIVE_PATH / template_filename
        )
        if not template_path.is_file():
            raise ValueError(
                "Dataset entity view template not found for "
                f"{instance['entity_type']}: {template_path}"
            )
        plan.append(
            {
                **instance,
                "template_filename": template_filename,
                "template_path": template_path,
                "target_path": (
                    container_path
                    / VIEW_OUTPUT_RELATIVE_PATH
                    / entity_directory
                    / f"{instance['identifier']}.html"
                ),
            }
        )
    return tuple(plan)


def _serialized_facades_jsonld(container_path: Path) -> str:
    artifact_path = container_path / FACADES_JSONLD_RELATIVE_PATH
    try:
        document = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Invalid serialized facades JSON-LD: {artifact_path}"
        ) from exc
    serialized = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return serialized.replace("</", "<\\/")


def _render_page(container_path: Path, item: Dict[str, Any]) -> bytes:
    environment = Environment(
        loader=FileSystemLoader(container_path / TEMPLATE_RELATIVE_PATH),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(item["template_filename"])
    rendered = template.render(
        dataset_description=item["dataset_description"],
        dataset_name=item["dataset_name"],
        dataset_title=item["dataset_title"],
        entity_id=item["entity_id"],
        entity_type=item["entity_type"],
        facades_jsonld=_serialized_facades_jsonld(container_path),
        identifier=item["identifier"],
    )
    return rendered.rstrip().encode("utf-8") + b"\n"


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def generate_dataset_entity_views(container_path: Path) -> Dict[str, Any]:
    """Regenerate a page for every WorkStream and IfcWorkSchedule entity."""
    generated_pages = []
    fingerprint = hashlib.sha256()
    for item in dataset_entity_view_plan(container_path):
        content = _render_page(container_path, item)
        target_path = item["target_path"]
        relative_template = item["template_path"].relative_to(
            container_path
        ).as_posix()
        relative_target = target_path.relative_to(container_path).as_posix()
        fingerprint.update(relative_target.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(content)
        fingerprint.update(b"\0")
        _atomic_write_bytes(target_path, content)
        generated_pages.append(
            {
                "entity_id": item["entity_id"],
                "entity_type": item["entity_type"],
                "identifier": item["identifier"],
                "template": relative_template,
                "target": relative_target,
            }
        )

    return {
        "generated_pages": generated_pages,
        "page_count": len(generated_pages),
        "fingerprint": fingerprint.hexdigest(),
    }


def are_dataset_entity_views_generated(context: CliContextPort) -> bool:
    container_path = resolve_container_path(context)
    try:
        plan = dataset_entity_view_plan(container_path)
        for item in plan:
            target_path = item["target_path"]
            if not target_path.is_file():
                return False
            expected = _render_page(
                container_path,
                item,
            )
            if target_path.read_bytes() != expected:
                return False
    except (OSError, UnicodeError, ValueError):
        return False
    return True


class DatasetViewsGeneratedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.view.plugin.capability.transformation.target."
            "dataset_views_generated"
        ),
        version="1.1.0",
        name="Dataset Views Generated",
        description=(
            "Regenerate one published page for every WorkStream and "
            "IfcWorkSchedule entity declared by the container datasets."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "view",
            "dataset",
            "workstream",
            "ifc-work-schedule",
            "generation",
            "transformation",
        ],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerViewProcessState.DATASET_VIEWS_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerViewProcessState.DATASET_VIEWS_GENERATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if not FacadesSerializedCapability().is_satisfied(context):
            raise RuntimeError(
                "The dataset facade instances were not serialized in the container view."
            )

        container_path = resolve_container_path(context)
        result = generate_dataset_entity_views(container_path)
        return {
            "resulting_state": (
                ContainerViewProcessState.DATASET_VIEWS_GENERATED
            ),
            "container_path": str(container_path),
            **result,
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        if not FacadesSerializedCapability().is_satisfied(context):
            return False
        return are_dataset_entity_views_generated(context)
