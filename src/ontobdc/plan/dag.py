
import io
import sys
import json
import contextlib
import subprocess
import os
import re
from uuid import uuid4
from graphlib import TopologicalSorter
from typing import Dict, Any, Optional, List, Tuple
from ontobdc.list.list import main as list_capability
from ontobdc.plan.adapter.ontology import DirectedAcyclicGraph
from ontobdc.run.domain.port.contex import CliContextPort
from ontobdc.run.adapter.contex import CliContextResolver


def _get_capabilities_json() -> str:
    buf = io.StringIO()
    original_argv = sys.argv[:]
    try:
        sys.argv = [original_argv[0], "--json"]
        with contextlib.redirect_stdout(buf):
            try:
                list_capability()
            except SystemExit:
                pass
    finally:
        sys.argv = original_argv
    return buf.getvalue().strip()


def _get_arg_value(flag: str) -> Optional[str]:
    args = sys.argv[1:]
    try:
        i = args.index(flag)
        if i + 1 < len(args):
            v = args[i + 1]
            if not v.startswith("-"):
                return v
    except ValueError:
        pass
    return None

def _escape_urn_part(dag_object: DirectedAcyclicGraph, uri_value: str) -> str:
    dni: Optional[Tuple[str, str]] = dag_object.get_dni_from_uri(uri_value)
    if not dni:
        raise ValueError(f"URI {uri_value} does not match any known domain name")

    all_parts: List[str] = uri_value[len(dni[0]) + 1:].split(".")
    return f"urn:{dni[1]}:{":".join(all_parts)}"

current_dir = os.path.dirname(os.path.abspath(__file__))
msg_box_script = os.path.join(current_dir, "..", "cli", "message_box.sh")
capability_id: Optional[str] = _get_arg_value("--id")

if not capability_id or not capability_id.strip():
    if os.path.exists(msg_box_script):
        subprocess.run(["bash", msg_box_script, "RED", "Error", "Argument Missing", "You must define the capability id. Use: --id <capability_id>"], check=False)
    else:
        print("Error: --id is required", file=sys.stderr)
    sys.exit(1)

capabilities_json = _get_capabilities_json()
try:
    capabilities = json.loads(capabilities_json) if capabilities_json else []
except Exception:
    capabilities = []

target_capability: Optional[Dict[str, Any]] = None
for capability in capabilities:
    if capability.get("id") == capability_id:
        target_capability = capability
        break

if not target_capability:
    if os.path.exists(msg_box_script):
        subprocess.run(["bash", msg_box_script, "RED", "Error", "Capability Not Found", f"Capability {capability_id} not found"], check=False)
    else:
        print(f"Error: Capability {capability_id} not found", file=sys.stderr)

    sys.exit(1)

# dot_mode = "--dot" in sys.argv
# if a != "--dot"
argv_for_context = [a for a in sys.argv]

resolver: CliContextResolver = CliContextResolver()
context: CliContextPort = resolver.resolve(argv_for_context)

if context.unprocessed_args:
    unknown_args = " ".join(context.unprocessed_args)
    if os.path.exists(msg_box_script):
        subprocess.run(["bash", msg_box_script, "YELLOW", "Warning", "Invalid Argument", f"The following arguments were not recognized and will be ignored: {unknown_args}"], check=False)
    else:
        print(f"WARNING: The following arguments were not recognized and will be ignored: {unknown_args}", file=sys.stderr)

dag_object: DirectedAcyclicGraph = DirectedAcyclicGraph()

_nid = dag_object.get_dni_from_uri(capability_id)[1]
plan_uri = f"urn:{_nid}:instance:resource:plan:{uuid4()}"

dag_object.add_individual(plan_uri, f"urn:{_nid}:domain:resource:plan")

for capability in capabilities:
    capability_uri: str = _escape_urn_part(dag_object, capability.get("id"))
    dag_object.add_class(capability_uri)

for param_key, param in (context.parameters or {}).items():
    param_uri: str = _escape_urn_part(dag_object, param.get("uri"))
    dag_object.add_class(param_uri)
    dag_object.add_property(param['value'], param_uri)

input_schema = target_capability.get("input_schema") or {}
input_properties: Dict[str, Any] = (input_schema.get("properties") or {}) if isinstance(input_schema, dict) else {}
for prop_name, prop in input_properties.items():
    input_uri: str = _escape_urn_part(dag_object, prop.get("uri"))
    dag_object.add_class(input_uri)

    
# capability_uri = _escape_urn_part(dag_object, capability_id)
# dag_object.add_individual(plan_uri, OWL.NamedIndividual)



#     inp_uri: str = f"urn:{_escape_urn_part(prop.get("uri"))}"
#     dag_object.add_uri(cap_uri, "ontobdc/hasInput", inp_uri)
    # dag_object.add_literal(inp_uri, "ontobdc:property", prop_name)
# print(input_properties)




# output_schema = target_capability.get("output_schema") or {}
# output_properties: Dict[str, Any] = (output_schema.get("properties") or {}) if isinstance(output_schema, dict) else {}

# dag_object.add_capability_plan(
#     plan_uri=plan_uri,
#     cap_uri=cap_uri,
#     capability_id=capability_id,
#     capability_name=target_capability.get("name"),
#     capability_version=target_capability.get("version"),
#     parameters=context.parameters or {},
#     input_properties=input_properties,
#     output_properties=output_properties,
# )

print(dag_object.to_turtle())

# for param_key, param_meta in (context.parameters or {}).items():
#     p_uri = f"urn:ontobdc:context:param:{_escape_urn_part(param_key)}"
#     add_uri(plan_uri, "ontobdc:hasParameter", p_uri)
#     add_lit(p_uri, "ontobdc:key", param_key)
#     if isinstance(param_meta, dict):
#         if "uri" in param_meta and param_meta["uri"] is not None:
#             add_lit(p_uri, "ontobdc:uri", str(param_meta["uri"]))
#         if "param_uri" in param_meta and param_meta["param_uri"] is not None:
#             add_lit(p_uri, "ontobdc:paramUri", str(param_meta["param_uri"]))
#         if "value" in param_meta:
#             try:
#                 add_lit(p_uri, "ontobdc:value", json.dumps(param_meta["value"], ensure_ascii=False))
#             except Exception:
#                 add_lit(p_uri, "ontobdc:value", str(param_meta["value"]))


# dag_edges: Dict[str, set[str]] = {}


# def add_node(node: str) -> None:
#     if node not in dag_edges:
#         dag_edges[node] = set()


# def add_dep(node: str, depends_on: str) -> None:
#     add_node(node)
#     add_node(depends_on)
#     dag_edges[node].add(depends_on)


# add_node(cap_uri)

# for prop_name, prop in input_properties.items():
#     inp_uri = f"{cap_uri}:input:{_escape_urn_part(prop_name)}"
#     add_uri(cap_uri, "ontobdc:hasInput", inp_uri)
#     add_lit(inp_uri, "ontobdc:property", prop_name)
#     if isinstance(prop, dict):
#         if prop.get("uri"):
#             add_lit(inp_uri, "ontobdc:uri", str(prop.get("uri")))
#         if prop.get("required") is not None:
#             add_lit(inp_uri, "ontobdc:required", str(bool(prop.get("required"))).lower())
#         if prop.get("type") is not None:
#             add_lit(inp_uri, "ontobdc:type", str(prop.get("type")))
#         if prop.get("description"):
#             add_lit(inp_uri, "ontobdc:description", str(prop.get("description")))
#     add_dep(cap_uri, inp_uri)

# for prop_name, prop in output_properties.items():
#     out_uri = f"{cap_uri}:output:{_escape_urn_part(prop_name)}"
#     add_uri(cap_uri, "ontobdc:hasOutput", out_uri)
#     add_lit(out_uri, "ontobdc:property", prop_name)
#     if isinstance(prop, dict):
#         if prop.get("type") is not None:
#             add_lit(out_uri, "ontobdc:type", str(prop.get("type")))
#         if prop.get("description"):
#             add_lit(out_uri, "ontobdc:description", str(prop.get("description")))
#     add_dep(out_uri, cap_uri)

# ts = TopologicalSorter(dag_edges)
# topo_order = list(ts.static_order())

# rdf = {
#     "prefixes": prefixes,
#     "triples": [
#         {"s": s, "p": p, "o": o, "literal": lit}
#         for (s, p, o, lit) in triples
#     ],
#     "topological_order": topo_order,
# }

# ttl_lines: List[str] = []
# for prefix, uri in prefixes.items():
#     ttl_lines.append(f"@prefix {prefix}: <{uri}> .")
# ttl_lines.append("")
# for s, p, o, lit in triples:
#     s_str = f"<{s}>" if s.startswith("urn:") else s
#     p_str = p
#     if lit:
#         o_str = f"\"{_ttl_escape_literal(o)}\""
#     else:
#         o_str = f"<{o}>" if o.startswith("urn:") else o
#     ttl_lines.append(f"{s_str} {p_str} {o_str} .")

# rdf_turtle = "\n".join(ttl_lines)
# print(rdf_turtle)

# if dot_mode:
#     print(dag_object.to_dot())
# else:
#     _deps = dag_object.to_graphlib_dependencies(
#         predicates={"ontobdc:target", "ontobdc:hasParameter", "ontobdc:hasInput", "ontobdc:hasOutput"}
#     )
#     topological_order = list(TopologicalSorter(_deps).static_order())
#     print(dag_object.to_turtle())
