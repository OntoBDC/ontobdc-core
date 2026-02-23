#!/usr/bin/env python3
import sys
import os
import argparse
from rich.console import Console

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from ontobdc.run.capability_core import CapabilityRegistry
from ontobdc.resource.src.domain.port.repository import FileRepositoryPort
from ontobdc.resource.plugin.capability.list_documents import ListDocumentsCapability
from ontobdc.resource.plugin.capability.list_documents_by_type import ListDocumentsByTypeCapability
from ontobdc.resource.plugin.capability.list_documents_by_template import ListDocumentsByTemplateCapability
from ontobdc.resource.plugin.capability.list_documents_by_name_pattern import (
    ListDocumentsByNamePatternCapability,
)
from ontobdc.resource.plugin.capability.list_documents_by_bbox import ListDocumentsByBboxCapability


class SimpleMenuSelector:
    def __init__(self, console: Console) -> None:
        self.console = console

    def select_option(self, options, title: str = "Select an option"):
        self.console.print(f"[bold]{title}[/bold]")
        for idx, opt in enumerate(options, start=1):
            label = opt.get("label", "")
            self.console.print(f"  [cyan]{idx}[/cyan]] {label}")
        self.console.print("  [cyan]0[/cyan]] Cancel")
        while True:
            choice = input("Enter choice: ").strip()
            if not choice.isdigit():
                continue
            index = int(choice)
            if index == 0:
                return None
            if 1 <= index <= len(options):
                return options[index - 1].get("value")


CapabilityRegistry.register_many(
    [
        ListDocumentsCapability,
        ListDocumentsByTypeCapability,
        ListDocumentsByTemplateCapability,
        ListDocumentsByNamePatternCapability,
        ListDocumentsByBboxCapability,
    ]
)


def main():
    class SimpleFileRepository(FileRepositoryPort):
        def __init__(self, root: str) -> None:
            self._root = root
        @property
        def filesystem(self):
            return None
        @property
        def path_folders(self):
            return []
        def get_by_name(self, name):
            return []
        def get_by_mimetype(self, mimetype):
            return []
        def get_by_media_types(self, media_types):
            return []
        def iter_file_paths(self):
            for root, _, filenames in os.walk(self._root):
                for filename in filenames:
                    yield os.path.join(root, filename)
        def get_by_id(self, id):
            return []
        def get_all(self):
            return list(self.iter_file_paths())
        def get_by_type(self, type):
            return []
    simple_repo = SimpleFileRepository(os.getcwd())

    if "--json" in sys.argv:
        import json

        catalog = []
        for cid, cls in CapabilityRegistry.get_all().items():
            meta = cls.METADATA
            meta_dict = meta.__dict__.copy()
            catalog.append(meta_dict)
        print(json.dumps(catalog, indent=2, default=str))
        sys.exit(0)

    if "-h" in sys.argv or "--help" in sys.argv:
        if len(sys.argv) == 2:
            print("Usage: infobim run <capability_id> [args...]")
            print("\nAvailable capabilities:")
            for key in CapabilityRegistry.get_all().keys():
                print(f"  - {key}")
            sys.exit(0)

    outer_parser = argparse.ArgumentParser(add_help=False)
    outer_parser.add_argument(
        "--export",
        choices=["rich", "json"],
        help="Output format",
        default=None,
    )
    outer_parser.add_argument("capability_id", nargs="?", help="ID of the capability to run")

    parsed_args, remaining_args = outer_parser.parse_known_args(sys.argv[1:])
    global_export_format = parsed_args.export

    capability_id = parsed_args.capability_id
    if capability_id is None:
        console = Console()
        selector = SimpleMenuSelector(console=console)
        options = []
        for cid, cls in CapabilityRegistry.get_all().items():
            meta = getattr(cls, "METADATA", None)
            if not meta:
                continue
            name = getattr(meta, "name", cid)
            options.append({"label": f"{name}", "value": cid})

        if not options:
            console.print("[bold red]No capabilities available for this mode.[/bold red]")
            sys.exit(1)

        selected = selector.select_option(options, title="Select a Capability")
        if not selected:
            sys.exit(0)
        capability_id = selected

    sys.argv = [sys.argv[0], capability_id] + remaining_args

    cap_class = CapabilityRegistry.get(capability_id)
    if not cap_class:
        console = Console()
        console.print(f"[bold red]Error:[/bold red] Capability '{capability_id}' not found.")
        console.print("\n[dim]Available capabilities:[/dim]")
        for key in CapabilityRegistry.get_all().keys():
            console.print(f"  - [cyan]{key}[/cyan]")
        sys.exit(1)

    cap = cap_class()
    strategy = cap.get_default_cli_strategy(repository=simple_repo)

    if not strategy:
        print(f"The capability '{cap.metadata.name}' does not support CLI execution.")
        sys.exit(1)

    real_parser = argparse.ArgumentParser(
        description=f"Run {cap.metadata.name}",
        fromfile_prefix_chars="@",
    )
    real_parser.add_argument("capability_id", help="ID of the capability to run")
    real_parser.add_argument(
        "--export",
        choices=["rich", "json"],
        default="rich",
        help="Output format",
    )

    strategy.setup_parser(real_parser)

    if global_export_format:
        for action in real_parser._actions:
            if action.dest == "export":
                action.default = global_export_format

    final_args = real_parser.parse_args()

    console = Console()
    strategy.run(console, final_args, cap)


if __name__ == "__main__":
    main()
