from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


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


class Capability:
    METADATA: CapabilityMetadata

    @property
    def metadata(self) -> CapabilityMetadata:
        return self.METADATA

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        return None


class CapabilityExecutor:
    def execute(self, capability: Capability, inputs: Dict[str, Any]) -> Dict[str, Any]:
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

