from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type
from pathlib import Path

import yaml
from sismic.io import import_from_yaml
from sismic.model import FinalState, Statechart
from sismic.interpreter import Interpreter

from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.domain.port.worker import ChainOfResponsibilityWorkerPort
from ontobdc.shared.adapter.chain_loader import ChainResponsibilityLoader
from ontobdc.shared.domain.port.resolver import DynamicParamResolverPort
from ontobdc.shared.domain.port.capability import CapabilityPort


class ChainOfResponsibilityWorkerAdapter(
    ChainOfResponsibilityWorkerPort,
):
    """
    Interpret a chain statechart declared entirely in its YAML file.

    Every region, state, transition, guard and action of the chain is
    declared in the YAML. Each responsibility region names its capability
    by ID in its guards and actions (``worker.can_handle('<id>')`` and
    ``worker.execute_responsibility('<id>')``); the worker resolves that ID
    through ``ChainResponsibilityLoader`` against the chain's ``support``
    contract, evaluates ``can_handle`` and executes the capability. The
    worker never adds, removes or renames states or regions.
    """

    PRESENTATION_KEYS: Tuple[str, ...] = ("description", "label")

    def __init__(
        self,
        support: Type[ChainResponsibilityPort],
        context: CliContextPort,
        logger: Any,
        statechart_file_path: Path,
        root_packages: Tuple[str, ...] = ("ontobdc",),
        resolver: Optional[DynamicParamResolverPort] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._support: Type[ChainResponsibilityPort] = support
        self._context: CliContextPort = context
        self._logger: Any = logger
        self._statechart_file_path: Path = statechart_file_path
        self._responsibility_loader: ChainResponsibilityLoader = (
            ChainResponsibilityLoader(root_packages=root_packages)
        )
        self._resolver: DynamicParamResolverPort = resolver or StrategyParamResolver(
            ResolverLoader(root_packages=root_packages)
        )
        self._extra_data: Optional[Dict[str, Any]] = extra_data
        self._statechart_data: Dict[str, Any] = self._load_statechart_data()
        self._responsibilities: Dict[str, CapabilityPort] = {}
        self._results: Dict[str, Dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return str(self._statechart_data["statechart"]["name"])

    def work(self) -> Dict[str, Dict[str, Any]]:
        self._responsibilities = {}
        self._results = {}

        statechart: Statechart = import_from_yaml(
            text=yaml.safe_dump(
                self._without_presentation_metadata(self._statechart_data)
            )
        )
        interpreter: Interpreter = Interpreter(
            statechart,
            initial_context={"worker": self},
        )
        while interpreter.execute_once() is not None:
            pass

        self._ensure_every_region_completed(statechart, interpreter)
        return dict(self._results)

    def can_handle(self, responsibility_id: str) -> bool:
        return self._responsibility(responsibility_id).can_handle(
            self._context,
            self._extra_data,
        )

    def execute_responsibility(
        self,
        responsibility_id: str,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = CapabilityExecutor.execute(
            self._responsibility(responsibility_id),
            self._context,
            self._resolver,
        )
        self._results[responsibility_id] = result
        return result

    def _responsibility(self, responsibility_id: str) -> CapabilityPort:
        if responsibility_id in self._responsibilities:
            return self._responsibilities[responsibility_id]

        responsibility_type: Optional[Type[CapabilityPort]] = (
            self._responsibility_loader.get(self._support, responsibility_id)
        )
        if responsibility_type is None:
            raise ValueError(
                f"Chain '{self.name}' declares responsibility "
                f"'{responsibility_id}', but no capability implementing "
                f"{self._support.__name__} has that ID."
            )

        capability: CapabilityPort = responsibility_type()
        self._responsibilities[responsibility_id] = capability
        return capability

    def _ensure_every_region_completed(
        self,
        statechart: Statechart,
        interpreter: Interpreter,
    ) -> None:
        active_final_parents: List[Optional[str]] = [
            statechart.parent_for(state_name)
            for state_name in interpreter.configuration
            if isinstance(statechart.state_for(state_name), FinalState)
        ]
        region_name: str
        for region_name in statechart.children_for(statechart.root):
            if region_name not in active_final_parents:
                raise RuntimeError(
                    f"Chain '{self.name}' is stuck: region '{region_name}' "
                    "did not reach its final state."
                )

    def _load_statechart_data(self) -> Dict[str, Any]:
        with open(
            self._statechart_file_path,
            "r",
            encoding="utf-8",
        ) as file_handle:
            statechart_data: Any = yaml.safe_load(file_handle)

        if not isinstance(statechart_data, dict) or not isinstance(
            statechart_data.get("statechart"), dict
        ):
            raise ValueError(
                f"Chain YAML must declare a 'statechart': "
                f"{self._statechart_file_path}"
            )
        return statechart_data

    @classmethod
    def _without_presentation_metadata(cls, node: Any) -> Any:
        if isinstance(node, dict):
            return {
                key: cls._without_presentation_metadata(value)
                for key, value in node.items()
                if key not in cls.PRESENTATION_KEYS
            }
        if isinstance(node, list):
            return [cls._without_presentation_metadata(item) for item in node]
        return node
