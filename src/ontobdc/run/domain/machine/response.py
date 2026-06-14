
import json
from typing import List, Dict, Any, Iterator, Tuple
from dataclasses import dataclass, field
from dataclasses import asdict
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix

OBDC = get_ontology_by_prefix("obdc")


@dataclass
class IntentScoreResponse:
    text: str
    entities: List[Dict[str, Any]]
    pos_tags: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    roots: List[Dict[str, Any]]
    score: float
    matching_capabilities: List[str] = field(default_factory=list)
    supporting_capabilities: List[str] = field(default_factory=list)

    CANONICALIZED_INTENT_FILE_NAME: str = "context_canonicalized_intent.jsonld"
    PARSED_INTENT_FILE_NAME: str = "context_parsed_intent.jsonld"
    INTENT_SCORE_THRESHOLD: float = 0.8
    URI: str = OBDC["IntentScoreResponse"]

    def serialize(self) -> Dict[str, Any]:
        def serialize_item(item: Dict[str, Any], key_map: Dict[str, str]) -> Dict[str, Any]:
            node: Dict[str, Any] = {}

            if "uri" in item and item["uri"]:
                node["@type"] = str(item["uri"]).replace("http://purl.org/olia/olia.owl#", "olia:")

            for source_key, target_key in key_map.items():
                value = item.get(source_key)
                if value not in (None, ""):
                    node[target_key] = value

            return node

        jsonld: Dict[str, Any] = {
            "@context": {
                "obdc": str(OBDC),
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "olia": "http://purl.org/olia/olia.owl#",
                "intentText": "obdc:intentText",
                "intentScore": {
                    "@id": "obdc:intentScore",
                    "@type": "xsd:double",
                },
                "hasEntity": {
                    "@id": "obdc:hasEntity",
                    "@container": "@set",
                },
                "hasPosTag": {
                    "@id": "obdc:hasPosTag",
                    "@container": "@set",
                },
                "hasDependency": {
                    "@id": "obdc:hasDependency",
                    "@container": "@set",
                },
                "hasRoot": {
                    "@id": "obdc:hasRoot",
                    "@container": "@set",
                },
                "hasMatchingCapability": {
                    "@id": "obdc:hasMatchingCapability",
                    "@container": "@set",
                },
                "hasSupportingCapability": {
                    "@id": "obdc:hasSupportingCapability",
                    "@container": "@set",
                },
                "itemText": "obdc:itemText",
                "itemLabel": "obdc:itemLabel",
                "itemPos": "obdc:itemPos",
                "itemDep": "obdc:itemDep",
                "itemHead": "obdc:itemHead",
                "itemLemma": "obdc:itemLemma",
            },
            "@type": "obdc:IntentScoreResponse",
            "intentText": self.text,
            "intentScore": self.score,
            "hasEntity": [
                serialize_item(entity, {
                    "text": "itemText",
                    "label": "itemLabel",
                })
                for entity in self.entities
            ],
            "hasPosTag": [
                serialize_item(pos_tag, {
                    "text": "itemText",
                    "pos": "itemPos",
                })
                for pos_tag in self.pos_tags
            ],
            "hasDependency": [
                serialize_item(dependency, {
                    "text": "itemText",
                    "dep": "itemDep",
                    "head": "itemHead",
                })
                for dependency in self.dependencies
            ],
            "hasRoot": [
                serialize_item(root, {
                    "text": "itemText",
                    "pos": "itemPos",
                    "lemma": "itemLemma",
                })
                for root in self.roots
            ],
            "hasMatchingCapability": self.matching_capabilities,
            "hasSupportingCapability": self.supporting_capabilities,
        }

        return jsonld

    @classmethod
    def load_from_jsonld(cls, parsed_intent: Any) -> 'IntentScoreResponse':
        if not isinstance(parsed_intent, dict):
            raise ValueError("Parsed intent must be a JSON object.")

        def expand_olia_uri(value: Any) -> Any:
            if not isinstance(value, str):
                return value

            if value.startswith("olia:"):
                return value.replace("olia:", "http://purl.org/olia/olia.owl#", 1)

            return value

        def load_items(items: Any, key_map: Dict[str, str]) -> List[Dict[str, Any]]:
            if not isinstance(items, list):
                return []

            loaded_items: List[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                loaded_item: Dict[str, Any] = {}
                if "@type" in item:
                    loaded_item["uri"] = expand_olia_uri(item["@type"])

                for source_key, target_key in key_map.items():
                    if source_key in item:
                        loaded_item[target_key] = item[source_key]

                loaded_items.append(loaded_item)

            return loaded_items

        text = parsed_intent.get("intentText")
        score = parsed_intent.get("intentScore")

        if not isinstance(text, str) or not text.strip():
            raise ValueError("Parsed intent must contain a non-empty 'intentText' field.")

        if not isinstance(score, (int, float)):
            raise ValueError("Parsed intent must contain a numeric 'intentScore' field.")

        matching_capabilities = parsed_intent.get("hasMatchingCapability", [])
        if not isinstance(matching_capabilities, list):
            matching_capabilities = []

        supporting_capabilities = parsed_intent.get("hasSupportingCapability", [])
        if not isinstance(supporting_capabilities, list):
            supporting_capabilities = []

        return cls(
            text=text,
            entities=load_items(
                parsed_intent.get("hasEntity", []),
                {
                    "itemText": "text",
                    "itemLabel": "label",
                },
            ),
            pos_tags=load_items(
                parsed_intent.get("hasPosTag", []),
                {
                    "itemText": "text",
                    "itemPos": "pos",
                },
            ),
            dependencies=load_items(
                parsed_intent.get("hasDependency", []),
                {
                    "itemText": "text",
                    "itemDep": "dep",
                    "itemHead": "head",
                },
            ),
            roots=load_items(
                parsed_intent.get("hasRoot", []),
                {
                    "itemText": "text",
                    "itemPos": "pos",
                    "itemLemma": "lemma",
                },
            ),
            score=float(score),
            matching_capabilities=matching_capabilities,
            supporting_capabilities=supporting_capabilities,
        )

    def __iter__(self) -> Iterator[Tuple[str, Any]]:
        return iter(asdict(self).items())

    def __str__(self) -> str:
        return json.dumps(asdict(self), indent=2)
