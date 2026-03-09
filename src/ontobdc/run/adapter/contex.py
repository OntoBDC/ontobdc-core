
import os
import pkgutil
import inspect
import importlib
from typing import List, Dict, Any, Type
import ontobdc.run.core.strategy as strategy_pkg
from ontobdc.run.core.capability import Capability
from ontobdc.run.core.port.contex import CliContextPort, CliContextStrategyPort


class CliContextAdapter(CliContextPort):
    def __init__(self, argv: List[str]):
        self._raw_argv = argv
        self._unprocessed_args = argv[1:]
        self._parameters: Dict[str, Dict[str, Any]] = {}

    @property
    def raw_args(self) -> List[str]:
        return self._raw_argv

    @property
    def unprocessed_args(self) -> List[str]:
        return self._unprocessed_args

    @property
    def parameters(self) -> Dict[str, Dict[str, Any]]:
        return self._parameters

    @property
    def is_capability_targeted(self) -> bool:
        return self.target_capability_id is not None

    @property
    def target_capability_id(self) -> str | None:
        if "capability_id" in self._parameters:
            return self._parameters["capability_id"].get("value")
        return None

    def add_parameter(self, param_key: str, param_value: Dict[str, Any]):
        if param_key not in self._parameters:
            self._parameters[param_key] = {}

        self._parameters[param_key].update(param_value)

    def get_parameter_value(self, param_key: str) -> Any:
        param = self._parameters.get(param_key)
        if param:
            return param.get("value")

        return None

    def clear_parameters(self, param_keys: List[str]) -> None:
        for param_key in param_keys:
            if param_key in self._unprocessed_args:
                self._unprocessed_args.remove(param_key)


class CliContextResolver:
    def resolve(self, argv: List[str]) -> CliContextPort:
        context: CliContextPort = CliContextAdapter(argv)

        # Scan and load strategies dynamically
        strategies: List[CliContextStrategyPort] = []
        
        # 1. Load built-in strategies
        package = strategy_pkg
        prefix = package.__name__ + "."
        
        for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
            try:
                module = importlib.import_module(name)
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, CliContextStrategyPort) and 
                        obj is not CliContextStrategyPort):
                        strategies.append(obj())
            except ImportError:
                continue

        # 2. Load custom strategies from config/context.yaml
        config_path = os.path.join(os.getcwd(), "config", "context.yaml")

        if os.path.exists(config_path):
            import yaml
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}

                # Check for 'strategies' key or try to load from 'parameters' if it contains module definitions
                custom_strategies = config.get('strategies', [])
                if not custom_strategies and 'parameters' in config:
                    # Fallback if user puts strategies in parameters list
                    params = config['parameters']
                    if isinstance(params, list):
                        for p in params:
                            if isinstance(p, str) and '.' in p: # Simple heuristic
                                custom_strategies.append(p)
                            elif isinstance(p, dict) and 'module' in p:
                                custom_strategies.append(p['module'])

                for module_name in custom_strategies:
                    try:
                        module = importlib.import_module(module_name)

                        for _, name, is_pkg in pkgutil.walk_packages(module.__path__):
                            try:
                                submodule = importlib.import_module(f"{module.__name__}.{name}")
                                for _, obj in inspect.getmembers(submodule):
                                    if (inspect.isclass(obj) and
                                        issubclass(obj, CliContextStrategyPort) and 
                                        obj is not CliContextStrategyPort):
                                        strategies.append(obj())
                            except ImportError:
                                pass
                    except ImportError as e:
                        # print(f"Warning: Failed to import custom strategy module '{module_name}': {e}")
                        pass
            except Exception as e:
                # print(f"Warning: Failed to load strategies from {config_path}: {e}")
                pass

        # Execute strategies
        # print(strategies)

        # Execute strategies
        # Note: Order might matter. If so, strategies should define priority or be named strictly.
        # For now, executing in discovery order.
        for strategy in strategies:
            context = strategy.execute(context)
            
        return context

    def is_satisfied_by(self, capability: Capability, context: CliContextPort) -> bool:
        required_params = {}
        for param_name, param in capability.METADATA.input_schema['properties'].items():
            if param["required"]:
                if 'uri' not in param.keys():
                    return False

                required_params[param_name] = param

        available_params: List[str] = []
        for param_name, param in context.parameters.items():
            if "param_uri" in param.keys():
                available_params.append(param["param_uri"])

        for param in required_params.values():
            if param["uri"] not in available_params:
                return False

        return True
