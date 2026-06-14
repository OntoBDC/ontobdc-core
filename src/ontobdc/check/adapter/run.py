import json
import os
import sys

def main():
    if len(sys.argv) < 5:
        print("{}")
        return

    config_json_path = sys.argv[1]
    config_yaml_path = sys.argv[2]
    name = sys.argv[3]
    engine_name = sys.argv[4]

    try:
        with open(config_json_path) as f:
            data = json.load(f) or {}
    except Exception:
        data = {}

    try:
        import yaml
        with open(config_yaml_path) as f:
            yaml_data = yaml.safe_load(f) or {}
    except Exception:
        yaml_data = {}

    out = {}
    base = (data.get('base', {}) or {}).get(name, []) or []
    engine = ((data.get('engine', {}) or {}).get(engine_name, {}) or {}).get(name, []) or []

    yaml_checks = []
    try:
        chk_node = yaml_data.get('check', {}) or {}
        if isinstance(chk_node, dict):
            # If name is 'all' or similar global scope, we handled it outside.
            # But if a specific module is requested, e.g., 'a3', look at chk_node.get('a3')
            if name in chk_node:
                mod_cfg = chk_node[name]
                if isinstance(mod_cfg, dict):
                    # Iterate through groups (like 'infra', 'engine')
                    for k, v in mod_cfg.items():
                        if k not in ['auto', 'behavior'] and isinstance(v, list):
                            # Append group namespace for proper resolution by check.sh
                            for check_item in v:
                                yaml_checks.append(f"{k}.{check_item}")
            else:
                for mod, mod_cfg in chk_node.items():
                    if isinstance(mod_cfg, dict) and mod_cfg.get('auto') is True:
                        scope_items = mod_cfg.get(name, [])
                        if isinstance(scope_items, list):
                            yaml_checks.extend(scope_items)
    except Exception:
        pass

    if base or yaml_checks:
        out['base'] = ' '.join(base + yaml_checks)
    if engine:
        out['engine'] = ' '.join(engine)

    script_path = (data.get('script_path', {}) or {}).get('alternative', None)
    candidates = []
    if isinstance(script_path, str):
        candidates = [script_path]
    elif isinstance(script_path, list):
        candidates = [c for c in script_path if isinstance(c, str)]

    env_key = None
    for c in candidates:
        if isinstance(c, str) and os.path.isabs(c) and c.rstrip(os.sep).endswith(os.sep + 'check'):
            env_key = os.path.basename(os.path.dirname(c.rstrip(os.sep)))
            break

    if env_key:
        env_cfg = data.get(env_key, None)
        if isinstance(env_cfg, dict):
            env_checks = (env_cfg.get(name, []) or [])
            if env_checks:
                out[env_key] = ' '.join(env_checks)

    print(json.dumps(out))

if __name__ == "__main__":
    main()
