
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console
from ontobdc.run.capability_core import Capability, CapabilityExecutor, CapabilityMetadata
from ontobdc.core.src.adapter.rich_table import TableViewAdapter
from ontobdc.resource.src.domain.port.repository import FileRepositoryPort


class ListDocumentsByTypeCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        self.repository: Optional[FileRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        parser.add_argument(
            "type",
            nargs="+",
            help="One or more document types to filter",
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
            "types": args.type,
        }
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

    def export_rich(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        docs = result.get("org.ontobdc.domain.resource.document.list_by_type.content", [])
        count = result.get("org.ontobdc.domain.resource.document.list_by_type.count", 0)
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

    def export_json(self, console: Console, args: Any, capability: Capability, result: Any) -> None:
        print(json.dumps(result, indent=2, default=str))


class ListDocumentsByTypeCapability(Capability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents_by_type",
        version="0.1.0",
        name="List Documents by Type",
        description="Lists documents from a FileRepositoryPort filtered by type.",
        author="Elias M. P. Junior",
        tags=["resource", "document", "file", "listing", "type"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "object",
                    "required": True,
                    "description": "Repository instance (FileRepositoryPort)",
                },
                "types": {
                    "type": "array",
                    "required": True,
                    "description": "List of document types to filter by",
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
                "org.ontobdc.domain.resource.document.list_by_type.content": {
                    "type": "array",
                    "description": "List of documents",
                },
                "org.ontobdc.domain.resource.document.list_by_type.count": {
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

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repo = inputs.get("repository")
        if not isinstance(repo, FileRepositoryPort):
            raise ValueError("Repository must be a FileRepositoryPort")
        types = inputs.get("types")
        if not isinstance(types, list) or not types:
            raise ValueError("Types must be a non-empty list of strings")
        limit = inputs.get("limit")

        documents: List[Any] = []
        for t in types:
            if not isinstance(t, str):
                raise ValueError("Each type must be a string")
            docs = repo.get_by_type(t)
            if isinstance(docs, list):
                documents.extend(docs)

        base_path = inputs.get("base_path")
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
            "org.ontobdc.domain.resource.document.list_by_type.content": documents,
            "org.ontobdc.domain.resource.document.list_by_type.count": len(documents),
        }

    def check(self, inputs: Dict[str, Any]) -> bool:
        repo_ok = isinstance(inputs.get("repository"), FileRepositoryPort)
        types = inputs.get("types")
        return repo_ok and isinstance(types, list) and bool(types)

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListDocumentsByTypeCliStrategy(**kwargs)

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
