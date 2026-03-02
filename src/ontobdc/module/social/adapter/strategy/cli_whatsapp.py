from typing import Any, Dict, Optional
from rich.console import Console
from ontobdc.run.core.action import Action
from ontobdc.module.resource.domain.port.repository import DocumentRepositoryPort

class ExtractWhatsappCliStrategy:
    def __init__(self, **kwargs: Any) -> None:
        self.repository: Optional[DocumentRepositoryPort] = kwargs.get("repository")

    def setup_parser(self, parser) -> None:
        parser.add_argument(
            "--whatsapp-account",
            dest="whatsapp_account",
            required=False,
            help="The name of the WhatsApp account (to identify sent messages vs received).",
        )

    def run(self, console: Console, args: Any, action: Action) -> None:
        inputs: Dict[str, Any] = {
            "repository": self.repository,
            "whatsapp-account": args.whatsapp_account,
        }

        # 1. Validation using METADATA schema
        if not self._validate_inputs(console, action, inputs):
            return

        # 2. Execute
        try:
            result = action.execute(inputs)
            self.render(console, result)
        except Exception as e:
            console.print(f"[red]Execution Error:[/red] {e}")

    def _validate_inputs(self, console: Console, action: Action, inputs: Dict[str, Any]) -> bool:
        schema = action.metadata.input_schema
        if not schema or "properties" not in schema:
            return True

        is_valid = True
        for key, prop in schema["properties"].items():
            # Skip if input is missing (handled by required=True in argparse or logic check)
            # But if we want to support optional args that have validation, we check if key in inputs
            if key not in inputs:
                if prop.get("required", False):
                     console.print(f"[red]Validation Error:[/red] Missing required input: {key}")
                     is_valid = False
                continue

            value = inputs[key]
            checks = prop.get("check", [])
            
            for check_item in checks:
                try:
                    if isinstance(check_item, type):
                        validator = check_item()
                    else:
                        validator = check_item

                    if not validator.verify(key, value, inputs):
                        console.print(f"[red]Validation Error:[/red] Invalid value for '{key}': {value}")
                        is_valid = False
                except Exception as e:
                    console.print(f"[red]Validation Exception:[/red] Error validating '{key}': {e}")
                    is_valid = False
        
        return is_valid

    def render(self, console: Console, result: Any) -> None:
        # Simple render for now
        interactions = result.get("org.ontobdc.domain.social.interaction.list.content", [])
        count = result.get("org.ontobdc.domain.social.interaction.list.count", 0)

        console.print(f"[bold green]Found {count} unanswered interactions[/bold green]")
        for item in interactions:
            console.print(f"- {item}")
