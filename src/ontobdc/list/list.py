#!/usr/bin/env python3

import sys
import json
import argparse
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.box import ROUNDED


from ontobdc.run.ui import print_message_box, RED, YELLOW, GREEN, CYAN, GRAY, WHITE
from ontobdc.shared.adapter.plugin import CapabilityLoader

def log(level, message, *args):
    """Wrapper to call print_log.sh"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # list.py is in src/ontobdc/list/
    # print_log.sh is in src/ontobdc/cli/
    log_script = os.path.join(current_dir, "..", "cli", "print_log.sh")
    
    if os.path.exists(log_script):
        import subprocess
        cmd = ["bash", log_script, level, message] + list(args)
        subprocess.run(cmd, check=False)
    else:
        # Fallback
        print(f"[{level}] {message} {' '.join(args)}")

def show_help():
    RAW_BOLD = "\\033[1m"
    RAW_RESET = "\\033[0m"
    RAW_CYAN = "\\033[36m"
    RAW_GRAY = "\\033[90m"
    RAW_WHITE = "\\033[37m"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    # message_box.sh is in src/ontobdc/cli/
    msg_box_script = os.path.join(current_dir, "..", "cli", "message_box.sh")

    help_content = f"""
  {RAW_WHITE}Usage:{RAW_RESET}
    {RAW_GRAY}ontobdc list [OPTIONS]{RAW_RESET}

  {RAW_WHITE}Options:{RAW_RESET}
    {RAW_CYAN}--json{RAW_RESET}          {RAW_GRAY}Output in JSON format{RAW_RESET}
    {RAW_CYAN}--help, -h{RAW_RESET}      {RAW_GRAY}Show this help message{RAW_RESET}
"""

    if os.path.exists(msg_box_script):
        import subprocess
        subprocess.run(["bash", msg_box_script, "GRAY", "OntoBDC", "List Help", help_content], check=False)
    else:
        print("Usage: ontobdc list [--json]")

def main():
    # Handle help manually to use our custom message box
    if "--help" in sys.argv or "-h" in sys.argv:
        show_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="List OntoBDC capabilities", add_help=False)
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args, unknown = parser.parse_known_args()

    if unknown:
        unknown_args_str = " ".join(unknown)
        print_message_box(
            YELLOW,
            "Warning",
            "Unknown Arguments",
            f"The following arguments were not recognized and will be ignored:\n\n{unknown_args_str}"
        )

    try:
        capabilities = []

        for cap_cls in CapabilityLoader().get_all("capability"):
            if hasattr(cap_cls, "METADATA") and cap_cls.METADATA:
                meta = cap_cls.METADATA
                input_schema = {}
                if meta.input_schema:
                    input_schema = meta.input_schema.copy()
                    if "properties" in input_schema:
                        for prop_key, prop_val in input_schema["properties"].items():
                            if "type" in prop_val and isinstance(prop_val["type"], type):
                                prop_val["type"] = str(prop_val["type"])
                            if "check" in prop_val and isinstance(prop_val["check"], list):
                                prop_val["check"] = [str(c) for c in prop_val["check"]]

                cap_instance = cap_cls()
                cap_dict = {
                    "id": meta.id,
                    "name": meta.name,
                    "description": meta.description,
                    "author": meta.author,
                    "tags": cap_instance.tags() if hasattr(cap_instance, "tags") else (meta.tags if isinstance(meta.tags, (list, tuple)) else []),
                    "supported_languages": meta.supported_languages,
                    "input_schema": input_schema,
                    "output_schema": meta.output_schema,
                    "raises": meta.raises,
                    "type": "capability"
                }
                capabilities.append(cap_dict)

        unique_caps = {c['id']: c for c in capabilities}.values()
        
        if args.json:
            print(json.dumps(list(unique_caps), indent=2))
        else:
            # Rich output
            console = Console()
            
            # Print Capability Cards
            if unique_caps:
                console.print(f"\n[bold cyan]Capabilities[/bold cyan]\n")
                for item in unique_caps:
                    content = Text()
                    
                    # ID and Version
                    content.append(f"ID: ", style="bold cyan")
                    content.append(f"{item['id']}\n", style="dim")
                    content.append(f"Version: ", style="bold cyan")
                    content.append(f"{item.get('version', '0.0.0')}\n\n", style="green")
                    
                    # Description
                    if item.get('description'):
                        content.append(f"Description:\n", style="bold cyan")
                        content.append(f"{item['description']}\n\n", style="white")
                    
                    # Inputs
                    if item.get('input_schema') and item['input_schema'].get('properties'):
                        content.append(f"Inputs:\n", style="bold cyan")
                        for prop, details in item['input_schema']['properties'].items():
                            req = "*" if details.get('required') else ""
                            content.append(f"  • {prop}{req} ", style="blue")
                            content.append(f"({details.get('type', 'any')})", style="dim")
                            if details.get('description'):
                                content.append(f": {details['description']}", style="white")
                            content.append("\n")
                        content.append("\n")
                    
                    # Outputs
                    if item.get('output_schema'):
                        content.append(f"Outputs:\n", style="bold cyan")
                        # output_schema might be a simple type string or a dict
                        out = item['output_schema']
                        if isinstance(out, dict):
                            # If it has properties (like input_schema)
                            if 'properties' in out:
                                for prop, details in out['properties'].items():
                                    content.append(f"  • {prop} ", style="blue")
                                    content.append(f"({details.get('type', 'any')})\n", style="dim")
                            else:
                                content.append(f"  {json.dumps(out)}\n", style="white")
                        else:
                            content.append(f"  {out}\n", style="white")
                    
                    panel = Panel(
                        content,
                        title=f"[bold white]{item['name']}[/bold white]",
                        title_align="left",
                        border_style="bright_black",
                        box=ROUNDED,
                        padding=(1, 2)
                    )
                    console.print(panel)
                console.print("")

            if not unique_caps:
                print_message_box(YELLOW, "Warning", "No Items Found", "No capabilities were discovered.")

    except Exception as e:
        print_message_box(RED, "Error", "Listing Failed", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
