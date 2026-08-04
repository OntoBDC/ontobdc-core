import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.adapter.repository import DocumentImportStepRepository, LocalContextFileResource
from ontobdc.context.domain.machine.document_import_state import DocumentImportProcessState
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort


class DocumentImportStateTransitionHandler:
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._step_repository: DocumentImportStepRepository = context.get_parameter_value("step_repository")
        self._target_path: Path = self._step_repository.source_path

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def observed_state(self) -> DocumentImportProcessState:
        for state in reversed(self._import_state_sequence()):
            if self._step_repository.exists(state):
                return state
        return DocumentImportProcessState.UNDEFINED

    def execute(self) -> CommandResponse:
        generated_steps: List[Dict[str, Any]] = []

        previous_state: DocumentImportProcessState = DocumentImportProcessState.UNDEFINED
        state: DocumentImportProcessState
        for state in self._import_state_sequence():
            step_payload: Dict[str, Any] = self._build_step_payload(
                state=state,
                previous_state=previous_state,
            )
            step_path: Path = self._step_repository.write_text_file(
                state=state,
                content=json.dumps(step_payload, ensure_ascii=True, indent=2, sort_keys=True),
                file_type="json",
            )
            self._context.set_parameter_value("resource", LocalContextFileResource(step_path))
            generated_steps.append(
                {
                    "state": state.value,
                    "path": str(step_path),
                }
            )
            previous_state = state

        current_state: DocumentImportProcessState = self.observed_state

        return CommandResponse(
            title="Context Import Bootstrap",
            description=f"Bootstrapped the import workflow for '{self._target_path.name}' with an empty workbook source.",
            content={
                "container_id": str(self._context.get_parameter_value("container_id") or "").strip(),
                "container_path": str(self._context.get_parameter_value("container_path") or "").strip(),
                "entity_uri": str(self._context.get_parameter_value("entity_uri") or "").strip(),
                "source_path": str(self._target_path),
                "current_state": current_state.value,
                "visited_states": [DocumentImportProcessState.UNDEFINED.value]
                + [step["state"] for step in generated_steps],
                "step_dir": str(self._step_repository.step_dir),
                "generated_steps": generated_steps,
            },
        )

    def _import_state_sequence(self) -> List[DocumentImportProcessState]:
        return [
            DocumentImportProcessState.INGESTED,
            DocumentImportProcessState.PROFILED,
            DocumentImportProcessState.EXTRACTED,
            DocumentImportProcessState.STRUCTURED,
            DocumentImportProcessState.INSTANTIATED,
            DocumentImportProcessState.RESOLVED,
            DocumentImportProcessState.VALIDATED,
            DocumentImportProcessState.LINKED,
            DocumentImportProcessState.PACKAGED,
            DocumentImportProcessState.PUBLISHED,
        ]

    def _build_step_payload(
        self,
        *,
        state: DocumentImportProcessState,
        previous_state: DocumentImportProcessState,
    ) -> Dict[str, Any]:
        source_resource: LocalContextFileResource = self._step_repository.reload(DocumentImportProcessState.UNDEFINED)
        entity_facade: Dict[str, Any] = dict(self._context.get_parameter_value("entity_facade") or {})
        field_identifiers: List[str] = [
            str(field.get("identifier") or "").strip()
            for field in list(entity_facade.get("fields") or [])
            if str(field.get("identifier") or "").strip()
        ]

        payload: Dict[str, Any] = {
            "state": state.value,
            "state_label": state.label(),
            "state_description": state.description(),
            "previous_state": previous_state.value,
            "container_id": str(self._context.get_parameter_value("container_id") or "").strip(),
            "container_path": str(self._context.get_parameter_value("container_path") or "").strip(),
            "entity_uri": str(self._context.get_parameter_value("entity_uri") or "").strip(),
            "entity_name": str(entity_facade.get("entity_name") or "").strip(),
            "entity_identifier": str(entity_facade.get("entity_identifier") or "").strip(),
            "entity_facade_uri": str(entity_facade.get("facade_uri") or "").strip(),
            "source_file": source_resource.to_json(),
            "workbook": {
                "path": str(source_resource.path),
                "worksheet_name": str(self._context.get_parameter_value("worksheet_name") or "").strip(),
                "field_count": len(field_identifiers),
                "field_identifiers": field_identifiers,
                "row_count": 0,
                "format": "xlsx",
            },
            "datapackage_path": str(self._context.get_parameter_value("datapackage_path") or "").strip(),
            "bootstrap_mode": "empty_entity_workbook",
        }

        return payload
