from rich.console import Console
from rich.table import Table

class DocumentListRenderer:
    def render(self, result: dict, format: str = "text"):
        console = Console()
        files = result.get("org.ontobdc.domain.resource.document.list.content", [])
        
        if format == "json":
            import json
            console.print(json.dumps(files, indent=4))
        else:
            table = Table(title="Documents")
            table.add_column("Path", style="cyan", no_wrap=True)
            
            for f in files:
                table.add_row(str(f))
                
            console.print(table)
