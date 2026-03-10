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

# Setup path
try:
    from ontobdc.run.util import setup_project_root, load_capability_packages
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from ontobdc.run.util import setup_project_root, load_capability_packages

setup_project_root()

from ontobdc.run.adapter.loader import CapabilityLoader, ActionLoader
from ontobdc.run.ui import print_message_box, RED, YELLOW, GREEN, CYAN, GRAY, WHITE

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
        packages = load_capability_packages()
        # packages = list(set(packages)) # Packages might be unhashable? No, strings usually.
        
        capabilities = []
        actions = []
        
        for pkg in packages:
            try:
                caps = CapabilityLoader.load_from_package(pkg)
                # acts = ActionLoader.load_from_package(pkg) # ActionLoader might not be fully impl or needed for list yet?
                # The original code loaded actions too.
                acts = []
                try:
                    acts = ActionLoader.load_from_package(pkg)
                except Exception:
                    pass
                
                for cap_cls in caps:
                    # Convert metadata to dict
                    if hasattr(cap_cls, "METADATA") and cap_cls.METADATA:
                        meta = cap_cls.METADATA
                        
                        # Handle input_schema types serialization (classes to strings)
                        input_schema = {}
                        if meta.input_schema:
                            input_schema = meta.input_schema.copy()
                            if "properties" in input_schema:
                                for prop_key, prop_val in input_schema["properties"].items():
                                    if "type" in prop_val and isinstance(prop_val["type"], type):
                                        prop_val["type"] = str(prop_val["type"])
                                    if "check" in prop_val and isinstance(prop_val["check"], list):
                                        prop_val["check"] = [str(c) for c in prop_val["check"]]

                        cap_dict = {
                            "id": meta.id,
                            "version": meta.version,
                            "name": meta.name,
                            "description": meta.description,
                            "author": meta.author,
                            "tags": meta.tags if isinstance(meta.tags, (list, tuple)) else [],
                            "supported_languages": meta.supported_languages,
                            "input_schema": input_schema,
                            "output_schema": meta.output_schema,
                            "raises": meta.raises,
                            "type": "capability"
                        }
                        capabilities.append(cap_dict)
                        
                for act_cls in acts:
                    if hasattr(act_cls, "METADATA") and act_cls.METADATA:
                        meta = act_cls.METADATA
                        act_dict = {
                            "id": meta.id,
                            "version": meta.version,
                            "name": meta.name,
                            "description": meta.description,
                            "author": meta.author,
                            "tags": meta.tags if isinstance(meta.tags, (list, tuple)) else [],
                            "type": "action"
                        }
                        actions.append(act_dict)
                        
            except Exception as e:
                # log("WARN", f"Error loading package {pkg}: {e}")
                pass

        # Deduplicate by ID
        unique_caps = {c['id']: c for c in capabilities}.values()
        unique_acts = {a['id']: a for a in actions}.values()
        
        all_items = list(unique_caps) + list(unique_acts)
        
        if args.json:
            print(json.dumps(all_items, indent=2))
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

            # Print Action Table (keeping table for actions as they are usually simpler)
            if unique_acts:
                table = Table(title="Actions", show_header=True, header_style="bold cyan", expand=True)
                table.add_column("ID", style="dim")
                table.add_column("Name", style="white")
                table.add_column("Version", style="green")
                table.add_column("Description", style="white")

                for item in unique_acts:
                    table.add_row(
                        item['id'],
                        item['name'],
                        item.get('version', '0.0.0'),
                        item.get('description', '').split('\n')[0]
                    )
                console.print(table)
                console.print("")
                
            if not unique_caps and not unique_acts:
                print_message_box(YELLOW, "Warning", "No Items Found", "No capabilities or actions were discovered.")

    except Exception as e:
        print_message_box(RED, "Error", "Listing Failed", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
