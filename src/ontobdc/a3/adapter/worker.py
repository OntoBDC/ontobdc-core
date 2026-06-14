
from pathlib import Path
from typing import Any, Dict
from sismic.model import Statechart
from sismic.interpreter import Interpreter
from ontobdc.shared.domain.resource.logger import LogLevel
from ontobdc.shared.domain.port.logger import LogRepositoryPort
from ontobdc.a3.adapter.machine import SismicA3TransitionHandlerAdapter
from ontobdc.a3.adapter.repository import A3LocalStatechartRepository
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState
from ontobdc.a3.domain.port.machine import (
    EtlProcessStatePort,
    EtlStateTransitionHandlerPort,
    EtlStatechartRepositoryPort,
)


class StateWorkerAdapter:
    """
    Worker that executes the Sismic Statechart for a given physical package.
    """

    def __init__(self, log_repository: LogRepositoryPort, package_path: str | Path):
        self._log_repository: LogRepositoryPort = log_repository
        self._package_path: Path = Path(package_path)
        self._name: str = self._package_path.name
        self._handler: EtlStateTransitionHandlerPort = SismicA3TransitionHandlerAdapter(self._package_path)

    @property
    def name(self) -> str:
        return self._name

    def work(self) -> str:
        context: Dict[str, Any] = {
            "handler": self._handler,
            "EtlProcessStatePort": A3EtlProcessState,
        }

        initial_state: EtlProcessStatePort = self._handler.current_state
        initial_state_code: str = initial_state.value.strip("__")

        self._log_repository.log(
            LogLevel.INFORMATIONAL,
            f"Starting A3 pipeline for package '{self.name}' in state: {initial_state_code}",
        )

        statechart_repo: EtlStatechartRepositoryPort = A3LocalStatechartRepository()
        statechart: Statechart = statechart_repo.get_statechart()
        statechart.state_for(statechart.root).initial = initial_state_code

        interpreter: Interpreter = Interpreter(statechart, initial_context=context)
        interpreter.execute_once()

        while not interpreter.final:
            interpreter.execute_once()
            final_state: EtlProcessStatePort = self._handler.current_state

            if initial_state == final_state:
                stuck_state_code: str = final_state.value.strip("__")
                raise RuntimeError(f"State stuck at {stuck_state_code}. No transition was made.")

            initial_state = final_state

        final_state_code: str = self._handler.current_state.value.strip("__")
        return f"Package '{self.name}' processed successfully. Final state: {final_state_code}"
