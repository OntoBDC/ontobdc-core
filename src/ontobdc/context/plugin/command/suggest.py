from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.adapter.instance import ContainerEntityInstanceRepository
from ontobdc.context.adapter.resource_inventory import ContainerResourceInventory
from ontobdc.context.adapter.suggestion_agent import (
    invoke_suggestion_agent,
    validate_suggestion_response,
)
from ontobdc.context.adapter.workstream_linkset import WorkStreamResourceLinkset
from ontobdc.context.plugin.parameter.global_id import resolve_entity_by_global_id


class ContextSuggestCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="suggest",
        logical_component="context",
        description="Suggest existing resources for one WorkStream dimension.",
        arguments=[
            {"accepts": ["--entity"], "valued": True},
            {"accepts": ["--global-id"], "valued": True},
            {"accepts": ["--dimension"], "valued": True},
            {"accepts": ["--container-id", "--container"], "valued": True},
            {"accepts": ["--suggest"], "valued": False},
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    @staticmethod
    def accepts(args: list[str]) -> bool:
        return bool(
            args
            and args[0] == "context"
            and "--suggest" in args
            and "--entity" in args
            and "--global-id" in args
            and "--dimension" in args
        )

    def check(self) -> bool:
        context = self._request.context
        entity = str(context.get_parameter_value("entity") or "").strip()
        if entity.lower() != "workstream":
            raise CliCommandArgumentException(
                "--suggest currently requires --entity WorkStream."
            )
        if not str(context.get_parameter_value("global_id") or "").strip():
            raise CliCommandArgumentException("--global-id is required.")
        if not str(context.get_parameter_value("dimension") or "").strip():
            raise CliCommandArgumentException("--dimension is required.")
        if not str(context.get_parameter_value("container_path") or "").strip():
            raise CliCommandArgumentException(
                "Could not resolve a container. Run inside one or pass --container."
            )
        return True

    def execute(self) -> CommandResponse:
        context = self._request.context
        container_path = Path(
            str(context.get_parameter_value("container_path"))
        ).resolve()
        global_id = str(context.get_parameter_value("global_id")).strip()
        instance = context.get_parameter_value(
            "entity_instance"
        ) or resolve_entity_by_global_id(
            container_path=str(container_path), entity="WorkStream", global_id=global_id
        )
        dimension_label, dimension_uri, dimension_value = self._resolve_dimension(
            container_path, str(context.get_parameter_value("dimension")), instance
        )
        related = WorkStreamResourceLinkset(container_path, "related")
        excluded = related.active_resources(dimension_uri)
        resources = [
            item
            for item in ContainerResourceInventory(container_path).list_resources()
            if item["uri"] not in excluded
        ]
        candidates = {
            f"R{index:03d}": item for index, item in enumerate(resources, start=1)
        }
        prompt = self._build_prompt(
            global_id=global_id,
            instance=instance,
            dimension_label=dimension_label,
            dimension_uri=dimension_uri,
            dimension_value=dimension_value,
            candidates=candidates,
        )
        selected = validate_suggestion_response(
            invoke_suggestion_agent(prompt), candidates.keys()
        )
        suggested = WorkStreamResourceLinkset(container_path, "suggested")
        for key in selected:
            suggested.add(dimension_uri, candidates[key]["uri"])
        return CommandResponse(
            title="WorkStream resource suggestions",
            description="Persisted Proposed suggestions from the bounded inventory.",
            content={
                "workstream_global_id": global_id,
                "dimension": dimension_label,
                "dimension_uri": dimension_uri,
                "candidate_count": len(candidates),
                "suggested": [
                    {"key": key, "resource_uri": candidates[key]["uri"]}
                    for key in selected
                ],
                "linkset": str(suggested.path),
            },
        )

    def run(self) -> CommandResponse:
        return self.execute()

    def _resolve_dimension(
        self, container_path: Path, requested: str, instance: dict[str, Any]
    ) -> tuple[str, str, str]:
        payload = ContainerEntityInstanceRepository(
            container_path=str(container_path), entity="WorkStream"
        ).list_instances()
        fields: list[dict[str, str]] = []
        for dataset in payload.get("datasets", []):
            facade_path = Path(str(dataset.get("facade_path") or ""))
            if not facade_path.is_file():
                continue
            graph = Graph().parse(facade_path, format="turtle")
            for facade, predicate, field in graph:
                if self._local(predicate) != "hasFacadeField" or not isinstance(
                    field, URIRef
                ):
                    continue
                identifier = self._value_by_local(graph, field, "identifier")
                mapped = self._value_by_local(graph, field, "mapsToProperty")
                if identifier and mapped:
                    fields.append({"identifier": identifier, "uri": mapped})
        normalized = requested.strip().lower().replace("-", "").replace("_", "")
        matches = [
            field
            for field in fields
            if normalized
            in {
                field["identifier"].lower().replace("_", "").replace("-", ""),
                self._local(field["uri"]).lower().removeprefix("has"),
            }
        ]
        if len(matches) != 1:
            available = sorted({field["identifier"] for field in fields})
            raise CliCommandArgumentException(
                f"Invalid WorkStream dimension '{requested}'. Facade fields: {available}"
            )
        field = matches[0]
        value = instance.get(
            field["identifier"], instance.get(self._local(field["uri"]), "")
        )
        return field["identifier"], field["uri"], str(value or "")

    @staticmethod
    def _local(value: Any) -> str:
        text = str(value)
        return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    def _value_by_local(self, graph: Graph, subject: URIRef, name: str) -> str:
        for predicate, value in graph.predicate_objects(subject):
            if self._local(predicate) == name:
                return str(value).strip()
        return ""

    def _build_prompt(
        self,
        *,
        global_id: str,
        instance: dict[str, Any],
        dimension_label: str,
        dimension_uri: str,
        dimension_value: str,
        candidates: dict[str, dict[str, str]],
    ) -> str:
        lines = [
            "SYSTEM/ROLE: constrained project-information evidence selector. Not a project database. Cannot invent resources. Cannot modify project state. Must select zero or more candidates ONLY from the provided set.",
            "",
            "CONTEXT:",
            "  Entity type: WorkStream",
            f"  WorkStream GlobalId: {global_id}",
            f"  WorkStream title: {instance.get('Title', instance.get('Name', ''))}",
            f"  WorkStream description: {instance.get('Description', '')}",
            f"  Selected dimension: {dimension_label}",
            f"  Dimension semantic identity: {dimension_uri}",
            f"  Current dimension value: {dimension_value}",
            "",
            "QUESTION: Which candidates are plausibly relevant as evidence, source material, documentation, communication, reference, or supporting information for the SELECTED DIMENSION of THIS WorkStream specifically? Evaluate the selected dimension, not general WorkStream relatedness.",
            "",
            "CANDIDATES:",
        ]
        for key, item in candidates.items():
            lines.extend(
                [
                    f"  {key}",
                    f"    title: {item['title']}",
                    f"    path: {item['path']}",
                    f"    media_type: {item['media_type']}",
                    f"    description/snippet: {item['description']}",
                ]
            )
        lines.extend(
            [
                "",
                'OUTPUT CONTRACT — JSON ONLY, exact schema: {"suggested": ["R001", "R007"]}',
                "Rules: array of exactly-supplied candidate keys only; no explanations, no markdown, no confidence scores, no extra metadata, no invented keys; empty array is valid.",
            ]
        )
        return "\n".join(lines)
