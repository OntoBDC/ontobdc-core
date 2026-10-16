import re
from pathlib import Path
from typing import Iterator, Optional


OLD_NAMESPACE: bytes = b"http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#"
# Consume literals and comments together with IRIs so their text is untouched.
_TURTLE_TOKENS: re.Pattern[bytes] = re.compile(
    rb'"""(?:\\.|(?!""").)*"""'
    rb"|'''(?:\\.|(?!''').)*'''"
    rb'|"(?:\\.|[^"\\])*"'
    rb"|'(?:\\.|[^'\\])*'"
    rb"|\\."
    rb"|#[^\r\n]*"
    rb"|<[^>]*>",
    re.DOTALL,
)


def _uses_old_namespace(content: bytes) -> bool:
    return OLD_NAMESPACE in content and any(
        match.group().startswith(b"<" + OLD_NAMESPACE)
        for match in _TURTLE_TOKENS.finditer(content)
    )


def _ttl_files(container_path: Path) -> Iterator[Path]:
    """Limit migration to container metadata and immediate dataset children."""
    metadata: Path = container_path / ".__ontobdc__"
    if metadata.is_symlink():
        raise ValueError(f"Namespace migration cannot traverse a symlink: {metadata}")
    for path in sorted(metadata.glob("*.ttl")):
        if path.is_file() and not path.is_symlink():
            yield path

    for dataset in sorted(container_path.iterdir()):
        if not dataset.is_dir() or dataset.is_symlink():
            continue
        dataset_metadata: Path = dataset / ".__ontobdc__" / "dataset.ttl"
        if not dataset_metadata.is_file():
            continue
        if dataset_metadata.parent.is_symlink() or dataset_metadata.is_symlink():
            raise ValueError(f"Namespace migration cannot traverse a symlink: {dataset_metadata}")
        yield dataset_metadata
        triples: Path = dataset / "payload" / "triple"
        if (dataset / "payload").is_symlink() or triples.is_symlink():
            raise ValueError(f"Namespace migration cannot traverse a symlink: {triples}")
        for path in sorted(triples.glob("*.ttl")):
            if path.is_file() and not path.is_symlink():
                yield path


def main(container_path: Optional[str] = None) -> int:
    """Return 0 when the scoped Turtle files no longer use the old core IRI."""
    if not isinstance(container_path, str) or not container_path.strip():
        return 1
    resolved: Path = Path(container_path).expanduser().resolve()
    if not (resolved / ".__ontobdc__" / "container.ttl").is_file():
        return 1
    return 1 if any(_uses_old_namespace(path.read_bytes()) for path in _ttl_files(resolved)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
