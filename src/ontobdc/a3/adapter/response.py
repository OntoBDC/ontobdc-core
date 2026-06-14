
import json
from dataclasses import dataclass, asdict
from ontobdc.a3.domain.machine.lifecycle import A3EtlProcessState


@dataclass
class TransformationResponse:
    resultingState: A3EtlProcessState
    URI: str = "http://ontobdc.org/ontology/domain/ns.ttl#TransformationResponse"

    def __str__(self) -> str:
        return json.dumps(asdict(self), indent=2)