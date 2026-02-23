import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from stack.run.capability_core import Capability, CapabilityExecutor, CapabilityMetadata
from stack.core.src.adapter import TableViewAdapter
from stack.resource.src.domain.port.repository import FileRepositoryPort


class ListDocumentsByTemplateCapability(Capability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents_by_template",
        version="0.1.0",
        name="List Documents by Template",
        description="Lists documents from a FileRepositoryPort filtered by mimetypes.",
        author="Elias M. P. Junior",
        tags=["resource", "document", "file", "listing", "template", "mimetype"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "object",
                    "required": True,
                    "description": "Repository instance (FileRepositoryPort)",
                },
                "mimetypes": {
                    "type": "array",
                    "required": False,
                    "description": "Optional list of mimetypes to filter by",
                },
                "limit": {
                    "type": "integer",
                    "required": False,
                    "description": "Maximum number of documents to return (0 = no limit)",
                },
                "base_path": {
                    "type": "string",
                    "required": False,
                    "description": "Base filesystem path to restrict documents to",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.domain.resource.document.list_by_template.content": {
                    "type": "array",
                    "description": "List of documents",
                },
                "org.ontobdc.domain.resource.document.list_by_template.count": {
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
        ],
    )

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repo = inputs.get("repository")
        if not isinstance(repo, FileRepositoryPort):
            raise ValueError("Repository must be a FileRepositoryPort")
        mimetypes = inputs.get("mimetypes")
        limit = inputs.get("limit")
        base_path = inputs.get("base_path")
        documents: List[Any] = []
        if isinstance(mimetypes, list) and mimetypes:
            for mt in mimetypes:
                if not isinstance(mt, str):
                    raise ValueError("Each mimetype must be a string")
                docs = repo.get_by_mimetype(mt)
                if isinstance(docs, list):
                    documents.extend(docs)
        else:
            docs = repo.get_by_mimetype(None)
            if isinstance(docs, list):
                documents.extend(docs)
        if isinstance(base_path, str) and base_path:
            base = Path(base_path).resolve()
            filtered: List[Any] = []
            for doc in documents:
                name = self._extract_name(doc)
                if not name:
                    continue
                try:
                    resolved = Path(name).resolve()
                except Exception:
                    continue
                try:
                    resolved.relative_to(base)
                    filtered.append(doc)
                except ValueError:
                    continue
            documents = filtered
        if isinstance(limit, int) and limit > 0:
            documents = documents[:limit]
        return {
            "org.ontobdc.domain.resource.document.list_by_template.content": documents,
            "org.ontobdc.domain.resource.document.list_by_template.count": len(documents),
        }

    def check(self, inputs: Dict[str, Any]) -> bool:
        repo_ok = isinstance(inputs.get("repository"), FileRepositoryPort)
        mimetypes = inputs.get("mimetypes")
        if mimetypes is None:
            return repo_ok
        if not isinstance(mimetypes, list):
            return False
        return repo_ok

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListDocumentsByTemplateCliStrategy(**kwargs)

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


class ListDocumentsByTemplateCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        self.repository: Optional[FileRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        parser.add_argument(
            "--mimetype",
            dest="mimetypes",
            action="append",
            default=None,
            help="Mimetype to filter by (can be repeated, optional)",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Maximum number of documents to list (0 = no limit)",
        )
        parser.add_argument(
            "--base-path",
            dest="base_path",
            type=str,
            default=None,
            help="Base path to restrict documents to",
        )

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        executor = CapabilityExecutor()
        inputs: Dict[str, Any] = {
            "repository": self.repository,
        }
        if args.mimetypes:
            inputs["mimetypes"] = args.mimetypes
        if args.limit:
            inputs["limit"] = args.limit
        if getattr(args, "base_path", None):
            inputs["base_path"] = args.base_path
        result = executor.execute(capability, inputs)
        self.render(console, args, capability, result)

    def render(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        fmt = getattr(args, "export", "rich")
        if fmt == "json":
            self.export_json(console, args, capability, result)
        else:
            self.export_rich(console, args, capability, result)

    def export_rich(
        self,
        console: Console,
        args: Any,
        capability: Capability,
        result: Any,
    ) -> None:
        docs = result.get("org.ontobdc.domain.resource.document.list_by_template.content", [])
        count = result.get("org.ontobdc.domain.resource.document.list_by_template.count", 0)
        table = TableViewAdapter.create_table(
            title="Documents",
            columns=[
                ("#", {"justify": "right", "style": "dim"}),
                ("Document", {"overflow": "fold"}),
            ],
        )
        for idx, doc in enumerate(docs, start=1):
            table.add_row(str(idx), str(doc))
        console.print(f"[green]Documents:[/green] {count}")
        console.print(table)

    def export_json(
        self,
        console: Console,
        args: Any,
        capability: Capability,
        result: Any,
    ) -> None:
        print(json.dumps(result, indent=2, default=str))
