#!/usr/bin/env python3
import os
import sys
import argparse
from rich.console import Console

# Bootstrap: Setup project root first to allow ontobdc imports
# We import directly from util (local file) because ontobdc package is not yet resolvable
try:
    from .util import setup_project_root
except ImportError:
    # Fallback: manually add current dir to path if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from util import setup_project_root

setup_project_root()

from ontobdc.run.ui import print_message_box, RED
from ontobdc.run.core.action import ActionRegistry
from ontobdc.run.core.selector import SimpleMenuSelector
from ontobdc.run.core.capability import CapabilityRegistry
from ontobdc.run.core.loader import CapabilityLoader, ActionLoader
from ontobdc.module.resource.adapter.repository import SimpleFileRepository

try:
    # Scan for capabilities in the 'ontobdc' package recursively
    # We focus on 'ontobdc.module' where plugins usually reside
    capabilities = CapabilityLoader.load_from_package("ontobdc.module")
    actions = ActionLoader.load_from_package("ontobdc.module")

except Exception as e:
    print_message_box(RED, "Error", "Loading Error", str(e))
    sys.exit(1)

CapabilityRegistry.register_many(capabilities)
ActionRegistry.register_many(actions)


def main():
    root_path = os.getcwd()
    
    # Manual scan for --root-path or --repository (alias) before argparse
    if "--root-path" in sys.argv:
        try:
            root_path = sys.argv[sys.argv.index("--root-path") + 1]
        except IndexError:
            pass # Use cwd
    elif "--repository" in sys.argv:
         try:
            root_path = sys.argv[sys.argv.index("--repository") + 1]
         except IndexError:
            pass
    
    # If no explicit path is provided, try to find a repository root by walking up
    # or checking for a known marker (e.g., .__ontobdc__)
    # For now, let's just ensure we are using absolute path
    root_path = os.path.abspath(root_path)

    # Repository resolution heuristic
    if not os.path.isdir(os.path.join(root_path, ".__ontobdc__")):
        # 1. Check if 'projects' subdirectory has .__ontobdc__
        projects_path = os.path.join(root_path, "projects")
        if os.path.isdir(projects_path) and os.path.isdir(os.path.join(projects_path, ".__ontobdc__")):
            root_path = projects_path
        else:
            # 2. Walk up to find .__ontobdc__
            current = root_path
            while current != "/":
                if os.path.isdir(os.path.join(current, ".__ontobdc__")):
                    root_path = current
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent

    simple_repo = SimpleFileRepository(root_path)

    capabilities_attrs = {
        "org.ontobdc.domain.resource.document.repository.incoming": simple_repo,
        "repository": simple_repo,
    }

    # Parse CLI arguments to add to capabilities attributes
    cleaned_argv = []
    extra_args = []
    i = 1
    include_actions = False

    # Debug print to diagnose argument parsing issues
    # print(f"DEBUG: sys.argv={sys.argv}")
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        # Standard arguments handling
        if arg == "--root-path":
            # root-path is manually handled, exclude from cleaned_argv
            if i + 1 < len(sys.argv):
                i += 2
            else:
                i += 1
            continue
            
        if arg == "--repository":
            # Ignore duplicate repository argument if user provides it by mistake (since it's internal)
            # But wait, maybe we should treat --repository as alias for --root-path?
            # Let's stick to --root-path as the canonical one for now.
             if i + 1 < len(sys.argv):
                i += 2
             else:
                i += 1
             continue

        if arg == "--act":
            include_actions = True
            i += 1
            continue

        if arg == "--export":
            # Standard arg for parser. Keep it.
            cleaned_argv.append(arg)
            if i + 1 < len(sys.argv) and not sys.argv[i+1].startswith("-"):
                 cleaned_argv.append(sys.argv[i+1])
                 i += 2
            else:
                 i += 1
            continue

        if arg == "--act":
            include_actions = True
            i += 1
            continue

        if arg in ["-h", "--help", "--json"]:
            cleaned_argv.append(arg)
            i += 1
            continue
            
        # Parse --key value or --key=value
        if arg.startswith("--"):
            key = arg[2:]
            val = True 
            
            if "=" in key:
                key, val = key.split("=", 1)
                capabilities_attrs[key] = val
                extra_args.append(arg)
                i += 1
            elif i + 1 < len(sys.argv) and not sys.argv[i+1].startswith("-"):
                val = sys.argv[i+1]
                capabilities_attrs[key] = val
                extra_args.append(arg)
                extra_args.append(sys.argv[i+1])
                i += 2 
            else:
                capabilities_attrs[key] = val
                extra_args.append(arg)
                i += 1 
            continue
            
        # If not standard arg and not attribute (e.g. positional capability_id), keep it
        cleaned_argv.append(arg)
        i += 1

    if "--json" in sys.argv:
        import json

        catalog = []
        for cid, cls in CapabilityRegistry.get_by_attr(capabilities_attrs).items():
            meta = cls.METADATA
            meta_dict = meta.__dict__.copy()
            meta_dict['type'] = 'capability'
            catalog.append(meta_dict)
        
        if include_actions:
            for aid, cls in ActionRegistry.get_by_attr(capabilities_attrs).items():
                meta = cls.METADATA
                meta_dict = meta.__dict__.copy()
                meta_dict['type'] = 'action'
                catalog.append(meta_dict)

        print(json.dumps(catalog, indent=2, default=str))
        sys.exit(0)

    if "-h" in sys.argv or "--help" in sys.argv:
        from rich.table import Table
        from rich import box

        console = Console()
        
        # Function to format ID: 3 segments on first line, rest on next line
        def format_id(id_str):
            parts = id_str.split('.')
            if len(parts) > 3:
                return ".".join(parts[:3]) + ".\n" + ".".join(parts[3:])
            return id_str

        table = Table(title="Available Capabilities", box=box.ROUNDED, show_lines=True)
        # Use overflow="fold" to ensure wrapping instead of truncation, though we handle split manually
        table.add_column("ID", style="cyan", no_wrap=False, overflow="fold")
        table.add_column("Name", style="green")
        table.add_column("Description", style="dim")
        table.add_column("Inputs", style="dim")

        caps = CapabilityRegistry.get_all()
        for cid, cls in caps.items():
            meta = getattr(cls, "METADATA", None)
            # if not meta:
            #     continue

            name = getattr(meta, "name", "")
            desc = getattr(meta, "description", "")

            # Extract inputs/args from metadata if available
            inputs_list = []
            inputs_meta = getattr(meta, "input_schema", {}).get("properties", {})
            if inputs_meta:
                for k, v in inputs_meta.items():
                    # Skip internal/implicit inputs if they are Repository ports
                    # But wait, we might want to show required args.
                    # Usually CLI args map to these properties.
                    
                    # Filter out repository injection if desired, or keep all.
                    # For CLI help, we usually care about what the user can pass as --arg.
                    
                    # Check if it's a repository port (heuristic: contains 'repository')
                    if "repository" in k.lower():
                        continue
                        
                    required = v.get("required", False)
                    # Use a compact required indicator (e.g., '•' or '*' or just bold/color)
                    req_mark = "*" if required else ""
                    
                    # Extract type info
                    prop_type = v.get("type", "any")
                    if isinstance(prop_type, type):
                        type_str = prop_type.__name__
                    else:
                        type_str = str(prop_type)
                    
                    # Format: name* (type)
                    # inputs_list.append(f"{k}{req_mark} ({type_str})")
                    
                    # Or better visual style:
                    # name (type)*
                    inputs_list.append(f"{k} [dim]({type_str})[/dim]{req_mark}")

            inputs_str = "\n".join(inputs_list) if inputs_list else "-"
            table.add_row(format_id(cid), name, desc, inputs_str)

        actions = ActionRegistry.get_all()
        for aid, cls in actions.items():
            meta = getattr(cls, "METADATA", None)
            if not meta:
                continue
            
            name = f"[yellow]{getattr(meta, 'name', '')}[/yellow]"
            desc = getattr(meta, "description", "")
            
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

            table.add_row(format_id(aid), name, desc, inputs_str)

        console.print("\n")
        console.print(table)
            
        sys.exit(0)
        

    outer_parser = argparse.ArgumentParser(add_help=False)
    outer_parser.add_argument(
        "--export",
        choices=["rich", "json"],
        help="Output format",
        default=None,
    )
    outer_parser.add_argument("capability_id", nargs="?", help="ID of the capability or action to run")

    parsed_args, remaining_args = outer_parser.parse_known_args(cleaned_argv)
    
    # Check if help was requested globally (no capability_id provided)
    if ("-h" in sys.argv or "--help" in sys.argv) and not parsed_args.capability_id:
        from rich.table import Table
        from rich import box

        console = Console()
        
        # Function to format ID: 3 segments on first line, rest on next line
        def format_id(id_str):
            parts = id_str.split('.')
            if len(parts) > 3:
                return ".".join(parts[:3]) + ".\n" + ".".join(parts[3:])
            return id_str

        table = Table(title="Available Capabilities", box=box.ROUNDED, show_lines=True)
        # Use overflow="fold" to ensure wrapping instead of truncation, though we handle split manually
        table.add_column("ID", style="cyan", no_wrap=False, overflow="fold")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_column("Inputs", style="yellow")

        caps = CapabilityRegistry.get_by_attr(capabilities_attrs)
        for cid, cls in caps.items():
            meta = getattr(cls, "METADATA", None)
            if not meta:
                continue
            
            name = getattr(meta, "name", "")
            desc = getattr(meta, "description", "")
            
            # Extract inputs/args from metadata if available
            inputs_list = []
            inputs_meta = getattr(meta, "inputs", {})
            if inputs_meta:
                for k, v in inputs_meta.items():
                    input_desc = v.get("description", "")
                    required = v.get("required", False)
                    req_mark = "*" if required else ""
                    inputs_list.append(f"{k}{req_mark}")
            
            inputs_str = ", ".join(inputs_list) if inputs_list else "-"
            
            table.add_row(format_id(cid), name, desc, inputs_str)
        
        console.print(table)

        if include_actions:
            act_table = Table(title="Available Actions", box=box.ROUNDED, show_lines=True)
            act_table.add_column("ID", style="cyan", no_wrap=False, overflow="fold")
            act_table.add_column("Name", style="green")
            act_table.add_column("Description", style="white")
            act_table.add_column("Inputs", style="yellow")

            actions = ActionRegistry.get_by_attr(capabilities_attrs)
            for aid, cls in actions.items():
                meta = getattr(cls, "METADATA", None)
                if not meta:
                    continue
                
                name = getattr(meta, "name", "")
                desc = getattr(meta, "description", "")
                
                inputs_list = []
                inputs_meta = getattr(meta, "inputs", {})
                if inputs_meta:
                    for k, v in inputs_meta.items():
                         input_desc = v.get("description", "")
                         required = v.get("required", False)
                         req_mark = "*" if required else ""
                         inputs_list.append(f"{k}{req_mark}")

                inputs_str = ", ".join(inputs_list) if inputs_list else "-"
                
                act_table.add_row(format_id(aid), name, desc, inputs_str)
            
            console.print("\n")
            console.print(act_table)
            
        sys.exit(0)

    global_export_format = parsed_args.export

    capability_id = parsed_args.capability_id

    # Resolve numeric capability ID from filtered list
    if capability_id and capability_id.isdigit():
        filtered_caps = CapabilityRegistry.get_by_attr(capabilities_attrs)
        # Use same order as menu (insertion order of dict)
        options = []
        for cid, cls in filtered_caps.items():
            meta = getattr(cls, "METADATA", None)
            if not meta:
                continue
            options.append(cid)
        
        if include_actions:
            for aid, cls in ActionRegistry.get_by_attr(capabilities_attrs).items():
                meta = getattr(cls, "METADATA", None)
                if not meta:
                    continue
                options.append(aid)
        
        try:
            idx = int(capability_id)
            if 1 <= idx <= len(options):
                capability_id = options[idx - 1]
        except (ValueError, IndexError):
            pass

    if capability_id is None:
        console = Console()
        selector = SimpleMenuSelector(console=console)
        # ... (selector options building logic remains same)
        options = []
        filtered_caps = CapabilityRegistry.get_by_attr(capabilities_attrs)
        for cid, cls in filtered_caps.items():
            meta = getattr(cls, "METADATA", None)
            if not meta:
                continue
            name = getattr(meta, "name", cid)
            options.append({"label": f"{name}", "value": cid})
        
        if include_actions:
            filtered_actions = ActionRegistry.get_by_attr(capabilities_attrs)
            for aid, cls in filtered_actions.items():
                meta = getattr(cls, "METADATA", None)
                if not meta:
                    continue
                name = getattr(meta, "name", aid)
                options.append({"label": f"[yellow][Action][/yellow] {name}", "value": aid})

        if not options:
            print_message_box(RED, "Error", "No Options", "No capabilities or actions available for this mode.")
            sys.exit(1)

        selected = selector.select_option(options, title="Select a Capability (Query or Action):")
        if not selected:
            sys.exit(0)
        capability_id = selected['value'] if isinstance(selected, dict) else selected

    # Reconstruct sys.argv for the specific capability parser
    # We must ensure only relevant arguments are passed.
    # The previous logic blindly appended remaining_args + extra_args, which might contain
    # arguments not understood by the capability parser (like --export if handled globally but not locally?)
    # Actually, argparse handles extra args gracefully with parse_known_args.
    
    # The issue is likely that we are NOT stripping the initial script name and 'run' command properly
    # when constructing the new sys.argv for the *next* parser, or the *next* parser expects
    # 'capability_id' as a positional argument, but we are providing it via sys.argv[1].
    
    # Let's verify what real_parser expects.
    # real_parser.add_argument("capability_id", ...)
    
    # So sys.argv should look like: ['run.py', 'capability_id', '--other-arg', 'val']
    
    # Remove help arguments if they were used to trigger the menu
    clean_remaining_args = [arg for arg in remaining_args if arg not in ["-h", "--help"]]
    
    sys.argv = [sys.argv[0], capability_id] + clean_remaining_args + extra_args

    # Try to find as capability first
    cap_class = CapabilityRegistry.get(capability_id)
    if cap_class:
        cap = cap_class()
        strategy = cap.get_default_cli_strategy(repository=simple_repo)

        if not strategy:
            print(f"The capability '{cap.metadata.name}' does not support CLI execution.")
            sys.exit(1)

        real_parser = argparse.ArgumentParser(
            description=f"Run {cap.metadata.name}",
            fromfile_prefix_chars="@",
        )
        real_parser.add_argument("capability_id", help="ID of the capability to run")
        real_parser.add_argument(
            "--export",
            choices=["rich", "json"],
            default="rich",
            help="Output format",
        )

        strategy.setup_parser(real_parser)

        if global_export_format:
            for action in real_parser._actions:
                if action.dest == "export":
                    action.default = global_export_format

        final_args, unknown = real_parser.parse_known_args()
        
        # If unknown args are present and this capability doesn't handle them, 
        # we might want to warn or just ignore if they were intended for other capabilities in a chain
        # For now, we just ignore them to prevent crash when passing args for Action to a Capability
        
        console = Console()
        strategy.run(console, final_args, cap)
        sys.exit(0)

    # If not capability, try action
    if include_actions:
        action_class = ActionRegistry.get(capability_id)
        if action_class:
            action = action_class()
            strategy = action.get_default_cli_strategy(repository=simple_repo)
            
            if not strategy:
                # Default strategy for actions if not provided? 
                # For now, require strategy or fail
                print(f"The action '{action.metadata.name}' does not support CLI execution.")
                sys.exit(1)
            
            real_parser = argparse.ArgumentParser(
                description=f"Run {action.metadata.name}",
                fromfile_prefix_chars="@",
            )
            real_parser.add_argument("capability_id", help="ID of the action to run")
            real_parser.add_argument(
                "--export",
                choices=["rich", "json"],
                default="rich",
                help="Output format",
            )
            
            strategy.setup_parser(real_parser)

            if global_export_format:
                for action_arg in real_parser._actions:
                    if action_arg.dest == "export":
                        action_arg.default = global_export_format

            # Use parse_known_args to allow extra args to pass through if not handled by this action
            final_args, unknown = real_parser.parse_known_args()

            console = Console()
            strategy.run(console, final_args, action)
            sys.exit(0)

    print_message_box(RED, "Error", "Not Found", f"ID '{capability_id}' not found in capabilities{' or actions' if include_actions else ''}.")
    sys.exit(1)


if __name__ == "__main__":
    main()
