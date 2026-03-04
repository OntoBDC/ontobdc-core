from typing import Any, Dict
from rich.console import Console
from rich.table import Table
from rich import box


def print_table(data: Dict[str, Any]):
    """
    Print a table using rich based on the provided data dictionary.
    
    Expected data structure:
    {
        "title": "Table Title",
        "headers": {
            "ID": {"style": "cyan", "no_wrap": False, "overflow": "fold"},
            "Name": {"style": "green"},
            ...
        },
        "values": {
            "capabilities": [...],
            "actions": [...]
        }
    }
    """
    console = Console()
    
    title = data.get("title", "Available Capabilities")
    headers = data.get("headers", {})
    values = data.get("values", {})
    
    capabilities = values.get("capabilities", [])
    actions = values.get("actions", [])
    
    # Function to format ID: 3 segments on first line, rest on next line
    def format_id(id_str):
        parts = id_str.split('.')
        if len(parts) > 3:
            return ".".join(parts[:3]) + ".\n" + ".".join(parts[3:])
        return id_str

    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    
    # Add columns dynamically based on headers config
    # Fallback to default columns if headers not provided or empty?
    # For now, we assume the structure matches what run.py sends.
    if headers:
        for name, style_config in headers.items():
            table.add_column(
                name, 
                style=style_config.get("style", "dim"),
                no_wrap=style_config.get("no_wrap", False),
                overflow=style_config.get("overflow", "ellipsis")
            )
    else:
        # Fallback defaults
        table.add_column("ID", style="cyan", no_wrap=False, overflow="fold")
        table.add_column("Name", style="green")
        table.add_column("Description", style="dim")
        table.add_column("Inputs", style="dim")

    # Helper to process items (capabilities or actions)
    def process_items(items, is_action=False):
        for item in items:
            # Check if it's a class or instance
            if isinstance(item, type):
                try:
                    # Instantiate to get metadata property
                    instance = item()
                    meta = instance.metadata
                except Exception:
                    continue
            else:
                instance = item
                meta = instance.metadata

            if not meta:
                continue

            cid = meta.id
            # Actions usually get yellow styling for name in default impl
            name_style = "[yellow]{}[/yellow]" if is_action else "{}"
            name = name_style.format(getattr(meta, "name", ""))
            desc = getattr(meta, "description", "")

            # Extract inputs/args from metadata if available
            inputs_list = []
            inputs_meta = getattr(meta, "input_schema", {}).get("properties", {})
            if inputs_meta:
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
                    
                    inputs_list.append(f"{k} [dim]({type_str})[/dim]{req_mark}")

            inputs_str = "\n".join(inputs_list) if inputs_list else "-"
            table.add_row(format_id(cid), name, desc, inputs_str)

    # Process capabilities
    process_items(capabilities, is_action=False)
    
    # Process actions
    process_items(actions, is_action=True)

    console.print("\n")
    console.print(table)
