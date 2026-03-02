from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
from ontobdc.core.domain.port.verification import SelfVerifiablePort, VerificationStrategyPort


@dataclass
class ActionMetadata:
    id: str
    version: str
    name: str
    description: str
    author: List[str]
    tags: List[str] = field(default_factory=list)
    supported_languages: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    raises: Optional[List[Dict[str, Any]]] = None


class Action(SelfVerifiablePort):
    """
    Base class for Level 2 Actions (Stateless Transformation/Creation).
    Actions modify data or create files but do not manage business state transitions.
    """
    METADATA: ActionMetadata

    @property
    def metadata(self) -> ActionMetadata:
        return self.METADATA

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def check(self, inputs: Dict[str, Any]) -> bool:
        """
        Validates if the inputs are sufficient to run the action.
        """
        return True

    def check_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Implementation of SelfVerifiablePort.check_inputs.
        Delegates to check() for backward compatibility.
        """
        return self.check(inputs)

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None


class ActionExecutor:
    def execute(self, action: Action, inputs: Dict[str, Any], verification_strategy: Optional[VerificationStrategyPort] = None) -> Dict[str, Any]:
        # 1. Self-Check
        if not action.check(inputs):
            raise ValueError(f"Action {action.metadata.name} failed self-verification check.")
        
        # 2. External Strategy Check (if provided)
        if verification_strategy:
            if not verification_strategy.verify(inputs):
                raise ValueError(f"Action {action.metadata.name} failed external verification strategy.")

        return action.execute(inputs)


class ActionRegistry:
    _registry: Dict[str, Type[Action]] = {}

    @classmethod
    def register(cls, action_cls: Type[Action]) -> None:
        meta = getattr(action_cls, "METADATA", None)
        if not meta:
            return
        action_id = getattr(meta, "id", None)
        if not action_id:
            return
        cls._registry[action_id] = action_cls

    @classmethod
    def register_many(cls, action_classes: List[Type[Action]]) -> None:
        for c in action_classes:
            cls.register(c)

    @classmethod
    def get(cls, action_id: str) -> Optional[Type[Action]]:
        return cls._registry.get(action_id)

    @classmethod
    def get_all(cls) -> Dict[str, Type[Action]]:
        return dict(cls._registry)

    @classmethod
    def get_by_attr(cls, attributes: Dict[str, Any]) -> Dict[str, Type[Action]]:
        matched = {}
        for aid, action_cls in cls._registry.items():
            meta = getattr(action_cls, "METADATA", None)
            if not meta or not meta.input_schema:
                # If no schema, assume no requirements? Or always include?
                # For consistency with capabilities, if no schema, we might skip or include.
                # CapabilityRegistry skips if not meta or not meta.input_schema.
                # Let's verify CapabilityRegistry behavior.
                # It says: if not meta or not meta.input_schema: continue
                # So capabilities without schema are NOT discoverable by attributes.
                # Let's stick to that for consistency.
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
                matched[aid] = action_cls
        
        return matched
