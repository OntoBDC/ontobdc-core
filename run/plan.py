import argparse
import sys
import os
import shutil
import textwrap
import networkx as nx
from rich.console import Console
from rich.text import Text
from rich.style import Style
from typing import Dict, List, Set, Any, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from stack.src.bib.core.capability.registry import CapabilityRegistry
from stack.src.bib.core.capability.repository import LocalCapabilityRepository
from stack.src.bib.core.capability.metadata import CapabilityMetadata

console = Console()

GRAY = "bright_black"
CYAN = "cyan"
YELLOW = "yellow"
GREEN = "green"
RED = "red"
WHITE = "white"
BOLD = "bold"


def print_header(title: str):
    term_width = shutil.get_terminal_size().columns
    hline = "─" * term_width
    console.print(f"\n[{GRAY}]{hline}[/{GRAY}]")
    console.print(f"[{CYAN}]{title}[/{CYAN}]")
    console.print(f"[{GRAY}]{hline}[/{GRAY}]")


def print_step(name: str):
    console.print("")
    console.print(f"[{YELLOW}]❯ [{WHITE}]Planning [{CYAN}]{name}[/{CYAN}]")


def print_sub_step(msg: str, status: str = "success"):
    if status == "success":
        console.print(f"  [{GREEN}]✓ {msg}[/{GREEN}]")
    elif status == "error":
        console.print(f"  [{RED}]✗ {msg}[/{RED}]")
    elif status == "info":
        console.print(f"  [{GRAY}]• {msg}[/{GRAY}]")


def print_message_box(color: str, title_type: str, title_text: str, msg_text: str):
    console.print("")
    term_width = shutil.get_terminal_size().columns
    inner_width = term_width - 2
    hline = "─" * inner_width

    console.print(f"[{color}]╭{hline}╮[/{color}]")

    prefix = " >_ "
    type_formatted = f"[{BOLD} {color}]{title_type}[/{BOLD} {color}]"

    visible_len = 4 + len(title_type) + (1 + len(title_text) if title_text else 0)
    pad_len = max(0, inner_width - visible_len)
    padding = " " * pad_len

    line_content = f"[{color}]│[/{color}]{prefix}{type_formatted}"
    if title_text:
        line_content += f" {title_text}"
    line_content += f"{padding}[{color}]│[/{color}]"

    console.print(line_content)

    console.print(f"[{color}]│[/{color}]{' ' * inner_width}[{color}]│[/{color}]")

    lines = msg_text.split("\n")
    for line in lines:
        if not line:
            wrapped_lines = [" "]
        else:
            wrapped_lines = textwrap.wrap(line, width=inner_width, drop_whitespace=False)

        for wline in wrapped_lines:
            visible_len = Text.from_markup(wline).cell_len
            pad_len = max(0, inner_width - visible_len)
            padding = " " * pad_len
            console.print(
                f"[{color}]│[/{color}][{GRAY}]{wline}[/{GRAY}]{padding}[{color}]│[/{color}]"
            )

    console.print(f"[{color}]╰{hline}╯[/{color}]")


class ExecutionPlanner:
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
        self.graph = nx.DiGraph()

    def build_plan(
        self, target_capability_id: str, initial_context: Dict[str, Any] = None
    ) -> nx.DiGraph:
        if initial_context is None:
            initial_context = {}

        target_cap = self.registry.get(target_capability_id)
        if not target_cap:
            raise ValueError(f"Capability '{target_capability_id}' not found.")

        queue = [target_capability_id]
        visited = set()

        self.graph.add_node(
            target_capability_id, type="capability", metadata=target_cap.METADATA
        )

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            current_cap = self.registry.get(current_id)
            if not current_cap:
                continue

            print_step(f"requirements for {current_id.split('.')[-1]}")

            requirements = self._get_requirements(current_cap.METADATA)

            for req_key in requirements:
                if req_key in initial_context:
                    print_sub_step(f"Found input: {req_key}", "success")
                    self.graph.add_node(
                        req_key, type="context", value=initial_context[req_key]
                    )
                    self.graph.add_edge(req_key, current_id, label="provides")
                    continue

                provider_id = self._find_provider(req_key)
                if provider_id:
                    print_sub_step(
                        f"Resolved dependency: {req_key} <- {provider_id}", "success"
                    )
                    self.graph.add_node(
                        provider_id,
                        type="capability",
                        metadata=self.registry.get(provider_id).METADATA,
                    )
                    self.graph.add_edge(
                        provider_id, current_id, label=f"provides: {req_key}"
                    )
                    if provider_id not in visited:
                        queue.append(provider_id)
                else:
                    print_sub_step(f"Missing dependency: {req_key}", "error")
                    self.graph.add_node(req_key, type="missing")
                    self.graph.add_edge(req_key, current_id, label="required")

            if hasattr(current_cap.METADATA, "request") and current_cap.METADATA.request:
                for req in current_cap.METADATA.request:
                    condition = req.get("condition")
                    satisfied = False
                    if not condition:
                        satisfied = True
                    elif isinstance(condition, str):
                        if condition in initial_context and initial_context[condition]:
                            satisfied = True

                    if satisfied:
                        provider_id = req["id"]
                        print_sub_step(
                            f"Resolved direct dependency: {provider_id}", "success"
                        )
                        provider_cap = self.registry.get(provider_id)
                        if provider_cap:
                            self.graph.add_node(
                                provider_id,
                                type="capability",
                                metadata=provider_cap.METADATA,
                            )
                            self.graph.add_edge(
                                provider_id, current_id, label="requested"
                            )
                            if provider_id not in visited:
                                queue.append(provider_id)
                        else:
                            print_sub_step(
                                f"Missing requested capability: {provider_id}", "error"
                            )

        return self.graph

    def _get_requirements(self, metadata: CapabilityMetadata) -> List[str]:
        reqs = []
        if metadata.input_schema and "properties" in metadata.input_schema:
            for key, prop in metadata.input_schema["properties"].items():
                if prop.get("required", False):
                    reqs.append(key)
        return reqs

    def _find_provider(self, key: str) -> Optional[str]:
        for cap_id, cap_cls in self.registry.get_all().items():
            meta = cap_cls.METADATA
            if meta.output_schema and "properties" in meta.output_schema:
                if key in meta.output_schema["properties"]:
                    return cap_id
        return None


def main():
    parser = argparse.ArgumentParser(description="InfoBIM Execution Planner")
    parser.add_argument(
        "capability_id", help="The ID of the target capability to plan for"
    )
    parser.add_argument(
        "--context", nargs="*", help="Initial context in key=value format"
    )

    args = parser.parse_args()

    print_header("Running Execution Planner...")

    repo = LocalCapabilityRepository("stack.src.plugin.capability")
    registry = CapabilityRegistry()
    registry.register_from(repo)

    initial_ctx = {}
    if args.context:
        for item in args.context:
            if "=" in item:
                k, v = item.split("=", 1)
                if v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                initial_ctx[k] = v

    planner = ExecutionPlanner(registry)

    try:
        plan_graph = planner.build_plan(args.capability_id, initial_ctx)

        missing = [
            n for n, d in plan_graph.nodes(data=True) if d.get("type") == "missing"
        ]

        if missing:
            msg = "The following dependencies could not be resolved:\n"
            msg += "\n".join([f"• {m}" for m in missing])
            msg += "\n\nPlease provide them via --context or implement a provider capability."
            print_message_box(RED, "Error", "Plan Execution Impossible", msg)
        else:
            try:
                execution_order = list(nx.topological_sort(plan_graph))
                steps = [
                    node
                    for node in execution_order
                    if plan_graph.nodes[node].get("type") == "capability"
                ]

                msg = "Execution Plan Ready:\n"
                for i, step_id in enumerate(steps, 1):
                    meta = plan_graph.nodes[step_id].get("metadata")
                    outputs = []
                    if meta and meta.output_schema and "properties" in meta.output_schema:
                        outputs = list(meta.output_schema["properties"].keys())

                    msg += f"\n[{WHITE}]{i}.[/{WHITE}] [{CYAN}]{step_id}[/{CYAN}]\n"
                    if outputs:
                        for out in outputs:
                            msg += f"   [{WHITE}]❯[/{WHITE}] {out}\n"
                    else:
                        msg += f"   [{GRAY}]❯ (No explicit output)[/{GRAY}]\n"

                print_message_box(GREEN, "Success", "Plan Generated", msg)

            except nx.NetworkXUnfeasible:
                print_message_box(
                    RED, "Error", "Cycle Detected", "Circular dependency detected in the plan."
                )

    except Exception as e:
        print_message_box(RED, "Error", "Planner Exception", str(e))


if __name__ == "__main__":
    main()

