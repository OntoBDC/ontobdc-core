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
        ".__ontobdc__/config.yaml",
        "../.__ontobdc__/config.yaml",
        "../../.__ontobdc__/config.yaml"
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
                if data and 'capability' in data and isinstance(data['capability'], dict):
                    if data['capability'] and 'package' in data['capability'] and isinstance(data['capability']['package'], list):
                        raw_packages = data['capability']['package']
                        processed_packages = []

                        config_dir = os.path.dirname(os.path.abspath(found_config))

                        for pkg in raw_packages:
                            if isinstance(pkg, str):
                                processed_packages.append(pkg)
                            elif isinstance(pkg, dict):
                                pkg_id = pkg.get("id")
                                if pkg_id:
                                    processed_packages.append(pkg_id)

                                    # Handle local path
                                    if pkg.get("type") == "local" and pkg.get("path"):
                                        local_path = pkg.get("path")
                                        abs_path = os.path.abspath(os.path.join(config_dir, local_path))

                                        # Try to determine the import root
                                        parts = pkg_id.split('.')
                                        current_path = abs_path
                                        match = True
                                        # Walk up the path matching package parts
                                        for part in reversed(parts):
                                            if os.path.basename(current_path) == part:
                                                current_path = os.path.dirname(current_path)
                                            else:
                                                match = False
                                                break

                                        target_path = current_path if match else abs_path

                                        if target_path not in sys.path:
                                            sys.path.insert(0, target_path)

                        if processed_packages:
                            return processed_packages
        except Exception as e:
            # If error reading config, fallback silently
            print_message_box(RED, "Error", "Loading Error", str(e))
            pass
            
    return default_packages
