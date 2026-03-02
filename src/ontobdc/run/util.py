import os
import sys

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
