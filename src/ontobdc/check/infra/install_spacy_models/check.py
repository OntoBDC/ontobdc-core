import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Iterable


LANGUAGE_TO_MODEL = {
    "en": "en_core_web_md",
    "pt": "pt_core_news_md",
    "pt_BR": "pt_core_news_md",
}


def get_all_capabilities() -> list[type]:
    capabilities: list[type] = []

    for package_name in _list_capability_packages():
        try:
            package = importlib.import_module(package_name)
        except Exception:
            continue

        package_path = getattr(package, "__path__", None)
        if package_path is None:
            continue

        for _, module_name, _ in pkgutil.walk_packages(package_path, package.__name__ + "."):
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            for _, obj in inspect.getmembers(module):
                if not inspect.isclass(obj):
                    continue
                metadata = getattr(obj, "METADATA", None)
                metadata_id = getattr(metadata, "id", None)
                if isinstance(metadata_id, str) and metadata_id.strip():
                    capabilities.append(obj)

    return capabilities


def _list_capability_packages() -> list[str]:
    discovered_packages: list[str] = []
    ontobdc_root: Path = Path(__file__).resolve().parents[3]

    def _scan_directory(base_dir: Path, base_package: str) -> None:
        try:
            for entry in sorted(base_dir.iterdir()):
                if entry.name.startswith(".") or entry.name.startswith("_") or entry.name == "__pycache__":
                    continue
                if not entry.is_dir():
                    continue

                plugin_dir: Path = entry / "plugin"
                capability_dir: Path = plugin_dir / "capability"
                if capability_dir.is_dir():
                    discovered_packages.append(f"{base_package}.{entry.name}.plugin.capability")
        except Exception:
            return

    _scan_directory(ontobdc_root, "ontobdc")

    module_dir: Path = ontobdc_root / "module"
    if module_dir.is_dir():
        _scan_directory(module_dir, "ontobdc.module")

    return discovered_packages


def get_supported_languages() -> set[str]:
    supported_languages: set[str] = set()

    for capability in get_all_capabilities():
        metadata = getattr(capability, "METADATA", None)
        languages = getattr(metadata, "supported_languages", [])
        supported_languages.update(languages)

    return supported_languages


def get_required_models() -> list[str]:
    models = {
        LANGUAGE_TO_MODEL[language]
        for language in get_supported_languages()
        if language in LANGUAGE_TO_MODEL
    }
    return sorted(models)


def get_missing_models() -> list[str]:
    try:
        import spacy
    except ImportError:
        return get_required_models()

    missing_models: list[str] = []
    for model_name in get_required_models():
        try:
            spacy.load(model_name)
        except OSError:
            missing_models.append(model_name)

    return missing_models


def print_lines(values: Iterable[str]) -> None:
    for value in values:
        print(value)


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"

    if command == "required-models":
        print_lines(get_required_models())
        return 0

    if command == "missing-models":
        print_lines(get_missing_models())
        return 0

    if command == "check":
        return 0 if not get_missing_models() else 1

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
