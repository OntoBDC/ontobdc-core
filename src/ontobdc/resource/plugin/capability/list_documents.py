
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from rich.console import Console
from ontobdc.run.capability_core import Capability, CapabilityExecutor, CapabilityMetadata
from ontobdc.core.src.adapter.rich_table import TableViewAdapter
from ontobdc.resource.src.domain.port.repository import FileRepositoryPort


class ListDocumentsCapability(Capability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.domain.resource.capability.list_documents",
        version="0.1.0",
        name="List Repository Documents",
        description="Lists all documents from a FileRepositoryPort, including subfolders.",
        author="Elias M. P. Junior",
        tags=["resource", "document", "file", "listing"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "repository": {
                    "type": "object",
                    "required": True,
                    "description": "Repository instance (FileRepositoryPort)",
                },
                "limit": {
                    "type": "integer",
                    "required": False,
                    "description": "Maximum number of files to return (0 = no limit)",
                },
                "base_path": {
                    "type": "string",
                    "required": False,
                    "description": "Base filesystem path to restrict files to",
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

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        repo = inputs.get("repository")
        if not isinstance(repo, FileRepositoryPort):
            raise ValueError("Repository must be a FileRepositoryPort")
        limit = inputs.get("limit")
        base_path = inputs.get("base_path")
        paths: List[Path] = list(repo.iter_file_paths())
        if isinstance(base_path, str) and base_path:
            base = Path(base_path).resolve()
            filtered_paths: List[Path] = []
            for p in paths:
                try:
                    resolved = Path(p).resolve()
                except Exception:
                    continue
                try:
                    resolved.relative_to(base)
                    filtered_paths.append(p)
                except ValueError:
                    continue
            paths = filtered_paths
        if isinstance(limit, int) and limit > 0:
            paths = paths[:limit]
        files = [str(p) for p in paths]
        return {
            "org.ontobdc.domain.resource.file.list_files.files": files,
            "org.ontobdc.domain.resource.file.list_files.count": len(files),
        }

    def check(self, inputs: Dict[str, Any]) -> bool:
        return isinstance(inputs.get("repository"), FileRepositoryPort)

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return ListFilesCliStrategy(**kwargs)


class ListFilesCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        self.repository: Optional[FileRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=0,
            help="Maximum number of files to list (0 = no limit)",
        )
        parser.add_argument(
            "--base-path",
            dest="base_path",
            type=str,
            default=None,
            help="Base path to restrict files to",
        )

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        executor = CapabilityExecutor()
        inputs: Dict[str, Any] = {}
        inputs["repository"] = self.repository
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
        files = result.get("org.ontobdc.domain.resource.file.list_files.files", [])
        count = result.get("org.ontobdc.domain.resource.file.list_files.count", 0)
        table = TableViewAdapter.create_table(
            title="Files",
            columns=[
                TableViewAdapter.col("#", kind="index"),
                TableViewAdapter.col("Path", kind="primary", overflow="fold"),
            ],
        )
        for idx, path in enumerate(files, start=1):
            table.add_row(str(idx), str(path))
        console.print(f"[green]Files:[/green] {count}")
        console.print(table)

    def export_json(
        self,
        console: Console,
        args: Any,
        capability: Capability,
        result: Any,
    ) -> None:
        print(json.dumps(result, indent=2, default=str))


def iter_file_paths(repository: FileRepositoryPort) -> Iterable[Path]:
    return repository.iter_file_paths()


def list_file_paths(repository: FileRepositoryPort) -> List[Path]:
    return list(iter_file_paths(repository))
