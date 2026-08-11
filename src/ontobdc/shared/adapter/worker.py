import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import yaml
from sismic.interpreter import Interpreter
from sismic.io import import_from_yaml
from sismic.model import Statechart


class StateWorkerAdapter:
    def __init__(
        self,
        state_adapter: Type[Any],
        state_context_name: str,
        handler: Any,
        logger: Any,
        statechart_file_path: Path,
    ) -> None:
        self._state_adapter: Type[Any] = state_adapter
        self._state_context_name: str = state_context_name
        self._handler: Any = handler
        self._logger: Any = logger
        self._statechart_file_path: Path = statechart_file_path
        self._statechart_data: Dict[str, Any] = self._load_statechart_data()
        self._bind_state_adapter_metadata()

    @property
    def name(self) -> str:
        statechart_data: Dict[str, Any] = self._statechart_data.get("statechart", {})
        return str(statechart_data.get("name", self._statechart_file_path.stem))

    def work(self, stop_state: Optional[Any] = None) -> List[str]:
        initial_state: Any = self._handler.current_state
        if hasattr(self._logger, "log_info"):
            self._logger.log_info(
                f"Starting statechart '{self.name}' in state: {initial_state.value.strip('_')}",
            )

        statechart: Statechart = self._load_sismic_statechart()
        initial_state_code: str = initial_state.value.strip("_")
        statechart.state_for(statechart.root).initial = initial_state_code

        context: Dict[str, Any] = {
            "handler": self._handler,
            self._state_context_name: self._state_adapter,
        }
        interpreter: Interpreter = Interpreter(statechart, initial_context=context)
        self._bind_current_interpreter_state(interpreter, fallback_state=initial_state)
        visited_states: List[str] = [self._handler.current_state.value]

        if stop_state is not None and self._handler.current_state == stop_state:
            return visited_states

        if self._is_final_state(initial_state_code):
            return visited_states

        while not interpreter.final:
            previous_state: Any = self._handler.current_state
            previous_configuration: List[str] = list(getattr(interpreter, "configuration", []))
            interpreter.execute_once()
            self._bind_current_interpreter_state(interpreter, fallback_state=previous_state)
            current_state: Any = self._handler.current_state
            current_configuration: List[str] = list(getattr(interpreter, "configuration", []))

            if current_state == previous_state and current_configuration == previous_configuration:
                raise RuntimeError(
                    f"State stuck at {current_state.value.strip('_')}. No transition was made.",
                )

            if visited_states[-1] != current_state.value:
                visited_states.append(current_state.value)

            if stop_state is not None and current_state == stop_state:
                break

        return visited_states

    def _load_statechart_data(self) -> Dict[str, Any]:
        with open(self._statechart_file_path, "r", encoding="utf-8") as file_handle:
            return yaml.safe_load(file_handle) or {}

    def _bind_state_adapter_metadata(self) -> None:
        statechart_data: object = self._statechart_data.get("statechart")
        if not isinstance(statechart_data, dict):
            return

        root_state: object = statechart_data.get("root state")
        if not isinstance(root_state, dict):
            return

        self._bind_state_adapter_metadata_in_node(root_state)

    def _bind_state_adapter_metadata_in_node(self, node: Dict[str, Any]) -> None:
        for collection_name in ("states", "parallel states"):
            state_definitions: object = node.get(collection_name)
            if not isinstance(state_definitions, list):
                continue

            for state_definition in state_definitions:
                if not isinstance(state_definition, dict):
                    continue

                state_name: str = str(
                    state_definition.get("name", "")
                ).strip()
                if state_name:
                    try:
                        state: Any = self._state_adapter.get_state(state_name)
                    except (AttributeError, KeyError):
                        state = None

                    bind_metadata: Any = getattr(
                        state,
                        "bind_presentation_metadata",
                        None,
                    )
                    if callable(bind_metadata):
                        bind_metadata(
                            label=state_definition.get("label"),
                            description=state_definition.get("description"),
                        )

                self._bind_state_adapter_metadata_in_node(state_definition)

    def _bind_current_interpreter_state(
        self,
        interpreter: Interpreter,
        fallback_state: Any,
    ) -> None:
        configuration: List[str] = list(getattr(interpreter, "configuration", []))
        if configuration:
            state_name: str = configuration[-1]
            active_state: Any = self._state_adapter.get_state(state_name)
            self._handler.bind_active_state(active_state)
            return

        observed_state: Any = getattr(self._handler, "observed_state", fallback_state)
        self._handler.bind_active_state(observed_state)

    def _load_sismic_statechart(self) -> Statechart:
        cleaned_data: Dict[str, Any] = self._remove_presentation_metadata(
            self._statechart_data
        )
        file_descriptor: int
        temp_path: str
        file_descriptor, temp_path = tempfile.mkstemp(suffix=".yaml")

        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temp_file:
                yaml.dump(cleaned_data, temp_file)

            return import_from_yaml(filepath=temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _is_final_state(self, state_name: str) -> bool:
        statechart_data: Dict[str, Any] = self._statechart_data.get("statechart", {})
        root_state: object = statechart_data.get("root state")
        if not isinstance(root_state, dict):
            return False

        return self._is_final_state_in_node(root_state, state_name)

    @classmethod
    def _is_final_state_in_node(cls, node: Dict[str, Any], state_name: str) -> bool:
        states: object = node.get("states")
        if isinstance(states, list):
            for state_node in states:
                if not isinstance(state_node, dict):
                    continue

                if str(state_node.get("name", "")).strip() == state_name:
                    return str(state_node.get("type", "")).strip() == "final"

                if cls._is_final_state_in_node(state_node, state_name):
                    return True

        parallel_states: object = node.get("parallel states")
        if isinstance(parallel_states, list):
            for parallel_node in parallel_states:
                if not isinstance(parallel_node, dict):
                    continue
                if cls._is_final_state_in_node(parallel_node, state_name):
                    return True

        return False

    @classmethod
    def _remove_presentation_metadata(cls, node: Dict[str, Any]) -> Dict[str, Any]:
        cleaned_node: Dict[str, Any] = dict(node)
        for key, value in list(cleaned_node.items()):
            if key in {"description", "label"}:
                del cleaned_node[key]
                continue

            if isinstance(value, dict):
                cleaned_node[key] = cls._remove_presentation_metadata(value)
                continue

            if isinstance(value, list):
                cleaned_node[key] = cls._remove_presentation_metadata_list(value)

        return cleaned_node

    @classmethod
    def _remove_presentation_metadata_list(cls, items: List[Any]) -> List[Any]:
        cleaned_items: List[Any] = []
        for item in items:
            if isinstance(item, dict):
                cleaned_items.append(cls._remove_presentation_metadata(item))
                continue

            cleaned_items.append(item)

        return cleaned_items
