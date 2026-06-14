
import os
import json
import requests
import tempfile
import subprocess
from pathlib import Path
from rdflib import Graph, URIRef
from typing import Any, Dict, Optional
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.a3.adapter.guardrail import JsonSchemaGuardrailAdapter
from ontobdc.a3.domain.port.guardrail import JsonSchemaGuardrailPort
from ontobdc.a3.domain.machine.response import TransformationResponse
from ontobdc.storage.domain.port.repository import LocalRepositoryPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata

PEO = get_ontology_by_prefix('peo')


class TransformationToParsedCapability(TransformationCapability):
    """
    Capability for transforming a package to a parsed version.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.a3.plugin.capability.transformation.target.parsed",
        version="0.1.0",
        name="Data package transformation to Parsed",
        description="Transform a data package to a parsed version.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "parsed", "transformation"],
            "pt": ["dados", "analisado", "transformação"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "etl_package_path": {
                    "type": Path,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataPackage",
                    "required": True,
                    "description": "The data package to transform.",
                },
                "etl_shape_uri": {
                    "type": str,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#TransformableDataShape",
                    "required": True,
                    "description": "The shape URI to use for parsing.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse": {
                    "type": "object",
                    "description": "The parsed data package.",
                    "http://ontobdc.org/ontology/domain/ns.ttl#resultingState": "http://ontobdc.org/ontology/domain/nid.ttl#EtlProcessState.PARSED",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Data package transformation to Parsed",
            "pt": "Transformação de pacote de dados para Analisado",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Transform a data package to a parsed version.",
            "pt": "Transforma um pacote de dados para uma versão analisada.",
        }
        return descriptions.get(lang, descriptions["en"])

    def __init__(self) -> None:
        self._guardrail_graph: Optional[Graph] = None

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Execute the transformation capability.
        """
        etl_package_path: LocalRepositoryPort = context.get_parameter_value("etl_package_path")
        etl_shape_uri: str = context.get_parameter_value("etl_shape_uri")
        package_path: Path = etl_package_path.path

        raw_path: Path = package_path / "sanitized.txt"
        parsed_data: Dict[str, Any] = self._extract_required_fields_with_llm(
            raw_path, etl_shape_uri
        )

        try:
            self._validate_parsed_data(parsed_data, etl_shape_uri)
        except Exception as exc:
            self._write_error(package_path, str(exc))
            raise

        parsed_path = package_path / "parsed.json"
        parsed_path.write_text(json.dumps(parsed_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return TransformationResponse(resultingState=A3EtlProcessState.PARSED)

    def _write_error(
        self,
        package_path: Path,
        error_message: str,
    ) -> None:
        error_path = package_path / "err.json"
        error_path.write_text(
            json.dumps(
                {
                    "state": A3EtlProcessState.TYPED.value,
                    "error": error_message,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _graph(self, guardrail_schema_uri: str) -> Graph:
        if not isinstance(self._guardrail_graph, Graph):
            ontology_uri = guardrail_schema_uri.split("#")[0]
            try:
                response = requests.get(ontology_uri, timeout=10)
                response.raise_for_status()
                ontology_content = response.text
            except requests.RequestException as e:
                raise RuntimeError(f"Failed to download ontology from '{ontology_uri}': {e}")

            self._guardrail_graph = Graph()
            self._guardrail_graph.parse(data=ontology_content, format="turtle", publicID=ontology_uri)
            self._guardrail_graph.bind("peo", PEO)

        return self._guardrail_graph

    def _extract_required_fields_with_llm(
        self,
        raw_path: Path,
        guardrail_schema_uri: str,
        *,
        llm_bin: str = "codex",
        model: Optional[str] = None,
        timeout_s: int = 120,
    ) -> Dict[str, Any]:
        raw_file = raw_path.expanduser().resolve()
        text = raw_file.read_text(encoding="utf-8")

        guardrail_graph = self._graph(guardrail_schema_uri)

        shape_node = URIRef(guardrail_schema_uri)
        prompt_individuals = list(guardrail_graph.objects(shape_node, PEO.hasPrompt))
        if not prompt_individuals:
            raise ValueError(
                f"No peo:hasPrompt found for shape '{guardrail_schema_uri}'. "
                "Ensure the shape defines :promptTemplate peo:hasPrompt :SomePrompt."
            )

        job_schema: JsonSchemaGuardrailPort = JsonSchemaGuardrailAdapter(guardrail_schema_uri)

        prompt_node = prompt_individuals[0]
        instruction_vals = list(guardrail_graph.objects(prompt_node, PEO.hasInstruction))
        if not instruction_vals:
            raise ValueError(f"No peo:hasInstruction found for prompt individual '{prompt_node}'.")

        prompt = str(instruction_vals[0])

        with tempfile.TemporaryDirectory(prefix="codex_job_") as td:
            tmp_dir = Path(td)
            schema_path = tmp_dir / "schema.json"
            out_path = tmp_dir / "out.json"
            schema_path.write_text(json.dumps(self._llm_output_schema(job_schema.schema), ensure_ascii=False), encoding="utf-8")

            cmd = [
                llm_bin,
                "exec",
                prompt,
                "--output-schema",
                str(schema_path),
                "-o",
                str(out_path),
            ]
            if model:
                cmd.extend(["--model", model])

            env = dict(os.environ)

            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                env=env,
                timeout=timeout_s,
            )

            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                stdout = (proc.stdout or "").strip()
                raise RuntimeError(f"codex exec failed (exit={proc.returncode}). stderr={stderr} stdout={stdout}")

            raw = out_path.read_text(encoding="utf-8").strip() if out_path.exists() else (proc.stdout or "").strip()
            if not raw:
                raise RuntimeError("codex exec produced empty output")

            data = json.loads(raw)

            return data


    def _llm_output_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        allowed_property_keys = {"type", "pattern", "enum", "minLength", "minItems", "items"}
        properties: Dict[str, Any] = {}

        for key, value in schema.get("properties", {}).items():
            if not isinstance(value, dict):
                continue
            cleaned: Dict[str, Any] = {}
            for k in allowed_property_keys:
                if k in value:
                    cleaned[k] = value[k]
            if cleaned.get("type") == "array" and "items" in cleaned and isinstance(cleaned["items"], dict):
                cleaned_items = {}
                for ik in allowed_property_keys:
                    if ik in cleaned["items"]:
                        cleaned_items[ik] = cleaned["items"][ik]
                cleaned["items"] = cleaned_items
            properties[key] = cleaned

        required = list(properties.keys())

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    def _validate_parsed_data(self, parsed_data: Dict[str, Any], guardrail_schema_uri: str) -> None:
        job_schema: JsonSchemaGuardrailPort = JsonSchemaGuardrailAdapter(guardrail_schema_uri)
        job_schema.validate(parsed_data)
