
import json
from pathlib import Path
from rich.console import Console
from typing import Any, Dict, Iterable, List, Optional
from ontobdc.core.adapter import TableViewAdapter
from ontobdc.module.resource.domain.port.repository import FileRepositoryPort
from ontobdc.run.core.capability import Capability, CapabilityExecutor, CapabilityMetadata


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
            "--start",
            dest="start",
            type=int,
            default=0,
            help="Starting index for pagination (0 = first)",
        )
        parser.add_argument(
            "--type",
            "--file-type",
            dest="type",
            nargs="+",
            default=None,
            help="Filter by file type(s)",
        )
        parser.add_argument(
            "--file-name",
            dest="file_name",
            type=str,
            default=None,
            help="Filter by file name pattern (glob or regex:)",
        )
        parser.add_argument(
            "--base-path",
            dest="base_path",
            type=str,
            default=None,
            help="Base path to restrict listing to",
        )

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        executor = CapabilityExecutor()
        inputs: Dict[str, Any] = {}
        # Populate repository using the key defined in the capability schema
        inputs["org.ontobdc.domain.resource.document.repository.incoming"] = self.repository
        # Fallback for older capabilities
        inputs["repository"] = self.repository
        
        if args.limit:
            inputs["limit"] = args.limit
        if getattr(args, "start", 0):
            inputs["start"] = args.start
        if getattr(args, "base_path", None):
            inputs["base_path"] = args.base_path
        if getattr(args, "type", None):
            inputs["types"] = args.type
            inputs["file-type"] = args.type
        if getattr(args, "file_name", None):
            inputs["name_pattern"] = args.file_name
            inputs["file-name"] = args.file_name
            
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
        # Check for generic list keys
        files = result.get("org.ontobdc.domain.resource.document.list.content")
        count = result.get("org.ontobdc.domain.resource.document.list.count")
        
        # Check for typed list keys if generic not found
        if files is None:
            files = result.get("org.ontobdc.domain.resource.document.list_by_type.content", [])
            count = result.get("org.ontobdc.domain.resource.document.list_by_type.count", 0)
            
        table = TableViewAdapter.create_table(
            title="Documents",
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