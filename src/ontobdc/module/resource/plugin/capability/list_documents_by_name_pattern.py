
import re
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional
from ontobdc.module.resource.audit.repository import HasReadPermission
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from ontobdc.module.resource.adapter.strategy.cli_file import ListFilesCliStrategy
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort


class ListDocumentsByNamePatternCapability(Capability):
    """
    Capability to list documents in a repository filtered by name pattern.
    Supports glob patterns (e.g. *.txt) and regex (prefix with 'regex:').
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents_by_name_pattern",
        version="0.1.0",
        name="List Documents by Name Pattern",
        description="Lists documents from a FileRepositoryPort filtered by name pattern (glob or regex).",
        author=["Elias M. P. Junior"],
        tags=["resource", "document", "file", "listing", "pattern", "regex"],
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
                "file-name": {
                    "type": "string",
                    "required": True,
                    "description": "Name pattern to filter by. Default is glob. Use 'regex:' prefix for regex.",
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
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListFilesCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repo: DocumentRepositoryPort = inputs.get("repository")
        pattern: str = inputs.get("file-name")
        
        # Check for legacy/alias input
        if not pattern:
            pattern = inputs.get("name_pattern")

        if not pattern:
            raise ValueError("Name pattern is required")

        limit: int = inputs.get("limit", 0)
        start: int = inputs.get("start", 0)

        is_regex = False
        if pattern.startswith("regex:"):
            is_regex = True
            pattern = pattern[6:]
            try:
                regex = re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")

        documents: List[Any] = []
        
        # Use iter_file_paths for efficient traversal
        # Note: This might be slow for very large repos if we don't have a optimized search method in repo
        # ideally repo should support search_by_pattern, but for now we iterate.
        repository: DocumentRepositoryPort = inputs.get("repository")
        
        for path in repository.iter_file_paths():
            name = path.name
            match = False
            if is_regex:
                if regex.search(name):
                    match = True
            else:
                if fnmatch(name, pattern):
                    match = True
            
            if match:
                documents.append(str(path))

        if start > 0:
            documents = documents[start:]

        if limit > 0:
            documents = documents[:limit]

        return {
            "org.ontobdc.domain.resource.document.list.content": documents,
            "org.ontobdc.domain.resource.document.list.count": len(documents),
        }
