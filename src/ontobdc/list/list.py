#!/usr/bin/env python3

import sys
import json
import argparse
import os

# Setup path
try:
    from ontobdc.run.util import setup_project_root, load_capability_packages
except ImportError:
    # Fallback: manually add current dir to path if needed
    # We assume this script is in ontobdc/list/list.py
    # So we need to go up 2 levels to reach ontobdc/run/util.py via package import?
    # No, we need to add project root to path.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from ontobdc.run.util import setup_project_root, load_capability_packages

setup_project_root()

from ontobdc.run.adapter.loader import CapabilityLoader, ActionLoader

def main():
    parser = argparse.ArgumentParser(description="List OntoBDC capabilities")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    args = parser.parse_args()

    try:
        packages = load_capability_packages()
        packages = list(set(packages))
        
        capabilities = []
        actions = []
        
        for pkg in packages:
            try:
                caps = CapabilityLoader.load_from_package(pkg)
                acts = ActionLoader.load_from_package(pkg)
                
                for cap_cls in caps:
                    # Convert metadata to dict
                    if hasattr(cap_cls, "METADATA"):
                        meta = cap_cls.METADATA
                        # We can use asdict() if it's a dataclass, or manually construct
                        # Assuming CapabilityMetadata is a pydantic model or dataclass
                        # Let's check type. If pydantic, .dict(). If dataclass, asdict.
                        # For now, let's manually extract fields we know exist to be safe/consistent
                        
                        # Handle input_schema types serialization (classes to strings)
                        input_schema = meta.input_schema.copy() if meta.input_schema else {}
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
                            "tags": meta.tags if isinstance(meta.tags, (list, tuple)) else [], # Ensure tags is hashable-ish (list of strings usually) or handle later
                            "supported_languages": meta.supported_languages,
                            "input_schema": input_schema,
                            "output_schema": meta.output_schema,
                            "raises": meta.raises,
                            "type": "capability"
                        }
                        capabilities.append(cap_dict)
                        
                for act_cls in acts:
                    if hasattr(act_cls, "METADATA"):
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
                # print(f"Error loading package {pkg}: {e}", file=sys.stderr)
                pass

        # Deduplicate by ID
        # Convert list of dicts to dictionary keyed by ID
        # This avoids set(capabilities) which causes 'unhashable type: dict'
        unique_caps = {c['id']: c for c in capabilities}.values()
        unique_acts = {a['id']: a for a in actions}.values()
        
        all_items = list(unique_caps) + list(unique_acts)
        
        if args.format == "json":
            print(json.dumps(all_items, indent=2))
        else:
            for item in all_items:
                print(f"{item['id']} - {item['name']}")

    except Exception as e:
        print(f"Error listing capabilities: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
