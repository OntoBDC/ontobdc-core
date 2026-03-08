import json
from rich.console import Console
from typing import Any, Dict
from ontobdc.core.adapter import TableViewAdapter

class FileListRenderer:
    def render(self, console: Console, result: Dict[str, Any], format: str = "rich") -> None:
        if format == "json":
            self.export_json(console, result)
        else:
            self.export_rich(console, result)

    def export_rich(self, console: Console, result: Dict[str, Any]) -> None:
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

    def export_json(self, console: Console, result: Dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, default=str))
