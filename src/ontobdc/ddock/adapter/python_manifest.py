import json
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from ontobdc.ddock.domain.model.system_descriptor import PythonDependency


class PythonManifest:
    """
    The ``python/manifest.json`` of the source folder: what the runtime of the
    browser is made of. Its ``wheels`` are the pure-Python packages pinned from
    PyPI (``name==version``); the Python dependencies of ``system.obdc`` are
    put there, so that the browser has what the system asks for.

    A dependency the manifest gets from elsewhere (a package built for Pyodide,
    or one built from local source) is left to it, and one with no version has
    no pin to write. The text of the file is kept as it is; only the lines of
    ``wheels`` change.
    """

    BLOCK: ClassVar["re.Pattern[str]"] = re.compile(r'("wheels"\s*:\s*\[\n)(?P<body>.*?)(\n\s*\])', re.DOTALL)
    ENTRY: ClassVar["re.Pattern[str]"] = re.compile(r'^(?P<indent>\s*)"(?P<spec>[^"]+)"\s*,?\s*$')

    @staticmethod
    def normalize(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name.strip().lower())

    @classmethod
    def pins(cls, manifest: Path, dependencies: List[PythonDependency]) -> Dict[str, str]:
        """
        The pins ``system.obdc`` asks for that the manifest takes from PyPI,
        by normalized name (``{"infobim": "infobim==0.15.0"}``).
        """
        data: Dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
        elsewhere: Set[str] = {cls.normalize(name) for name in data.get("pyodidePackages", [])}
        elsewhere |= {cls.normalize(source["name"]) for source in data.get("localSources", [])}
        elsewhere |= {cls.normalize(str(wheel.get("pypi", "")).split("==")[0]) for wheel in data.get("localWheels", [])}

        pins: Dict[str, str] = {}
        dependency: PythonDependency
        for dependency in dependencies:
            key: str = cls.normalize(dependency.name)
            if dependency.version and key not in elsewhere:
                pins[key] = f"{dependency.name.strip()}=={dependency.version}"

        return pins

    @classmethod
    def is_updated(cls, manifest: Path, dependencies: List[PythonDependency]) -> bool:
        """
        Whether the wheels of the manifest already have every pin.
        """
        present: Set[str] = set(cls._wheels(manifest.read_text(encoding="utf-8"))[0])
        return all(pin in present for pin in cls.pins(manifest, dependencies).values())

    @classmethod
    def update(cls, manifest: Path, dependencies: List[PythonDependency]) -> List[str]:
        """
        Put every pin in the wheels of the manifest: the one the manifest has
        for the package is replaced in its place, and a package it does not
        have goes where its name falls in the order. Returns the pins that
        changed the file.
        """
        text: str = manifest.read_text(encoding="utf-8")
        specs: List[str]
        indent: str
        specs, indent = cls._wheels(text)
        changed: List[str] = []
        key: str
        pin: str
        for key, pin in cls.pins(manifest, dependencies).items():
            position: Optional[int] = next((i for i, spec in enumerate(specs) if cls.normalize(spec.split("==")[0]) == key), None)
            if position is not None:
                if specs[position] != pin:
                    specs[position] = pin
                    changed.append(pin)
                continue

            after: int = next((i for i, spec in enumerate(specs) if cls.normalize(spec.split("==")[0]) > key), len(specs))
            specs.insert(after, pin)
            changed.append(pin)

        if changed:
            body: str = ",\n".join(f'{indent}"{spec}"' for spec in specs)
            manifest.write_text(cls.BLOCK.sub(lambda match: f"{match.group(1)}{body}{match.group(3)}", text, count=1), encoding="utf-8")

        return changed

    @classmethod
    def _wheels(cls, text: str) -> Tuple[List[str], str]:
        match: Optional["re.Match[str]"] = cls.BLOCK.search(text)
        if match is None:
            raise ValueError("The manifest has no 'wheels' list.")

        specs: List[str] = []
        indent: str = "    "
        line: str
        for line in match.group("body").split("\n"):
            entry: Optional["re.Match[str]"] = cls.ENTRY.match(line)
            if entry is None:
                continue
            indent = entry.group("indent")
            specs.append(entry.group("spec"))

        return specs, indent
