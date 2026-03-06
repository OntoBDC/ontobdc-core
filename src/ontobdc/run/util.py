import os
import sys
import yaml

RED = "red"
YELLOW = "yellow"
GREEN = "green"

def print_message_box(color, title, subtitle, message):
    # Minimal implementation to avoid dependencies if rich is not available or just simple text
    print(f"[{color.upper()}] {title} - {subtitle}: {message}")

def setup_project_root():
    """
    Sets up the project root in sys.path to ensure modules can be imported correctly
    when running scripts directly.
    """
    # Assuming this file is at ontobdc/run/util.py
    # We want to reach the parent directory of 'ontobdc'
    
    # Current file path: .../ontobdc/run/util.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Project root: .../ (two levels up from run/)
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return project_root

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
                        return packages
        except Exception as e:
            # If error reading config, fallback silently
            print_message_box(RED, "Error", "Loading Error", str(e))
            pass
            
    return default_packages
