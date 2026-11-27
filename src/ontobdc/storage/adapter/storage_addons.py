import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List
from urllib.parse import urlparse

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.repository import LoadedStorageGraph, StorageGraphFileRepository


class StorageAddons:
    """
    The addons installed in a storage: each is a copy of the folder of the addon in the ``addon`` folder of the root of
    the storage (not of a container), and is modeled in the ``storage.ttl`` of that root. The addon is known by the name
    of its folder; it is installed once, so one that the ``storage.ttl`` already has is not copied again.
    """

    FOLDER: ClassVar[str] = "addon"
    IGNORED: ClassVar[List[str]] = [".git", "__pycache__", "node_modules"]

    @classmethod
    def iri(cls, name: str) -> URIRef:
        """The IRI of the addon the folder of that name is."""
        return URIRef(f"urn:ontobdc:addon/{name}")

    @classmethod
    def modeled(cls, storage_file: Path, name: str) -> bool:
        """Whether the ``storage.ttl`` models an addon with that name."""
        return (cls.iri(name), RDF.type, OBDC.Addon) in LoadedStorageGraph(storage_file).graph

    @classmethod
    def installed(cls, storage_file: Path) -> List[Path]:
        """
        The folders of the addons installed in the storage, by name: the ones the ``storage.ttl`` models, each in the
        ``addon`` folder of the root.

        Raises:
            FileNotFoundError: the storage models an addon whose folder is not there.
        """
        loaded: LoadedStorageGraph = LoadedStorageGraph(storage_file)
        root: Path = StorageGraphFileRepository(storage_file).root_path
        names: List[str] = sorted(str(name) for subject in loaded.graph.subjects(RDF.type, OBDC.Addon) for name in loaded.graph.objects(subject, DCTERMS.identifier))
        folders: List[Path] = []
        name: str
        for name in names:
            folder: Path = root / cls.FOLDER / cls._checked(name)
            if not folder.is_dir():
                raise FileNotFoundError(
                    f"The storage {storage_file} says the addon {name} is installed, but {folder} is not there: install it "
                    "again with `ontobdc init --addon <folder or address>`."
                )
            folders.append(folder)

        return folders

    @classmethod
    def _checked(cls, name: str) -> str:
        """The name, when it is the name of a folder of the ``addon`` folder."""
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError(f"The name of the addon '{name}' is not usable as the name of a folder of the storage.")

        return name

    @classmethod
    def install(cls, storage_file: Path, folder: Path, source: str) -> Dict[str, Any]:
        """
        Installs the addon in the ``addon`` folder of the root of the storage, and models it in the ``storage.ttl`` when
        the storage does not yet. What it does depends on what the storage and the folder have:

        - the storage models the addon and the folder is there: it is installed, nothing is done (``already``);
        - the storage models the addon and the folder is not there: the folder is copied (``restored``);
        - the storage does not model the addon and there is a folder of that name: the folder is removed first, then the
          new one is copied and the addon is modeled (``replaced``);
        - neither: the folder is copied and the addon is modeled (``installed``).

        Raises:
            ValueError: the name of the addon is not the name of a folder.
        """
        name: str = cls._checked(folder.name)
        root: Path = StorageGraphFileRepository(storage_file).root_path
        target: Path = root / cls.FOLDER / name
        modeled: bool = cls.modeled(storage_file, name)
        if modeled and target.is_dir():
            return {"addon": str(target), "name": name, "installed": False, "action": "already"}

        replaced: bool = target.exists()
        if replaced:
            shutil.rmtree(target) if target.is_dir() else target.unlink()

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(folder, target, ignore=shutil.ignore_patterns(*cls.IGNORED))
        if not modeled:
            cls._model(storage_file, name, target.relative_to(root).as_posix(), source)

        action: str = "restored" if modeled else ("replaced" if replaced else "installed")
        return {"addon": str(target), "name": name, "installed": True, "action": action}

    @classmethod
    def _model(cls, storage_file: Path, name: str, relative_location: str, source: str) -> None:
        """Writes in the ``storage.ttl`` that the storage has the addon, where it is in it and where it came from."""
        loaded: LoadedStorageGraph = LoadedStorageGraph(storage_file)
        graph: Graph = loaded.graph
        storages: List[Any] = list(graph.subjects(RDF.type, OBDC.DataStorage))
        if len(storages) != 1:
            raise ValueError(f"The storage {storage_file} has {len(storages)} storages, expected exactly one.")

        subject: URIRef = cls.iri(name)
        moment: str = datetime.now(timezone.utc).isoformat()
        graph.add((storages[0], OBDC.hasAddon, subject))
        graph.add((subject, RDF.type, OBDC.Addon))
        graph.add((subject, DCTERMS.identifier, Literal(name)))
        graph.add((subject, DCTERMS.title, Literal(name)))
        graph.add((subject, OBDC.relativeLocation, Literal(relative_location)))
        graph.add((subject, DCTERMS.source, cls._source(source)))
        graph.add((subject, DCTERMS.created, Literal(moment, datatype=XSD.dateTime)))
        StorageGraphFileRepository(storage_file).save(loaded.storage_graph)

    @staticmethod
    def _source(source: str) -> URIRef:
        """Where the addon came from: the address, or the ``file`` URI of the folder."""
        if urlparse(source).scheme:
            return URIRef(source)

        return URIRef(Path(source).expanduser().resolve().as_uri())
