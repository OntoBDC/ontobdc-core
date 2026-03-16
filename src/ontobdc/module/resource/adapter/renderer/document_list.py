from rich.console import Console
from rich.table import Table

class DocumentListRenderer:
    def render(self, console: Console, result: dict, format: str = "rich"):
        files = result.get("org.ontobdc.domain.resource.document.list.content", [])
        
        if format == "json":
            import json
            print(json.dumps([str(f) for f in files], indent=4))
        else:
            table = Table(title="Documents")
            table.add_column("Path", style="cyan", no_wrap=True)
            
            for f in files:
                table.add_row(str(f))
                
            console.print(table)
