#!/usr/bin/env python3

import os
import sys
import argparse
from typing import Any, Dict, List, Optional, Type
import yaml
from rich.console import Console
from ontobdc.run.core.capability import Capability, CapabilityExecutor
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.ui import YELLOW, RED, print_message_box, GRAY, CYAN

# Bootstrap: Setup project root first to allow ontobdc imports
# We import directly from util (local file) because ontobdc package is not yet resolvable
try:
    from .util import setup_project_root, load_capability_packages
except ImportError:
    # Fallback: manually add current dir to path if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from util import setup_project_root, load_capability_packages

setup_project_root()

from ontobdc.run.adapter.loader import CapabilityLoader, ActionLoader
from ontobdc.run.adapter.contex import CliContextResolver
from ontobdc.run.adapter.selector import SimpleMenuSelector

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
WHITE='\033[1;37m'
RESET='\033[0m'
CONFIG_JSON="${SCRIPT_DIR}/config.json"
FULL_HLINE="----------------------------------------"

def log(level, message, *args):
    """Wrapper to call print_log.sh"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming run.py is in src/ontobdc/run/
    # print_log.sh is in src/ontobdc/cli/
    log_script = os.path.join(current_dir, "..", "cli", "print_log.sh")
    
    if os.path.exists(log_script):
        import subprocess
        cmd = ["bash", log_script, level, message] + list(args)
        subprocess.run(cmd, check=False)
    else:
        # Fallback
        print(f"[{level}] {message} {' '.join(args)}")

def get_all_capabilities() -> List[type[Capability]]:
    all_capabilities: List[type[Capability]] = []
    for pkg in load_capability_packages():
        caps = CapabilityLoader.load_from_package(pkg)
        all_capabilities.extend(caps)

    return all_capabilities


def run_capability(capability: Capability, context: CliContextPort):
    try:
        result = CapabilityExecutor.execute(capability, context)

        # Check if capability has a default renderer
        if hasattr(capability, "get_default_cli_renderer"):
            renderer = capability.get_default_cli_renderer()
            if renderer:
                # Determine format from context parameters
                export_param = context.parameters.get("export")
                fmt = export_param["value"] if export_param else "rich"

                renderer.render(Console(), result, format=fmt)
            else:
                print(result)
        else:
            print(result)

    except Exception as e:
        print_message_box(
            RED,
            "Error",
            "Execution Failed",
            str(e)
        )


def show_help():
    RAW_BOLD = "\\033[1m"
    RAW_RESET = "\\033[0m"
    RAW_CYAN = "\\033[36m"
    RAW_GRAY = "\\033[90m"
    RAW_WHITE = "\\033[37m"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming run.py is in src/ontobdc/run/
    # message_box.sh is in src/ontobdc/cli/
    msg_box_script = os.path.join(current_dir, "..", "cli", "message_box.sh")

    help_content = f"""
  {RAW_WHITE}Usage:{RAW_RESET}
    {RAW_GRAY}ontobdc run [OPTIONS]{RAW_RESET}

  {RAW_WHITE}Options:{RAW_RESET}
    {RAW_CYAN}--id <ID>{RAW_RESET}          {RAW_GRAY}Run specific capability by ID{RAW_RESET}
    {RAW_CYAN}--help, -h{RAW_RESET}         {RAW_GRAY}Show this help message{RAW_RESET}
    {RAW_CYAN}--root-path <PATH>{RAW_RESET} {RAW_GRAY}Set root path for repository{RAW_RESET}
    {RAW_CYAN}--limit <N>{RAW_RESET}        {RAW_GRAY}Limit number of results{RAW_RESET}
    {RAW_CYAN}--start <N>{RAW_RESET}        {RAW_GRAY}Start index for pagination{RAW_RESET}
    {RAW_CYAN}--file-name <PAT>{RAW_RESET}  {RAW_GRAY}Filter by file name pattern{RAW_RESET}
    {RAW_CYAN}--file-type <EXT>{RAW_RESET}  {RAW_GRAY}Filter by file type{RAW_RESET}
"""

    if os.path.exists(msg_box_script):
        import subprocess
        subprocess.run(["bash", msg_box_script, "GRAY", "OntoBDC", "Run Help", help_content], check=False)
    else:
        # Fallback to simple print if script is missing
        console = Console()
        console.print("Usage: ontobdc run [OPTIONS]", style="blue")
        print("")
        console.print("Options:", style="blue")
        print("  --id <ID>          Run specific capability by ID")
        print("  --help, -h         Show this help message")
        print("  --root-path <PATH> Set root path for repository")
        print("  --limit <N>        Limit number of results")
        print("  --start <N>        Start index for pagination")
        print("  --file-name <PAT>  Filter by file name pattern")
        print("  --file-type <EXT>  Filter by file type")
        print("")


def main():
    resolver: CliContextResolver = CliContextResolver()
    context: CliContextPort = resolver.resolve(sys.argv)

    if context.get_parameter_value("help"):
        show_help()
        sys.exit(0)

    # Check for unknown/unprocessed arguments
    if context.unprocessed_args:
        unknown_args = " ".join(context.unprocessed_args)
        print_message_box(
            YELLOW,
            "Warning",
            "Unknown Arguments",
            f"The following arguments were not recognized and will be ignored:\n\n{unknown_args}"
        )

    all_capabilities: List[type[Capability]] = get_all_capabilities()

    selected_capabilities: List[type[Capability]] = []
    for cap in all_capabilities:
        if resolver.is_satisfied_by(cap, context):
            if cap.METADATA.id not in [c.METADATA.id for c in selected_capabilities]:
                selected_capabilities.append(cap)

    if context.is_capability_targeted:
        target_id = context.parameters["capability_id"]["value"]
        
        # Check if the targeted capability exists in the full list
        target_cap = next((c for c in all_capabilities if c.METADATA.id == target_id), None)
        
        if not target_cap:
             print_message_box(
                RED,
                "Error",
                "Capability Not Found",
                f"Capability with ID {target_id} not found."
            )
             sys.exit(1)
             
        # Check if it was filtered out by satisfaction rules (optional, but good for validation)
        if target_id not in [c.METADATA.id for c in selected_capabilities]:
             pass
             
        run_capability(target_cap(), context)
        sys.exit(0)

    if not selected_capabilities:
        print_message_box(RED, "Error", f"Capability Discovery Error", "No capabilities found matching the criteria.")
        sys.exit(0)

    selector = SimpleMenuSelector()
    options = [
        {"label": f"{cap.METADATA.name} ({cap.METADATA.id})", "value": cap}
        for cap in selected_capabilities
    ]

    console = Console()

    print("")
    console.print(f"[bright_black]{FULL_HLINE}[/bright_black]")
    console.print(f"[cyan]Select Capability...[/cyan]")
    console.print(f"[bright_black]{FULL_HLINE}[/bright_black]")
    print("")
    
    RAW_CYAN = "\\033[0;36m"
    RAW_WHITE = "\\033[1;37m"
    RAW_RESET = "\\033[0m"
    RAW_GRAY = "\\033[0;90m"
    
    # Define msg_box_script path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    msg_box_script = os.path.join(current_dir, "..", "cli", "message_box.sh")
    
    # Constructing a clean list for display inside the box
    menu_content = ""
    for idx, opt in enumerate(options, 1):
        label = opt['label']

        cap = opt['value']
        name = cap.METADATA.name
        cap_id = cap.METADATA.id
        
        menu_content += f"  {RAW_CYAN}{idx}.{RAW_RESET} {RAW_WHITE}{name}{RAW_RESET} {RAW_GRAY}({cap_id}){RAW_RESET}\n"

    footer_text = f"{RAW_CYAN}0{RAW_RESET} {RAW_GRAY}Exit{RAW_RESET}"

    if os.path.exists(msg_box_script):
        import subprocess
        # We need to pass arguments carefully. 
        subprocess.run(["bash", msg_box_script, "GRAY", "OntoBDC", "Select Capability", menu_content, "", footer_text], check=False)
    else:
        # Fallback to python implementation if script not found
        print_message_box(
            GRAY,
            "OntoBDC",
            "Select Capability",
            menu_content
        )
    
    selected_cap = selector.select_option(options, title="", print_menu=False)
    
    if selected_cap:
        run_capability(selected_cap(), context)
    else:
        print("")
        log("INFO", "Exiting...")
        print("")

if __name__ == "__main__":
    main()

