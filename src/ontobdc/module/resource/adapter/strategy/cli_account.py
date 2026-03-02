import json
from typing import Any, Dict, Optional
from rich.console import Console
from rich.table import Table
from ontobdc.run.core.capability import Capability
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort

class ListAccountsCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        self.repository: Optional[DocumentRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        # Allow overriding the repository root via CLI argument if needed
        # Though usually repository is injected, run.py might handle --repository global arg
        # But if it's passed to capability args, we need to accept it here or in run.py
        # Based on error, run.py passes unknown args to capability parser.
        parser.add_argument(
            "--repository",
            dest="repository_path",
            required=False,
            help="Override repository root path",
        )

    def run(self, console: Console, args: Any, capability: Capability) -> None:
        inputs: Dict[str, Any] = {
            "repository": self.repository,
        }

        # Execute
        try:
            result = capability.execute(inputs)
            self.render(console, result, getattr(args, "export", "rich"))
        except Exception as e:
            console.print(f"[red]Execution Error:[/red] {e}")

    def render(self, console: Console, result: Any, export_format: str = "rich") -> None:
        if export_format == "json":
            print(json.dumps(result, indent=2, default=str))
            return

        accounts = result.get("org.ontobdc.domain.social.account.list.content", [])
        count = result.get("org.ontobdc.domain.social.account.list.count", 0)

        if not accounts:
            console.print("[yellow]No WhatsApp accounts found.[/yellow]")
            return

        table = Table(title=f"WhatsApp Accounts Found ({count})")
        table.add_column("Account Identifier", style="cyan")
        table.add_column("Name(s)", style="green")
        table.add_column("Source", style="magenta")

        for account in accounts:
            if isinstance(account, dict):
                account_id = str(account.get("id", "Unknown"))
                names = ", ".join(account.get("names", []))
                source = str(account.get("source", "Unknown")).replace(".__ontobdc__/ro-crate-metadata.json", "{ro-crate}")
                table.add_row(account_id, names, source)
            else:
                table.add_row(str(account), "", "")

        console.print(table)
