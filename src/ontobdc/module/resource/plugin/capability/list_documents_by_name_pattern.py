
import re
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional
from ontobdc.module.resource.adapter.renderer.document_list import DocumentListRenderer
from ontobdc.module.resource.audit.repository import HasReadPermission
from ontobdc.run.domain.capability import Capability, CapabilityMetadata
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort
from ontobdc.run.domain.port.contex import CliContextPort


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
                    "uri": "org.ontobdc.domain.resource.document.repository.incoming",
                    "required": True,
                    "description": "Repository instance (DocumentRepositoryPort)",
                    "check": [HasReadPermission]
                },
                "file_name": {
                    "type": "string",
                    "uri": "org.ontobdc.domain.resource.input.file.name",
                    "required": True,
                    "description": "Name pattern to filter by. Default is glob. Use 'regex:' prefix for regex.",
                },
                "start": {
                    "type": "integer",
                    "uri": "org.ontobdc.domain.resource.input.pagination.start",
                    "required": False,
                    "description": "Starting index for pagination (0 = first)",
                },
                "limit": {
                    "type": "integer",
                    "uri": "org.ontobdc.domain.resource.input.pagination.limit",
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

    def get_default_cli_renderer(self) -> Optional[Any]:
        return DocumentListRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repo: DocumentRepositoryPort = context.get_parameter_value("repository")
        pattern: str = context.get_parameter_value("file_name")
        limit: int = context.get_parameter_value("limit", 0)
        start: int = context.get_parameter_value("start", 0)

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
        for path in repo.iter_file_paths():
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
