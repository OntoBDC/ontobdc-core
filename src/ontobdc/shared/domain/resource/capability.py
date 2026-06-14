
from pathlib import Path
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.resource.context import CapabilityParamResolverRunner
from ontobdc.shared.domain.port.resolver import CapabilityParamResolverRunnerPort
from ontobdc.shared.domain.port.capability import TransactionCapabilityPort, CapabilityPort, QueryCapabilityPort, TransformationCapabilityPort



@dataclass
class CapabilityMetadata:
    id: str
    version: str
    name: str
    description: str
    author: str
    tags: Any = field(default_factory=list)
    supported_languages: List[str] = field(default_factory=list)
    require: Optional[Dict[str, List[str]]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    raises: Optional[List[Dict[str, Any]]] = None


class Capability(CapabilityPort):
    METADATA: CapabilityMetadata

    @property
    def metadata(self) -> CapabilityMetadata:
        return self.METADATA

    def tags(self, lang: str = "en") -> List[str]:
        """
        Returns the tags in the specified language.
        """
        if isinstance(self.metadata.tags, dict):
            return self.metadata.tags.get(lang, self.metadata.tags.get("en", []))
        return self.metadata.tags

    def check_inputs(self, context: CliContextPort) -> None:
        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            required = spec.get("required", False)
            if required and not context.has_parameter(prop):
                raise ValueError(f"Missing required input: {prop}")
            
            if context.has_parameter(prop):
                input_value = context.get_parameter_value(prop)
                prop_type = spec.get("type", None)
                
                if prop_type:
                    valid = True
                    if isinstance(prop_type, type):
                        if not isinstance(input_value, prop_type):
                            valid = False
                    elif prop_type == "integer":
                        if not isinstance(input_value, int):
                            valid = False
                    elif prop_type == "string":
                        if not isinstance(input_value, str):
                            valid = False
                    elif prop_type == "boolean":
                        if not isinstance(input_value, bool):
                            valid = False

                    if not valid:
                        raise ValueError(f"Input {prop} has type {type(input_value)}, expected {prop_type}") 

                # Check verification strategies
                for check in spec.get("check", []):
                    strategy = check
                    if isinstance(strategy, type):
                        strategy = strategy()

                    if not strategy.verify(prop, input_value, context):
                        raise ValueError(f"Input {prop} failed verification strategy {strategy.__class__.__name__}")

    def resolve_inputs(self, context: CliContextPort) -> None:
        """
        Resolve the inputs of the capability.
        """
        resolver: CapabilityParamResolverRunnerPort = CapabilityParamResolverRunner()

        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            prop_uri: str = spec.get("uri", None)

            if not isinstance(prop_uri, str) or not prop_uri.strip():
                continue

            resolver.resolve(context, prop_uri, prop)

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None

    @abstractmethod
    def label(self, lang: str = "en") -> str:
        """
        Returns the label of the capability in the specified language.
        :param lang: The language to use.
        :return: The label of the capability in the specified language.
        """
        ...

    @abstractmethod
    def description(self, lang: str = "en") -> str:
        """
        Returns the description of the capability in the specified language.
        :param lang: The language to use.
        :return: The description of the capability in the specified language.
        """
        ...

    def __str__(self) -> str:
        return f"{self.metadata.id}"

    def __repr__(self) -> str:
        return f"{self.metadata.id}"


class QueryCapability(Capability, QueryCapabilityPort):
    pass


class TransformationCapability(Capability, TransformationCapabilityPort):
    pass


class TransactionCapability(Capability, TransactionCapabilityPort):
    pass


class CapabilityExecutor:
    @staticmethod
    def execute(capability: Capability, context: CliContextPort) -> Dict[str, Any]:
        """
        Execute the given capability with the provided context.

        :param capability: The capability to execute.
        :param context: The context to pass to the capability.
        :return: The output of the capability execution.
        """
        if isinstance(capability, CapabilityPort):
            capability.resolve_inputs(context)

            capability.check_inputs(context)

        return capability.execute(context)
