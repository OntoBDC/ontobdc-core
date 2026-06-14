
import requests
from typing import Dict, Optional
from ontobdc.shared.adapter.util import is_valid_url
from ontobdc.storage.adapter.resource import UrlResource
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.domain.port.logger import LoggerAwarePort
from ontobdc.context.adapter.remote import RemoteCommandRunAdapter
from ontobdc.shared.domain.port.context import PromptChoiceAwarePort
from ontobdc.storage.adapter.dataset import RemotePublicDatasetRepository
from ontobdc.storage.domain.port.dataset import RemoteDatasetRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.cli.domain.resource.command import ExceptionCommandResponse, ReportCommandResponse
from ontobdc.context.domain.resource.remote import EntityMetadata, RemoteCapabilityMetadata


class ContextRemoteDatasetCommand(CliCommandPort, LoggerAwarePort, PromptChoiceAwarePort):
    METADATA = CliCommandMetadata(
        id="remote_dataset",
        logical_component="context",
        description="Set the remote parameter in the execution context.",
        arguments=[
            {
                "accepts": ["--remote", "-r"],
                "valued": True,
                "description": "Remote parameter value to set.",
                "usage": "ontobdc context --remote <param_value>",
            },
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None
        self._prompt_choice: Optional[callable] = None
        self._log_strategy = None

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def set_prompt_choice(self, prompt_choice: callable) -> None:
        self._prompt_choice = prompt_choice

    def set_log_strategy(self, log_strategy) -> None:
        self._log_strategy = log_strategy

    @property
    def log_strategy(self):
        return self._log_strategy

    def check(self) -> bool:
        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        if check_error():
            return False

        args = self._request.command_args
        param_value = args[1]

        if not is_valid_url(param_value):
            return False

        return True

    def _get_selected_entity(self, entities: Dict[str, EntityMetadata]) -> EntityMetadata | ExceptionCommandResponse:
            if len(entities) == 1:
                selected_entity_id = list(entities.keys())[0]
            else:
                if self._prompt_choice is None:
                    return ExceptionCommandResponse(
                        title="Prompt Not Configured",
                        description="Cannot prompt the user to choose an entity because prompt_choice is not configured.",
                        content={}
                    )

                choice_options = []
                choice_values = []
                for entity_id, metadata in entities.items():
                    title = metadata.get_title(lang=self._request.context.language)
                    label = f"{title} ({entity_id})" if title else str(entity_id)
                    choice_options.append(label)
                    choice_values.append(entity_id)

                cancel_label = "Cancel" if self._request.context.language == "en" else "Cancelar"
                prompt_text = "Select an entity" if self._request.context.language == "en" else "Selecione uma entidade"

                selected_value = self._prompt_choice(
                    "Context",
                    prompt_text,
                    choice_options,
                    default=choice_options[0],
                    language=self._request.context.language,
                    none=cancel_label,
                )

                if selected_value == cancel_label:
                    return ExceptionCommandResponse(
                        title="Entity Selection Canceled",
                        description="The user canceled the entity selection.",
                        content={}
                    )

                selected_index = choice_options.index(selected_value)
                selected_entity_id = choice_values[selected_index]

            selected_entity = entities[selected_entity_id]
            if self._print_log:
                self._print_log(f"Selected entity: {selected_entity}")

            return selected_entity

    def _get_selected_capability(self, capabilities: Dict[str, RemoteCapabilityMetadata]) -> RemoteCapabilityMetadata | ExceptionCommandResponse:
        if len(capabilities) == 1:
            selected_capability_id = list(capabilities.keys())[0]
        else:
            if self._prompt_choice is None:
                return ExceptionCommandResponse(
                    title="Prompt Not Configured",
                    description="Cannot prompt the user to choose a capability because prompt_choice is not configured.",
                    content={}
                )

            choice_options = []
            choice_values = []
            for capability_id, metadata in capabilities.items():
                title = metadata.get_title(lang=self._request.context.language)
                label = f"{title} ({capability_id})" if title else str(capability_id)
                choice_options.append(label)
                choice_values.append(capability_id)

            cancel_label = "Cancel" if self._request.context.language == "en" else "Cancelar"
            prompt_text = "Select a capability" if self._request.context.language == "en" else "Selecione uma capability"

            selected_value = self._prompt_choice(
                "Context",
                prompt_text,
                choice_options,
                default=choice_options[0],
                language=self._request.context.language,
                none=cancel_label,
            )

            if selected_value == cancel_label:
                return ExceptionCommandResponse(
                    title="Capability Selection Canceled",
                    description="The user canceled the capability selection.",
                    content={}
                )

            selected_index = choice_options.index(selected_value)
            selected_capability_id = choice_values[selected_index]

        selected_capability = capabilities[selected_capability_id]
        if self._print_log:
            self._print_log(f"Selected capability: {selected_capability}")

        return selected_capability

    def run(self) -> ReportCommandResponse | ExceptionCommandResponse:
        try:
            args = self._request.command_args
            param_value = args[1]

            try:
                requests.head(param_value, timeout=5)
            except requests.exceptions.RequestException:
                return ExceptionCommandResponse(
                    title="Invalid Remote URL",
                    description=f"The provided remote URL '{param_value}' is not reachable.",
                    content={
                        "remote": param_value,
                    },
                )

            try:
                target_dataset: RemoteDatasetRepositoryPort = RemotePublicDatasetRepository(UrlResource(param_value))
            except Exception as error:
                return ExceptionCommandResponse(
                    title="Failed to Parse Remote Dataset",
                    description=f"An error occurred while parsing the remote dataset: {str(error)}",
                    content={
                        "execution_response": str(error),
                    },
                )

            entities = target_dataset.entities
            if not entities:
                return ExceptionCommandResponse(
                    title="No Entities Found",
                    description=f"The remote dataset '{param_value}' does not expose any valid entity.",
                    content={
                        "remote": param_value,
                    },
                )

            selected_entity = self._get_selected_entity(entities)

            if isinstance(selected_entity, ExceptionCommandResponse):
                return selected_entity

            capabilities = target_dataset.capabilities
            if not capabilities:
                return ExceptionCommandResponse(
                    title="No Capabilities Found",
                    description=f"The remote dataset '{param_value}' does not expose any valid capability.",
                    content={
                        "remote": param_value,
                    },
                )

            selected_capability = self._get_selected_capability(capabilities)
            if isinstance(selected_capability, ExceptionCommandResponse):
                return selected_capability

            return ReportCommandResponse(
                title="Context Remote Set",
                description=f"Successfully set context remote to '{param_value}', entity to '{selected_entity.get_title(lang=self._request.context.language)}', and capability to '{selected_capability.get_title(lang=self._request.context.language)}'.",
                content={
                    "url": param_value,
                    "entity": selected_entity,
                    "capability": selected_capability,
                    "response": RemoteCommandRunAdapter.execute(self._request.context, target_dataset, selected_capability),
                },
            )
        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to Set Context Remote",
                description=f"An error occurred while setting the context remote: {str(error)}",
                content={
                    "execution_response": str(error),
                },
            )

