
import re
import os
import importlib
from typing import List
from ontobdc.shared.adapter.util import to_pascal_case, to_snake_case
from ontobdc.shared.domain.port.resolver import CapabilityParamResolverRunnerPort
from ontobdc.shared.domain.port.context import CliContextPort


class CapabilityParamResolverRunner(CapabilityParamResolverRunnerPort):
    RESOLVABLE_URI: List[str] = [
        'http://ontobdc.org/ontology/domain/',
        'org.ontobdc.',
    ]

    def resolve(self, context: CliContextPort, prop_uri: str, prop: str) -> None:
        uri = (prop_uri or "").strip()
        if not uri:
            return

        if not any(uri.startswith(base) for base in self.RESOLVABLE_URI):
            return

        resolver_base = self._resolver_base_name(uri)
        if not resolver_base:
            return

        module_basename = to_snake_case(resolver_base)
        resolver_class_name = f"{to_pascal_case(resolver_base)}ParamResolver"

        ontobdc_dir = str(ConfigDataAdapter().script_dir)

        for entry in sorted(os.listdir(ontobdc_dir)):
            entry_path = os.path.join(ontobdc_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry.startswith((".", "_")):
                continue

            resolver_dir = os.path.join(entry_path, "plugin", "resolver")

            if not os.path.isdir(resolver_dir):
                continue

            resolver_path = os.path.join(resolver_dir, f"{module_basename}.py")

            if not os.path.isfile(resolver_path):
                continue

            module_name = f"ontobdc.{entry}.plugin.resolver.{module_basename}"
            module = importlib.import_module(module_name)
            resolver_cls = getattr(module, resolver_class_name, None)
            if resolver_cls is None:
                raise ImportError(f"Resolver class '{resolver_class_name}' not found in '{module_name}'")

            resolver = resolver_cls()
            resolve_fn = getattr(resolver, "resolve", None)
            if not callable(resolve_fn):
                raise TypeError(f"Resolver '{resolver_class_name}' must implement a callable 'resolve' method")

            resolve_fn(context, uri, prop)

            return

    def _resolver_base_name(self, uri: str) -> str:
        if uri.startswith("org.ontobdc."):
            return uri.split(".")[-1].strip()

        if "#" in uri:
            return uri.split("#")[-1].strip()

        m = re.search(r"/([^/#]+)$", uri)
        if m:
            return (m.group(1) or "").strip()

        return ""
