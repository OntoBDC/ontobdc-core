
from typing import Any, Dict, Optional
from ontobdc.module.resource.adapter.renderer.file_list import FileListRenderer
from ontobdc.module.resource.audit.repository import HasReadPermission
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from ontobdc.run.core.port.contex import CliContextPort


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
                "repository": {
                    "type": DocumentRepositoryPort,
                    "uri": "org.ontobdc.domain.resource.document.repository.incoming",
                    "required": True,
                    "description": "Repository instance (DocumentRepositoryPort)",
                    "check": [HasReadPermission]
                },
                "start": {
                    "type": "integer",
                    "uri": "org.ontobdc.domain.context.input.pagination.start",
                    "required": False,
                    "description": "Starting index for pagination (0 = first)",
                },
                "limit": {
                    "type": "integer",
                    "uri": "org.ontobdc.domain.context.input.pagination.limit",
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

    def get_default_cli_renderer(self) -> Optional[Any]:
        return FileListRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        # Extract repository parameter value
        repo: DocumentRepositoryPort = context.get_parameter_value("repository")

        limit_param = context.get_parameter_value("limit")
        limit = limit_param["value"] if limit_param else 0

        start_param = context.get_parameter_value("start")
        start = start_param["value"] if start_param else 0

        files = repo.get_all()
        if start > 0:
            files = files[start:]

        if limit > 0:
            files = files[:limit]

        return {
            "org.ontobdc.domain.resource.document.list.content": files,
            "org.ontobdc.domain.resource.document.list.count": len(files),
        }