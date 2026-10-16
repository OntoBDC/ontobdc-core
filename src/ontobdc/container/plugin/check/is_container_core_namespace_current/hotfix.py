import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Optional

from rdflib import Graph

from ontobdc.container.plugin.check.is_container_core_namespace_current.check import (
    OLD_NAMESPACE,
    _TURTLE_TOKENS,
    _ttl_files,
    _uses_old_namespace,
    main as check_core_namespace,
)
from ontobdc.shared.domain.vocabulary import OBDC


def _replace_bytes(path: Path, content: bytes, mode: int) -> None:
    """Replace a complete file atomically without leaving a backup behind."""
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".core-namespace-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _migrate_file(path: Path) -> None:
    original_stat: os.stat_result = path.stat()
    original: bytes = path.read_bytes()
    if not _uses_old_namespace(original):
        return

    def replace_iri(match: re.Match[bytes]) -> bytes:
        token: bytes = match.group()
        if token.startswith(b"<" + OLD_NAMESPACE):
            return b"<" + str(OBDC).encode("utf-8") + token[1 + len(OLD_NAMESPACE):]
        return token

    updated: bytes = _TURTLE_TOKENS.sub(replace_iri, original)
    mode: int = stat.S_IMODE(original_stat.st_mode)
    _replace_bytes(path, updated, mode)
    try:
        Graph().parse(str(path), format="turtle")
    except Exception as error:
        _replace_bytes(path, original, mode)
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        raise ValueError(f"Invalid Turtle after core namespace migration; original restored: {path}") from error


def main(container_path: Optional[str] = None) -> int:
    """Migrate only the exact old core prefix before container resolution."""
    if not isinstance(container_path, str) or not container_path.strip():
        return 1
    resolved: Path = Path(container_path).expanduser().resolve()
    if not (resolved / ".__ontobdc__" / "container.ttl").is_file():
        return 1
    for path in _ttl_files(resolved):
        _migrate_file(path)
    return check_core_namespace(container_path=str(resolved))


if __name__ == "__main__":
    raise SystemExit(main())
