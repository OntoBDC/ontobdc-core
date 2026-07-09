
from typing import Dict, Any, Optional
from sismic.model import Statechart
from sismic.interpreter import Interpreter
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.run.domain.port.machine import IntentStatePort
from ontobdc.shared.domain.port.logger import LoggerAwarePort
from ontobdc.shared.domain.resource.capability import Capability
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort
from ontobdc.shared.domain.port.machine import StatechartRepositoryPort
from ontobdc.shared.domain.resource.capability import CapabilityExecutor
from ontobdc.run.domain.machine.lifecycle import RunIntentResolutionState
from ontobdc.run.adapter.repository import IntentLocalStatechartRepository
from ontobdc.run.adapter.sismic import SismicIntentTransitionHandlerAdapter
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.run.plugin.check.has_valid_context.check import main as check_error
from ontobdc.run.plugin.check.has_valid_context.hotfix import main as plugin_hotfix
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.domain.port.context import PromptChoiceAwarePort, PromptRawTextAwarePort


class RunBaseCommand(CliCommandPort, LoggerAwarePort, PromptChoiceAwarePort, PromptRawTextAwarePort):
    """
    Base command for run plugin
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="run",
        description="Base command for run plugin",
        depends_on=None,
        arguments=[
            {
                "accepts": [],
                "description": "Run the component with context arguments",
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._log_strategy : Optional[LogStrategyContainerPort] = None
        self._prompt_choice : Optional[callable] = None
        self._prompt_raw_text : Optional[callable] = None

    @property
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        """
        Returns the log strategy container.
        """
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: callable):
        self._prompt_choice = prompt_choice

    def set_prompt_raw_text(self, prompt_raw_text: callable):
        self._prompt_raw_text = prompt_raw_text

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if check_error():
            plugin_hotfix()
            self._request.context.reload()

        return not check_error()

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        try:
            handler: SismicIntentTransitionHandlerAdapter = SismicIntentTransitionHandlerAdapter(self._request.context)
            handler.set_log_strategy(self._log_strategy)
            handler.set_prompt_choice(self._prompt_choice)
            handler.set_prompt_raw_text(self._prompt_raw_text)

            context: Dict[str, Any] = {
                'handler': handler,
                'IntentStatePort': RunIntentResolutionState,
            }

            current_state: IntentStatePort = handler.current_state

            statechart_repo: StatechartRepositoryPort = IntentLocalStatechartRepository()

            statechart: Statechart = statechart_repo.get_statechart()

            statechart.state_for(statechart.root).initial = current_state.value.strip('__')

            interpreter: Interpreter = Interpreter(statechart, initial_context=context)

            interpreter.execute_once()

            while not interpreter.final:
                interpreter.execute_once()
                final_state: IntentStatePort = handler.current_state

                if current_state == final_state:
                    stuck_state_code = final_state.value.strip('__')
                    raise RuntimeError(f"State stuck at {stuck_state_code}. No transition was made.")

                current_state = final_state
                # current_state_code = current_state.value.strip('__')

            if handler.is_unresolvable:
                return ExceptionCommandResponse(
                    content={
                        "execution_response": (
                            "The system is unresolvable. Please check your intent:"
                            f"{handler.intent}"
                        )
                    }
                )

            if handler.is_successful:
                capability: Optional[Capability] = handler.target_capability
                final_context = handler.context

                return CommandResponse(
                    title="OntoBDC Run",
                    description="Command executed successfully.",
                    content={
                        "execution_response": CapabilityExecutor.execute(capability, final_context)
                    }
                )
        except Exception as e:
            return ExceptionCommandResponse(
                content={
                    "execution_response": f"Error: {str(e)}"
                }
            )

        return ExceptionCommandResponse(
            content={
                "execution_response": (
                    f"The execution flow stopped in state '{current_state.label()}': "
                    f"{current_state.description()}"
                )
            }
        )








