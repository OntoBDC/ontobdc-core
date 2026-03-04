#!/usr/bin/env python3

import os
import sys
import argparse
import yaml
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

def load_capability_packages():
    """
    Load capability packages from config/capability.yaml or fallback to default.
    Returns a list of package names.
    """
    default_packages = ["ontobdc.module"]
    
    # Try to locate config/capability.yaml
    # We look in CWD and typical project structure
    config_paths = [
        "config/capability.yaml",
        "../config/capability.yaml",
        "../../config/capability.yaml"
    ]
    
    found_config = None
    for path in config_paths:
        if os.path.exists(path):
            found_config = path
            break
            
    if found_config:
        try:
            with open(found_config, 'r') as f:
                data = yaml.safe_load(f)
                if data and 'packages' in data and isinstance(data['packages'], list):
                    packages = data['packages']
                    if packages: # If list is not empty
                        # print(f"DEBUG: Loaded capability packages from {found_config}: {packages}")
                        return packages
        except Exception as e:
            # If error reading config, fallback silently (or log warning if verbose)
            pass
            
    return default_packages

try:
    # Scan for capabilities in the configured packages
    packages_to_scan = load_capability_packages()
    
    all_capabilities = []
    all_actions = []
    
    for pkg in packages_to_scan:
        try:
            caps = CapabilityLoader.load_from_package(pkg)
            acts = ActionLoader.load_from_package(pkg)
            all_capabilities.extend(caps)
            all_actions.extend(acts)
        except ImportError:
            # If a configured package is missing, we might want to warn but continue?
            # Or fail? For now, let's continue but maybe print a message if in debug mode
            pass
        except Exception as e:
             # Other errors might be critical
             print_message_box(RED, "Error", f"Loading Error in {pkg}", str(e))
    
    # If no capabilities loaded at all, maybe try fallback if we weren't using default?
    # But if user configured explicit packages and they failed, that's likely an error state.
    
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

    # Debug print to diagnose argument parsing issues
    # print(f"DEBUG: sys.argv={sys.argv}")
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        # Standard arguments handling
        if arg == "--root-path":
            # root-path is manually handled, exclude from cleaned_argv
            if i + 1 < len(sys.argv):
                i += 2
