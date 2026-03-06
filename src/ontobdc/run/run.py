#!/usr/bin/env python3

import os
import sys
import argparse
import yaml
from rich.console import Console

# Bootstrap: Setup project root first to allow ontobdc imports
# We import directly from util (local file) because ontobdc package is not yet resolvable
try:
    from .util import setup_project_root, load_capability_packages
except ImportError:
    # Fallback: manually add current dir to path if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from util import setup_project_root, load_capability_packages

setup_project_root()

from ontobdc.run.ui import YELLOW, print_message_box, RED

# Debug start
# console = Console()
# console.print("[bold cyan]OntoBDC Run: Starting...[/bold cyan]")

from ontobdc.run.core.action import ActionRegistry
from ontobdc.run.core.selector import SimpleMenuSelector
from ontobdc.run.core.capability import CapabilityRegistry
from ontobdc.run.core.loader import CapabilityLoader, ActionLoader
from ontobdc.module.resource.adapter.repository import SimpleFileRepository
# from ontobdc.plugin.template.table import print_table
from ontobdc.plugin.template.card import print_cards

try:
    # Scan for capabilities in the configured packages
    packages_to_scan = load_capability_packages()
    
    # Use set to avoid duplicates if config repeats them
    packages_to_scan = list(set(packages_to_scan))
    
    all_capabilities = []
    all_actions = []
    
    # Use a set to track loaded IDs to prevent duplicates
    # Since capabilities are classes, we can't easily hash them by content unless they have __hash__
    # But we can check their ID property if instantiated, or metadata attribute
    seen_capability_ids = set()
    seen_action_ids = set()
    
    for pkg in packages_to_scan:
        try:
            caps = CapabilityLoader.load_from_package(pkg)
            acts = ActionLoader.load_from_package(pkg)
            
            # Deduplicate Capabilities
            for cap_cls in caps:
                try:
                    # Try to get ID from metadata
                    # Assuming metadata is available on class or instance
                    # For safety, instantiate temporarily (lightweight usually) or inspect class attr
                    if hasattr(cap_cls, "METADATA"):
                        cid = cap_cls.METADATA.id
                    else:
                        # Fallback to instantiation
                        cid = cap_cls().metadata.id
                    
                    if cid not in seen_capability_ids:
                        all_capabilities.append(cap_cls)
                        seen_capability_ids.add(cid)
                except Exception:
                    # If we can't determine ID, append anyway? No, safer to skip or warn
                    pass

            # Deduplicate Actions
            for act_cls in acts:
                try:
                    if hasattr(act_cls, "METADATA"):
                        aid = act_cls.METADATA.id
                    else:
                        aid = act_cls().metadata.id
                    
                    if aid not in seen_action_ids:
                        all_actions.append(act_cls)
                        seen_action_ids.add(aid)
                except Exception:
                    pass

        except ImportError:
            # If a configured package is missing, continue
            pass
        except Exception as e:
             # Other errors might be critical, log but try to continue
             print_message_box(RED, "Error", f"Loading Error in {pkg}", str(e))
    
    capabilities = all_capabilities
    actions = all_actions

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
    explicit_capability_id = None

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

        if arg == "--id":
            if i + 1 < len(sys.argv):
                explicit_capability_id = sys.argv[i+1]
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
        print_cards(
                {
                    "title": "Available Capabilities",
                    "headers": {
                        "ID": {"style": "cyan", "no_wrap": False, "overflow": "fold"},
                        "Name": {"style": "green"},
                        "Description": {"style": "dim"},
                        "Inputs": {"style": "dim"}
                    },
                    "values": {
                        "capabilities": capabilities,
                        "actions": actions
                    }
                }
            )
        # console.print("[bold cyan]OntoBDC Run: Finished (Help).[/bold cyan]")
        sys.exit(0)
        

    outer_parser = argparse.ArgumentParser(add_help=False)
    outer_parser.add_argument(
        "--export",
        choices=["rich", "json"],
        help="Output format",
    )
    # Parse just to check export flag globally if set early
    # But wait, we want to parse the first positional arg as capability_id
    
    if len(cleaned_argv) <= 1 and not explicit_capability_id:
        # Interactive mode if no args (except prog name)
        
        # Construct options for SimpleMenuSelector
        options = []
        
        def is_satisfied(meta, attrs):
            """Check if all required inputs are present in attrs."""
            schema = getattr(meta, "input_schema", {}).get("properties", {})
            if not schema:
                return True
                
            for key, prop in schema.items():
                # Skip repository injection
                if "repository" in key.lower():
                    continue
                    
                if prop.get("required", False):
                    # Check if key is in attrs
                    if key not in attrs:
                        return False
            return True

        # Capabilities
        for cap_class in capabilities:
            try:
                cap = cap_class()
                meta = cap.metadata
                
                # Check required inputs against capabilities_attrs (which contains CLI args like --key=val)
                if is_satisfied(meta, capabilities_attrs):
                    options.append({
                        "label": f"[green]{meta.name}[/green] ({meta.id})",
                        "value": cap
                    })
            except Exception:
                continue

        # Actions
        if include_actions:
            for act_class in actions:
                try:
                    act = act_class()
                    meta = act.metadata
                    
                    if is_satisfied(meta, capabilities_attrs):
                        options.append({
                            "label": f"[yellow]{meta.name}[/yellow] ({meta.id})",
                            "value": act
                        })
                except Exception:
                    continue

        if not options:
            print_message_box(YELLOW, "Warning", "Loading Error", "No matching capabilities found (missing required arguments?).")
            sys.exit(1)

        selector = SimpleMenuSelector()
        selected = selector.select_option(options, title="Select Capability/Action:")
        
        if not selected:
            sys.exit(0)
            
        # selected is the instance (cap or act)
        # We need its ID to proceed with existing logic, or just use the instance directly
        # The existing logic below re-instantiates based on ID.
        # Let's extract ID.
        capability_id = selected.metadata.id
        
        # If it's an action, we need to know
        if ActionRegistry.get(capability_id):
             include_actions = True
        
    else:
        if explicit_capability_id:
            capability_id = explicit_capability_id
        else:
            capability_id = cleaned_argv[1]
        # Remove prog name and capability_id
        extra_args_start_index = 2
    
    # Check if capability exists
    capability_class = CapabilityRegistry.get(capability_id)
    
    if capability_class:
        # Instantiate capability
        cap = capability_class()
        
        # We need to find the CLI adapter/strategy for this capability
        strategy = cap.get_default_cli_strategy(repository=simple_repo)
        
        if not strategy:
            print(f"The capability '{cap.metadata.name}' does not support CLI execution.")
            sys.exit(1)
            
        # Setup argparse for this capability
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
        
        # Parse arguments
        # We need to filter out args that are not for this parser?
        # Or just pass everything and let argparse complain/ignore?
        # extra_args collected above might contain flags.
        
        # Merge cleaned_argv remainder (if any) and extra_args
        # Actually we parsed everything into extra_args manually above? No.
        # We constructed capabilities_attrs manually.
        # But for the capability execution, we want to pass CLI flags.
        
        # Let's re-parse sys.argv properly or use the cleaned_argv + extra_args logic?
        # The logic above was a bit mixed.
        
        # Simpler approach:
        # We know capability_id. We know extra flags provided.
        # Let's just use parse_known_args on sys.argv (excluding prog and capability_id)
        
        # But we modified sys.argv processing above.
        # Let's rely on `extra_args` collected? No, `extra_args` collected attributes.
        
        # We should probably pass the raw arguments that were not consumed by our manual loop?
        # But our manual loop consumed everything into `capabilities_attrs`.
        # This design seems to conflate attribute injection with CLI arguments.
        
        # Assuming for now we just want to run with default interactive or simple args.
        # If user passed specific flags for the capability, they should be in sys.argv.
        
        # Let's try to parse from sys.argv, filtering out what we handled?
        # Or just parse_known_args from the point after capability_id.
        
        # Find index of capability_id in sys.argv
        try:
            # When selected interactively, capability_id is not in sys.argv
            # So remaining_args from sys.argv might be just flags or empty
            # But the parser expects capability_id as first positional argument!
            if capability_id not in sys.argv:
                # We must inject capability_id into args for parser
                # But wait, remaining_args logic below relies on index.
                # If not present, we use cleaned_argv + extra_args? No.
                # We just use the raw flags provided.
                
                # Filter out program name and run command if present
                # Actually, in interactive mode, sys.argv might just be ['ontobdc', 'run', '--flag']
                # We want the flags.
                
                # Let's collect flags that are not 'run' or the program name.
                # Simplified: just use sys.argv[1:] but filter out 'run' if it's there?
                # Actually, the parser needs [capability_id, --flag, ...]
                
                # So we construct args_for_parser
                args_for_parser = [capability_id]
                
                # Append flags from sys.argv (skipping prog name)
                # We need to be careful not to duplicate things if logic is complex
                # But for interactive mode, usually user ran `ontobdc run` or `ontobdc run --flag`
                
                for arg in sys.argv[1:]:
                     # Skip 'run' command itself if present (it's usually sys.argv[1] if installed as entrypoint?)
                     # But entrypoint might be `ontobdc` calling this script.
                     # If we are here, we are running `python run.py` or via entrypoint.
                     # If via entrypoint, sys.argv[0] is script.
                     
                     # If user typed `ontobdc run`, sys.argv is ['.../ontobdc', 'run']
                     # We want to skip 'run' if it's not a flag.
                     if arg == "run": 
                         continue
                     if arg == "--act": # consume custom flag
                         continue
                     if arg in ["-h", "--help", "--json"]: # consume help flags
                         continue
                     
                     args_for_parser.append(arg)
                     
                remaining_args = args_for_parser
            else:
                idx = sys.argv.index(capability_id)
                remaining_args = sys.argv[idx:] # Include capability_id for parser!
                
        except ValueError:
            # Should not happen if check above works, but safety net
            # If we can't find it, we inject it
            args_for_parser = [capability_id]
            for arg in sys.argv[1:]:
                 if arg == "run": continue
                 if arg == "--act": continue
                 args_for_parser.append(arg)
            remaining_args = args_for_parser

        # Also need to handle global flags like --export if they appeared BEFORE capability_id
        global_export_format = None
        if "--export" in sys.argv:
             # This is tricky if it appeared before.
             # Let's just scan sys.argv for --export value
             try:
                 e_idx = sys.argv.index("--export")
                 if e_idx + 1 < len(sys.argv):
                     global_export_format = sys.argv[e_idx+1]
             except ValueError:
                 pass

        if global_export_format:
            # Ensure it overrides default in parser if not explicitly provided in remaining_args
            # (argparse uses last value if repeated, so if user provided it again it works)
            # But if user provided it before, we want it to apply.
            # We can set default.
            for action in real_parser._actions:
                if action.dest == "export":
                    action.default = global_export_format

        final_args, unknown = real_parser.parse_known_args(remaining_args)
        
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
