#!/usr/bin/env python3

import os
import sys
import argparse
from typing import Any, Dict, List, Optional, Type
import yaml
from rich.console import Console
from ontobdc.run.core.capability import Capability, CapabilityExecutor
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.ui import YELLOW, RED, print_message_box

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
             # It exists but parameters are missing.
             # We should probably run it anyway and let it fail or prompt?
             # For now, let's just warn but proceed with the targeted capability.
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
    
    selected_cap = selector.select_option(options, title="Select Capability:")
    
    if selected_cap:
        run_capability(selected_cap(), context)
    else:
        print("")
        print("Exiting...")
        print("")

if __name__ == "__main__":
    main()

