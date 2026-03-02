from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from ontobdc.core.domain.port.verification import SelfVerifiablePort


@dataclass
class CapabilityMetadata:
    id: str
    version: str
    name: str
    description: str
    author: str
    tags: List[str] = field(default_factory=list)
    supported_languages: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    raises: Optional[List[Dict[str, Any]]] = None


class Capability(SelfVerifiablePort):
    METADATA: CapabilityMetadata

    @property
    def metadata(self) -> CapabilityMetadata:
        return self.METADATA

    def check_inputs(self, inputs: Dict[str, Any]) -> None:
        for prop, spec in self.metadata.input_schema.get("properties", {}).items():
            required = spec.get("required", False)
            if required and prop not in inputs:
                raise ValueError(f"Missing required input: {prop}")
            
            if prop in inputs:
                input_value = inputs[prop]
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
                        
                    if not strategy.verify(prop, input_value, inputs):
                        raise ValueError(f"Input {prop} failed verification strategy {strategy.__class__.__name__}")

    @abstractmethod
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None


class CapabilityExecutor:
    def execute(self, capability: Capability, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the given capability with the provided inputs.

        :param capability: The capability to execute.
        :param inputs: The inputs to pass to the capability.
        :return: The output of the capability execution.
        """
        if isinstance(capability, SelfVerifiablePort):
            capability.check_inputs(inputs)

        return capability.execute(inputs)


class CapabilityRegistry:
    _registry: Dict[str, Type[Capability]] = {}

    @classmethod
    def register(cls, cap_cls: Type[Capability]) -> None:
        meta = getattr(cap_cls, "METADATA", None)
        if not meta:
            return
        cap_id = getattr(meta, "id", None)
        if not cap_id:
            return
        cls._registry[cap_id] = cap_cls

    @classmethod
    def register_many(cls, cap_classes: List[Type[Capability]]) -> None:
        for c in cap_classes:
            cls.register(c)

    @classmethod
    def get(cls, cap_id: str) -> Optional[Type[Capability]]:
        return cls._registry.get(cap_id)

    @classmethod
    def get_all(cls) -> Dict[str, Type[Capability]]:
        return dict(cls._registry)

    @classmethod
    def get_by_attr(cls, attributes: Dict[str, Any]) -> Dict[str, Type[Capability]]:
        matched = {}
        for cid, cap_cls in cls._registry.items():
            meta = getattr(cap_cls, "METADATA", None)
            if not meta or not meta.input_schema:
                continue

            props = meta.input_schema.get("properties", {})
            
            # 1. Relevance check: At least one input must be in attributes (to filter context)
            if not any(key in props for key in attributes):
                continue

            # 2. Requirement check: All required inputs must be in attributes
            missing_required = False
            for prop_name, prop_spec in props.items():
                if prop_spec.get("required", False) and prop_name not in attributes:
                    missing_required = True
                    break
            
            if not missing_required:
                matched[cid] = cap_cls
        
        return matched

