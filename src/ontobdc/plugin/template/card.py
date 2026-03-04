from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

def print_cards(data: Dict[str, Any]):
    """
    Print capabilities and actions as a list of full-width cards (Rich Panels).
    
    Expected data structure matches print_table:
    {
        "title": "Available Capabilities",
        "values": {
            "capabilities": [...],
            "actions": [...]
        }
    }
    """
    console = Console()
    title = data.get("title", "Available Capabilities")
    values = data.get("values", {})
    
    capabilities = values.get("capabilities", [])
    actions = values.get("actions", [])

    def process_items(items, is_action=False) -> List[Panel]:
        panels = []
        for item in items:
            # Handle class vs instance
            if isinstance(item, type):
                try:
                    instance = item()
                    meta = instance.metadata
                except Exception:
                    continue
            else:
                instance = item
                meta = instance.metadata

            if not meta:
                continue

            # Extract info
            cid = meta.id
            name = getattr(meta, "name", "Unknown")
            desc = getattr(meta, "description", "")
            
            # Formatting
            header_style = "bold yellow" if is_action else "bold green"
            title_text = Text(name, style=header_style)
            
            content = Text()
            content.append(f"ID: ", style="dim")
            content.append(f"{cid}\n", style="cyan")
            
            if desc:
                content.append(f"\n{desc}\n", style="white")
            
            # Inputs
            inputs_meta = getattr(meta, "input_schema", {}).get("properties", {})
            if inputs_meta:
                content.append("\nInputs:", style="bold dim")
                for k, v in inputs_meta.items():
                    if "repository" in k.lower():
                        continue
                    
                    required = v.get("required", False)
                    req_mark = "*" if required else ""
                    
                    prop_type = v.get("type", "any")
                    if isinstance(prop_type, type):
                        type_str = prop_type.__name__
                    else:
                        type_str = str(prop_type)
                    
                    content.append(f"\n • {k}", style="white")
                    content.append(f" ({type_str}){req_mark}", style="cyan")

            # Create Panel
            # Full width (expand=True is default for Panel if width not set, but explicit is good)
            # Border style white for all
            panel = Panel(
                content,
                title=title_text,
                title_align="left",
                border_style="white",
                box=box.ROUNDED,
                padding=(1, 2),
                expand=True
            )
            panels.append(panel)
        return panels

    # Generate Panels
    cap_panels = process_items(capabilities, is_action=False)
    act_panels = process_items(actions, is_action=True)
    
    all_panels = cap_panels + act_panels

    if all_panels:
        console.print(f"\n[bold underline]{title}[/bold underline]\n")
        # Print each panel individually to stack them vertically with full width
        for panel in all_panels:
            console.print(panel)
            console.print("") # Add spacing between cards
    else:
        console.print("[yellow]No capabilities found.[/yellow]")
