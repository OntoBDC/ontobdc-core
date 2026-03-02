---
code: SPEC001
title: Capability Structure Specification
status: Accepted
author: Elias M. P. Junior
date: 2026-02-25
tags: architecture, capability, standard
---

# Capability Structure Specification

This document defines the standard structure for implementing a **Capability** in the OntoBDC architecture. A Capability represents a discrete, executable unit of business logic that can be invoked via various interfaces (CLI, API, etc.).

## 1. File Location
Capabilities should be placed within the `module/<domain>/plugin/capability/` directory.
Example: `ontobdc/module/resource/plugin/capability/list_documents.py`

## 2. Class Definition
A Capability is a Python class that inherits from `ontobdc.run.core.capability.Capability`.

```python
from typing import Any, Dict
from ontobdc.run.core.capability import Capability, CapabilityMetadata

class MyCapability(Capability):
    """
    Docstring describing what the capability does.
    """
    ...
```

## 3. Metadata
The `METADATA` attribute is mandatory and must be an instance of `CapabilityMetadata`. It defines identity, documentation, and interface contracts.

```python
    METADATA = CapabilityMetadata(
        id="org.domain.capability.unique_id",
        version="0.1.0",
        name="Human Readable Name",
        description="Detailed description of functionality.",
        author=["Author Name"],
        tags=["tag1", "tag2"],
        supported_languages=["en", "pt_BR"],
        
        # INPUT CONTRACT
        input_schema={
            "type": "object",
            "properties": {
                "input_key": {
                    "type": ExpectedType,  # Python Type or "string", "integer"
                    "required": True,
                    "description": "Description of the input",
                    "check": [VerificationStrategy] # Optional list of verification strategies
                },
                # ...
            },
        },
        
        # OUTPUT CONTRACT
        output_schema={
            "type": "object",
            "properties": {
                "output_key": {
                    "type": "array", # or "string", "integer", "object"
                    "description": "Description of the output",
                },
            },
        },
        
        # ERROR CONTRACT
        raises=[
            {
                "code": "org.domain.exception.code",
                "python_type": "ValueError",
                "description": "When this error occurs",
            }
        ],
    )
```

## 4. Execution Logic
The `execute` method contains the core business logic. It **must not** contain interface-specific logic (like `argparse`, `print`, or `input`).
It receives a validated `inputs` dictionary and returns a dictionary matching `output_schema`.

```python
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Extract inputs (safe to assume they are validated/typed)
        repo = inputs.get("input_key")
        
        # 2. Perform business logic (delegate to Ports/Entities)
        result = repo.do_something()
        
        # 3. Return results
        return {
            "output_key": result
        }
```

## 5. CLI Strategy (Adapter)
To support CLI execution, the capability should implement `get_default_cli_strategy`. The strategy class itself should reside in `module/<domain>/adapter/cli_strategy.py` to keep the capability file clean.

```python
    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        from ontobdc.module.resource.adapter.cli_strategy import MyCapabilityCliStrategy
        return MyCapabilityCliStrategy(**kwargs)
```

### CLI Strategy Structure
The CLI Strategy handles parsing arguments and rendering output.

```python
class MyCapabilityCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        # Initialize with dependencies (e.g., repository)
        self.repository = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        # Configure argparse arguments
        parser.add_argument("--flag", ...)

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        # Map CLI args to Capability inputs
        inputs = {
            "input_key": self.repository,
            "other_input": args.flag
        }
        
        # Execute
        executor = CapabilityExecutor()
        result = executor.execute(capability, inputs)
        
        # Render
        self.render(console, args, capability, result)

    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        # format output (Rich Table, JSON, etc.)
        ...
```

## Key Principles
1.  **Separation of Concerns**: Capability handles *what* to do; Strategy handles *how* to invoke it and show results.
2.  **Declarative Validation**: Use `input_schema` and `check` strategies instead of manual validation code inside `execute`.
3.  **Typed Inputs**: Use Python types in schema (e.g., `FileRepositoryPort`) for stronger validation.
4.  **Clean Execution**: `execute` method should be pure business logic, delegating complex data access to Repositories.

## 7. Architectural Constraints

1.  **No Direct Filesystem Access**: Capabilities, Actions, Verifications, and Use Cases **MUST NEVER** access the filesystem directly (e.g., using `os.path`, `pathlib.Path.exists()`, `open()`). They **MUST ALWAYS** use a `RepositoryPort` to access data. This ensures the domain logic is decoupled from the physical storage.

## 8. Examples

Below are standard examples of capabilities implemented in the codebase.

### ListDocumentsCapability
*File: `module/resource/plugin/capability/list_documents.py`*

Lists all documents from a `FileRepositoryPort`, including subfolders.

- **ID**: `org.ontobdc.domain.resource.capability.list_documents`
- **Inputs**:
  - `org.ontobdc.domain.resource.document.repository.incoming` (DocumentRepositoryPort): Repository instance.
  - `start` (int): Starting index for pagination (0 = first).
  - `limit` (int): Maximum number of files to return (0 = no limit).
- **Outputs**:
  - `org.ontobdc.domain.resource.document.list.content` (array): List of document paths.
  - `org.ontobdc.domain.resource.document.list.count` (int): Number of documents listed.

### ListDocumentsByTypeCapability
*File: `module/resource/plugin/capability/list_documents_by_type.py`*

Lists documents in a repository filtered by type (e.g., `zip`, `pdf`).

- **ID**: `org.ontobdc.domain.resource.capability.list_documents_by_type`
- **Inputs**:
  - `repository` (DocumentRepositoryPort): Repository instance.
  - `file-type` (array): List of document types to filter by (e.g., `['pdf', 'json']`).
  - `file-name` (string, optional): Optional name pattern to filter by (glob or `regex:`).
  - `start` (int): Starting index for pagination.
  - `limit` (int): Maximum number of documents.
- **Outputs**:
  - `org.ontobdc.domain.resource.document.list.content` (array): List of document paths.
  - `org.ontobdc.domain.resource.document.list.count` (int): Number of documents listed.

### ListDocumentsByNamePatternCapability
*File: `module/resource/plugin/capability/list_documents_by_name_pattern.py`*

Lists documents in a repository filtered by name pattern. Supports glob patterns (e.g., `*.txt`) and regex (prefix with `regex:`).

- **ID**: `org.ontobdc.domain.resource.capability.list_documents_by_name_pattern`
- **Inputs**:
  - `repository` (DocumentRepositoryPort): Repository instance.
  - `file-name` (string): Name pattern to filter by. Default is glob. Use `regex:` prefix for regex.
  - `start` (int): Starting index for pagination.
  - `limit` (int): Maximum number of documents.
- **Outputs**:
  - `org.ontobdc.domain.resource.document.list.content` (array): List of document paths.
  - `org.ontobdc.domain.resource.document.list.count` (int): Number of documents listed.
