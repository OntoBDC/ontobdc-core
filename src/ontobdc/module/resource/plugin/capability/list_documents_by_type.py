
from fnmatch import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.module.resource.adapter.strategy.cli_file import ListFilesCliStrategy
from ontobdc.module.resource.audit.repository import HasReadPermission
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata


class ListDocumentsByTypeCapability(Capability):
    """
    Capability to list documents in a repository filtered by type.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents_by_type",
        version="0.1.0",
        name="List Documents by Type",
        description="Lists documents from a DocumentRepositoryPort filtered by type.",
        author=["Elias M. P. Junior"],
        tags=["resource", "document", "listing", "type"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": DocumentRepositoryPort,
                    "required": True,
                    "description": "Repository instance (DocumentRepositoryPort)",
                    "check": [HasReadPermission]
                },
                "file-type": {
                    "type": "array",
                    "required": True,
                    "description": "List of document types to filter by (e.g., ['pdf', 'json'])",
                },
                "file-name": {
                    "type": "string",
                    "required": False,
                    "description": "Optional name pattern to filter by (glob or regex:)",
                },
                "start": {
                    "type": "integer",
                    "required": False,
                    "description": "Starting index for pagination (0 = first)",
                },
                "limit": {
                    "type": "integer",
                    "required": False,
                    "description": "Maximum number of documents to return (0 = no limit)",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.resource.document.list.content": {
                    "type": "array",
                    "description": "List of document paths",
                },
                "org.ontobdc.domain.resource.document.list.count": {
                    "type": "integer",
                    "description": "Number of documents listed",
                },
            },
        },
        raises=[
            {
                "code": "org.ontobdc.domain.resource.document.exception.repository_not_configured",
                "python_type": "ValueError",
                "description": "File repository not configured for capability",
            },
            {
                "code": "org.ontobdc.domain.resource.document.exception.invalid_type_filter",
                "python_type": "ValueError",
                "description": "Invalid or empty type filter provided",
            },
        ],
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListFilesCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        types: List[str] = inputs.get("file-type", [])
            
        limit: int = inputs.get("limit", 0)
        start: int = inputs.get("start", 0)
        repository: DocumentRepositoryPort = inputs.get("repository")

        if not types:
            raise ValueError("Types must be a non-empty list of strings")

        documents: List[Any] = []
        for t in types:
            docs = repository.get_by_type(t)
            if isinstance(docs, list):
                documents.extend(docs)

        # Apply name pattern filtering if provided
        name_pattern: Optional[str] = inputs.get("file-name")
        if name_pattern:
            is_regex = False
            regex = None
            if name_pattern.startswith("regex:"):
                is_regex = True
                try:
                    regex = re.compile(name_pattern[6:])
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern: {e}")

            filtered_by_name: List[Any] = []
            for doc in documents:
                name = self._extract_name(doc)
                if not name:
                    continue
                
                # Extract filename from path if needed
                filename = Path(name).name
                
                if is_regex:
                    if regex and regex.match(filename):
                        filtered_by_name.append(doc)
                else:
                    if fnmatch(filename, name_pattern):
                        filtered_by_name.append(doc)
            documents = filtered_by_name

        if start > 0:
            documents = documents[start:]

        if limit > 0:
            documents = documents[:limit]

        return {
            "org.ontobdc.domain.resource.document.list.content": documents,
            "org.ontobdc.domain.resource.document.list.count": len(documents),
        }

    def _extract_name(self, doc: Any) -> Optional[str]:
        if isinstance(doc, dict):
            for key in ("name", "filename", "file_name", "path", "filepath", "file"):
                value = doc.get(key)
                if isinstance(value, str):
                    return value
            return None
        if isinstance(doc, str):
            return doc
        return None
