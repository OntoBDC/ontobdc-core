from typing import Any

class DocumentListRenderer:
    def render(self, console: Any, result: dict, format: str = "rich"):
        files = result.get("org.ontobdc.domain.resource.document.list.content", [])
        
        if format == "json":
            import json
            print(json.dumps([str(f) for f in files], indent=4))
            return

        try:
            from rich.table import Table
        except Exception:
            for f in files:
                print(str(f))
            return

        if console is None:
            try:
                from rich.console import Console
                console = Console()
            except Exception:
                for f in files:
                    print(str(f))
                return

        table = Table(title="Documents")
        table.add_column("Path", style="cyan", no_wrap=True)
        
        for f in files:
            table.add_row(str(f))
            
        console.print(table)
