
from typing import Any, Dict, Optional
from ontobdc.module.resource.adapter.strategy.cli_file import ListFilesCliStrategy
from ontobdc.module.resource.audit.repository import HasReadPermission
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata


class ListDocumentsCapability(Capability):
    """
    Capability to list documents in a repository.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents",
        version="0.1.0",
        name="List All Documents",
        description="Lists all documents from a FileRepositoryPort, including subfolders.",
        author=["Elias M. P. Junior"],
        tags=["resource", "document", "file", "listing"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.resource.document.repository.incoming": {
                    "type": DocumentRepositoryPort,
                    "required": True,
                    "description": "Repository instance (DocumentRepositoryPort)",
                    "check": [HasReadPermission]
                },
                "start": {
                    "type": "integer",
                    "required": False,
                    "description": "Starting index for pagination (0 = first)",
                },
                "limit": {
                    "type": "integer",
                    "required": False,
                    "description": "Maximum number of files to return (0 = no limit)",
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
            }
        ],
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListFilesCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repo: DocumentRepositoryPort = inputs.get("org.ontobdc.domain.resource.document.repository.incoming") or inputs.get("repository")
        limit: int = inputs.get("limit", 0)

        files = repo.get_all()
        start: int = inputs.get("start", 0)
        if start > 0:
            files = files[start:]

        if limit > 0:
            files = files[:limit]

        return {
            "org.ontobdc.domain.resource.document.list.content": files,
            "org.ontobdc.domain.resource.document.list.count": len(files),
        }