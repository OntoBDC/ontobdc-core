# SPEC004: RO-Crate Parsing and Repository Abstraction

## 1. Context

Capabilities often need to inspect metadata (like `ro-crate-metadata.json`) to discover entities, such as WhatsApp accounts, documents, or datasets.
The `ro-crate` Python library exists and provides convenient object-oriented methods for interacting with RO-Crates, such as `crate.get_entities_by_type(...)`.
However, the OntoBDC architecture strictly enforces access via `DocumentRepositoryPort` to support distributed and remote data sources, prohibiting direct filesystem access.

## 2. Problem

Using the `ro-crate` library typically requires initializing a `ROCrate` object with a local filesystem path (e.g., `ROCrate('/path/to/crate')`).
This creates a tight coupling to the local filesystem and bypasses the repository abstraction, violating the core architectural constraint:
"Capabilities MUST NEVER access the filesystem directly. They MUST ALWAYS use a REPOSITORY."

Additionally, adding a heavy dependency just for simple read/filter operations (like finding a specific entity type in a JSON-LD graph) introduces unnecessary overhead and complexity.

## 3. Decision

1.  **Repository-First Access**: Capabilities MUST use `repository.get_json(path)` (or equivalent repository methods) to retrieve metadata content as a Python dictionary/list.
2.  **Manual/Lightweight Parsing**: Capabilities MUST parse the JSON content (typically JSON-LD graphs) manually or using lightweight, dependency-free helper functions.
    *   Iterate over the `@graph` list.
    *   Check `@type` and other properties directly in the dictionary.
3.  **Avoid `ro-crate` Library**: Capabilities SHOULD NOT import or use the `ro-crate` library if it requires direct filesystem paths or adds significant dependencies for simple read-only tasks.

## 4. Rationale

*   **Architecture Compliance**: `DocumentRepositoryPort` is the single source of truth for data access. Direct filesystem access breaks support for remote repositories (e.g., S3, API-based).
*   **Dependency Management**: Avoids adding a large dependency (`rocrate`) for operations that are trivial to implement with standard Python data structures (dictionaries/lists).
*   **Performance**: Parsing a dictionary is faster and consumes less memory than initializing a full object graph for simple filtering tasks.
*   **Simplicity**: Keeps capabilities self-contained and focused on logic rather than library integration complexity.

## 5. Example Implementation

The pattern for finding entities in an RO-Crate metadata file without the library:

```python
# GOOD: Using repository and manual parsing
def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    repository: DocumentRepositoryPort = inputs["repository"]
    crate_path = "path/to/ro-crate-metadata.json"
    
    # 1. Retrieve JSON content via repository
    crate_content = repository.get_json(crate_path)
    
    found_entities = []
    if crate_content and "@graph" in crate_content:
        # 2. Iterate over the graph manually
        for node in crate_content["@graph"]:
            node_type = node.get("@type")
            
            # Normalize type to list for checking (JSON-LD can have single string or list)
            if not isinstance(node_type, list):
                node_type = [node_type]
            
            # 3. Filter by type
            if "urn:example:MyType" in node_type:
                found_entities.append(node)

    return {"entities": found_entities}
```

```python
# BAD: Using ro-crate library with filesystem path
from rocrate.rocrate import ROCrate

def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # VIOLATION: Direct filesystem access required
    crate = ROCrate('/absolute/path/to/crate') 
    entities = crate.get_entities_by_type("urn:example:MyType")
    return {"entities": entities}
```
