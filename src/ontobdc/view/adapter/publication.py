from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
    StoragePathStatHelper,
)
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
)
from ontobdc.storage.plugin.check.is_container_datapackage_frictionless_valid.hotfix import (
    main as hotfix_container_datapackage_frictionless_valid,
)
from ontobdc.storage.plugin.check.is_container_datapackage_ro_crate_synced.hotfix import (
    main as hotfix_container_datapackage_ro_crate_synced,
)

StorageNamespaceBootstrap.initialize()
_OBDC = StorageNamespaceBootstrap.OBDC
_CT = StorageNamespaceBootstrap.CT

VIEW_DATA_DIRECTORY = "view"
VIEW_DATA_FILE = "data.json"
GENERATED_INDEX_FILE = "index.html"
VIEW_SCHEMA_VERSION = 1
_SOURCE_FINGERPRINT_META = "ontobdc-source-fingerprint"
_OPTIONS_FINGERPRINT_META = "ontobdc-options-fingerprint"


def resolve_container_path(context: CliContextPort) -> Path:
    value = context.get_parameter_value("container_path")
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("The container path was not resolved.")
    container_path = Path(normalized).expanduser().resolve()
    if not container_path.is_dir():
        raise ValueError(
            f"Container path is not an accessible directory: {container_path}"
        )
    return container_path


def resolve_view_options(context: CliContextPort) -> Dict[str, str]:
    view_type = str(
        context.get_parameter_value("view_type") or "standard"
    ).strip().lower()
    representation = str(
        context.get_parameter_value("representation") or "html"
    ).strip().lower()
    language = str(
        context.get_parameter_value("language") or "en"
    ).strip().lower()

    if view_type != "standard":
        raise ValueError(
            f"Unsupported container view type: {view_type}. "
            "Supported value: standard."
        )
    if representation != "html":
        raise ValueError(
            "The container view command currently supports HTML only."
        )
    if not language:
        language = "en"

    return {
        "view_type": view_type,
        "representation": representation,
        "language": language,
    }


def ensure_publishable(context: CliContextPort) -> Dict[str, Any]:
    container_path = resolve_container_path(context)
    metadata = _container_metadata(container_path)
    sync_result = ContainerDataPackageSynchronizer().sync(container_path)

    # sync() is blind to format on purpose, so re-running it here would undo
    # container_healthy's frictionless pruning. Re-apply both hotfixes so
    # this stays consistent with the same "compatible files already in the
    # RO-Crate" definition instead of drifting back to "every local file".
    root_path = str(context.root_path)
    hotfix_container_datapackage_frictionless_valid(
        container_path=str(container_path),
        root_path=root_path,
    )
    hotfix_container_datapackage_ro_crate_synced(
        container_path=str(container_path),
        root_path=root_path,
    )

    return {
        "container_path": str(container_path),
        "container_id": metadata["id"],
        "datapackage_path": str(sync_result.datapackage_path),
        "resource_count": sync_result.resource_count,
        "local_resource_count": sync_result.local_resource_count,
        "added_resource_count": sync_result.added_resource_count,
        "updated_resource_count": sync_result.updated_resource_count,
        "removed_resource_count": sync_result.removed_resource_count,
    }


def is_publishable(context: CliContextPort) -> bool:
    try:
        container_path = resolve_container_path(context)
        _container_metadata(container_path)
        descriptor = _load_datapackage(container_path)
        expected_paths = set(
            ContainerDataPackageSynchronizer.list_resource_paths(container_path)
        )
        described_paths = set(
            _descriptor_local_paths(container_path, descriptor)
        )
        return expected_paths == described_paths
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def gather_view_data(context: CliContextPort) -> Dict[str, Any]:
    container_path = resolve_container_path(context)
    options = resolve_view_options(context)
    if not is_publishable(context):
        ensure_publishable(context)

    source_fingerprint = calculate_source_fingerprint(container_path)
    options_fingerprint = calculate_options_fingerprint(options)
    metadata = _container_metadata(container_path)
    resources = _resource_records(container_path)

    payload: Dict[str, Any] = {
        "schema_version": VIEW_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_fingerprint": source_fingerprint,
        "options_fingerprint": options_fingerprint,
        "options": options,
        "container": metadata,
        "summary": {
            "indexed_files": len(resources),
            "total_bytes": sum(int(item["bytes"]) for item in resources),
        },
        "resources": resources,
    }

    data_path = view_data_path(container_path)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        data_path,
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return payload


def is_data_gathered(context: CliContextPort) -> bool:
    try:
        container_path = resolve_container_path(context)
        options = resolve_view_options(context)
        payload = _load_view_data(container_path)
        return (
            payload.get("schema_version") == VIEW_SCHEMA_VERSION
            and payload.get("source_fingerprint")
            == calculate_source_fingerprint(container_path)
            and payload.get("options_fingerprint")
            == calculate_options_fingerprint(options)
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def generate_container_view(context: CliContextPort) -> Dict[str, Any]:
    container_path = resolve_container_path(context)
    if not is_data_gathered(context):
        payload = gather_view_data(context)
    else:
        payload = _load_view_data(container_path)

    index_path = container_path / GENERATED_INDEX_FILE
    _atomic_write_text(index_path, _render_html(payload))
    ContainerDataPackageSynchronizer().sync(container_path)

    return {
        "container_path": str(container_path),
        "index_path": str(index_path),
        "index_uri": index_path.as_uri(),
        "indexed_files": payload["summary"]["indexed_files"],
        "source_fingerprint": payload["source_fingerprint"],
        "options_fingerprint": payload["options_fingerprint"],
    }


def is_generated(context: CliContextPort) -> bool:
    try:
        container_path = resolve_container_path(context)
        options = resolve_view_options(context)
        index_path = container_path / GENERATED_INDEX_FILE
        if not index_path.is_file():
            return False

        source_fingerprint = calculate_source_fingerprint(container_path)
        options_fingerprint = calculate_options_fingerprint(options)
        document = index_path.read_text(encoding="utf-8")
        return (
            _meta_value(document, _SOURCE_FINGERPRINT_META)
            == source_fingerprint
            and _meta_value(document, _OPTIONS_FINGERPRINT_META)
            == options_fingerprint
            and is_data_gathered(context)
        )
    except (OSError, TypeError, ValueError):
        return False


def view_data_path(container_path: Path) -> Path:
    return (
        container_path
        / ".__ontobdc__"
        / VIEW_DATA_DIRECTORY
        / VIEW_DATA_FILE
    )


def calculate_source_fingerprint(container_path: Path) -> str:
    resolved = container_path.expanduser().resolve()
    digest = hashlib.sha256()

    metadata_path = StorageBootstrap.get_container_storage_file_path(resolved)
    if not metadata_path.is_file():
        raise ValueError(f"Container metadata not found: {metadata_path}")
    _update_file_digest(
        digest,
        metadata_path,
        ".__ontobdc__/container.ttl",
    )

    for relative_path in ContainerDataPackageSynchronizer.list_resource_paths(resolved):
        if relative_path == GENERATED_INDEX_FILE:
            continue
        _update_file_digest(
            digest,
            resolved / relative_path,
            relative_path,
        )

    return digest.hexdigest()


def calculate_options_fingerprint(options: Dict[str, str]) -> str:
    serialized = json.dumps(
        options,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _update_file_digest(
    digest: Any,
    file_path: Path,
    relative_path: str,
) -> None:
    safe_path: Path = StorageBootstrap.to_extended_length_path(file_path)
    stat_result: Any = StoragePathStatHelper.safe_stat(safe_path)
    if stat_result is None:
        raise ValueError(f"Cannot stat resource for fingerprint: {file_path}")

    size: int = int(stat_result.st_size)
    mtime_ns: int = int(stat_result.st_mtime_ns)
    ino: int = int(getattr(stat_result, "st_ino", 0))
    dev: int = int(getattr(stat_result, "st_dev", 0))
    nlink: int = int(getattr(stat_result, "st_nlink", 0))
    mode: int = int(getattr(stat_result, "st_mode", 0))
    uid: int = int(getattr(stat_result, "st_uid", 0))
    gid: int = int(getattr(stat_result, "st_gid", 0))

    digest.update(relative_path.encode("utf-8"))
    digest.update(b"\0")
    digest.update(
        struct.pack(
            "<QQQQQQQ",
            size & 0xFFFFFFFFFFFFFFFF,
            mtime_ns & 0xFFFFFFFFFFFFFFFF,
            ino & 0xFFFFFFFFFFFFFFFF,
            dev & 0xFFFFFFFFFFFFFFFF,
            nlink & 0xFFFFFFFFFFFFFFFF,
            mode & 0xFFFFFFFFFFFFFFFF,
            (uid << 32 | (gid & 0xFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF,
        )
    )
    digest.update(b"\0")


def _container_metadata(container_path: Path) -> Dict[str, str]:
    metadata_path = StorageBootstrap.get_container_storage_file_path(container_path)
    if not metadata_path.is_file():
        raise ValueError(f"Container metadata not found: {metadata_path}")

    graph = Graph()
    try:
        graph.parse(str(metadata_path), format="turtle")
    except Exception as exc:
        raise ValueError(
            f"Invalid container metadata: {metadata_path}"
        ) from exc

    subjects = [
        subject
        for subject in graph.subjects(RDF.type, _OBDC.DataContainer)
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        raise ValueError(
            "Container metadata must describe exactly one DataContainer: "
            f"{metadata_path}"
        )

    subject = subjects[0]
    title = (
        _graph_text(graph, subject, DCTERMS.title)
        or container_path.name
    )
    description = _graph_text(graph, subject, _CT.description)
    location = (
        _graph_text(graph, subject, PROV.atLocation)
        or container_path.as_uri()
    )
    identifier = (
        _graph_text(graph, subject, DCTERMS.identifier)
        or str(subject)
    )

    return {
        "id": identifier,
        "uri": str(subject),
        "name": title,
        "description": description,
        "path": str(container_path),
        "location": location,
    }


def _graph_text(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
) -> str:
    value = graph.value(subject, predicate)
    return str(value).strip() if value is not None else ""


def _load_datapackage(container_path: Path) -> Dict[str, Any]:
    datapackage_path = (
        container_path / ".__ontobdc__" / "datapackage.json"
    )
    if not datapackage_path.is_file():
        raise ValueError(
            f"Container datapackage not found: {datapackage_path}"
        )
    loaded = json.loads(datapackage_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(
            f"Invalid container datapackage: {datapackage_path}"
        )
    resources = loaded.get("resources", [])
    if not isinstance(resources, list):
        raise ValueError(
            "Container datapackage resources must be a list."
        )
    return loaded


def _descriptor_local_paths(
    container_path: Path,
    descriptor: Dict[str, Any],
) -> Iterable[str]:
    metadata_dir = container_path / ".__ontobdc__"
    for item in descriptor.get("resources", []):
        if not isinstance(item, dict):
            continue
        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        candidate = Path(path_value)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (metadata_dir / candidate).resolve()
        try:
            yield resolved.relative_to(container_path).as_posix()
        except ValueError:
            continue


def _resource_records(container_path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for relative_path in ContainerDataPackageSynchronizer.list_resource_paths(container_path):
        if relative_path == GENERATED_INDEX_FILE:
            continue
        file_path = container_path / relative_path
        media_type, _ = mimetypes.guess_type(file_path.name)
        records.append(
            {
                "path": relative_path,
                "name": file_path.name,
                "extension": file_path.suffix.lower(),
                "media_type": (
                    media_type or "application/octet-stream"
                ),
                "bytes": StorageBootstrap.to_extended_length_path(file_path).stat().st_size,
            }
        )
    return records


def _load_view_data(container_path: Path) -> Dict[str, Any]:
    data_path = view_data_path(container_path)
    if not data_path.is_file():
        raise ValueError(f"View data not found: {data_path}")
    loaded = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid view data: {data_path}")
    return loaded


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _meta_value(document: str, name: str) -> str:
    pattern = re.compile(
        rf'<meta\s+name="{re.escape(name)}"\s+'
        r'content="([^"]*)"\s*/?>',
        re.IGNORECASE,
    )
    match = pattern.search(document)
    return html.unescape(match.group(1)) if match else ""


def _render_html(payload: Dict[str, Any]) -> str:
    container = payload["container"]
    summary = payload["summary"]
    resources = payload["resources"]
    language = str(payload["options"]["language"] or "en")
    source_fingerprint = html.escape(
        payload["source_fingerprint"],
        quote=True,
    )
    options_fingerprint = html.escape(
        payload["options_fingerprint"],
        quote=True,
    )

    rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td><code>{html.escape(str(item['path']))}</code></td>"
            f"<td>{html.escape(str(item['media_type']))}</td>"
            f'<td class="number">{int(item["bytes"]):,}</td>'
            "</tr>"
        )
        for item in resources
    )
    if not rows:
        rows = (
            '<tr><td colspan="4" class="empty">'
            "No indexed files.</td></tr>"
        )

    title = html.escape(str(container["name"]))
    description = html.escape(
        str(container.get("description") or "")
    )
    container_id = html.escape(str(container["id"]))
    path = html.escape(str(container["path"]))
    generated_at = html.escape(str(payload["generated_at"]))

    return f'''<!doctype html>
<html lang="{html.escape(language, quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="{_SOURCE_FINGERPRINT_META}" content="{source_fingerprint}">
  <meta name="{_OPTIONS_FINGERPRINT_META}" content="{options_fingerprint}">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07101d;
      --surface: #0f1a2c;
      --surface-2: #131f33;
      --line: #2b3950;
      --text: #eef4ff;
      --muted: #9fb0c8;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-width: 0;
      background: var(--bg);
      color: var(--text);
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: clamp(16px, 3vw, 40px);
    }}
    .hero, .panel, .metric {{
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--surface);
    }}
    .hero {{ padding: clamp(22px, 4vw, 48px); }}
    .eyebrow {{
      color: var(--accent);
      font-size: .78rem;
      font-weight: 800;
      letter-spacing: .1em;
      text-transform: uppercase;
    }}
    h1 {{
      max-width: 20ch;
      margin: .35em 0 .2em;
      font-size: clamp(2.2rem, 7vw, 5.8rem);
      line-height: .95;
      overflow-wrap: anywhere;
    }}
    .description {{ max-width: 75ch; color: var(--muted); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin: 18px 0;
    }}
    .metric {{
      grid-column: span 4;
      min-width: 0;
      padding: 22px;
    }}
    .metric strong {{
      display: block;
      margin-top: 8px;
      font-size: clamp(2.2rem, 5vw, 4rem);
      line-height: 1;
    }}
    .metric span {{ color: var(--muted); }}
    .panel {{ overflow: hidden; }}
    .metadata {{
      display: grid;
      grid-template-columns: minmax(120px, 1fr) minmax(0, 4fr);
      gap: 0;
      margin: 0;
    }}
    .metadata dt, .metadata dd {{
      min-width: 0;
      margin: 0;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      overflow-wrap: anywhere;
    }}
    .metadata dt {{ color: var(--accent); font-weight: 700; }}
    .table-wrap {{ width: 100%; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
    th, td {{
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--accent); background: var(--surface-2); }}
    code {{ color: var(--muted); overflow-wrap: anywhere; }}
    .number {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .empty {{ color: var(--muted); text-align: center; }}
    .section-title {{
      margin: 0;
      padding: 20px 18px;
      font-size: 1.15rem;
    }}
    footer {{
      padding: 18px 2px 0;
      color: var(--muted);
      font-size: .85rem;
    }}
    @media (max-width: 900px) {{
      .metric {{ grid-column: span 6; }}
    }}
    @media (max-width: 620px) {{
      .metric {{ grid-column: 1 / -1; }}
      .metadata {{ grid-template-columns: 1fr; }}
      .metadata dt {{ padding-bottom: 3px; border-bottom: 0; }}
      .metadata dd {{ padding-top: 3px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <div class="eyebrow">OntoBDC container view</div>
      <h1>{title}</h1>
      <p class="description">{description}</p>
    </header>

    <section class="metrics" aria-label="Container summary">
      <article class="metric">
        <span>Indexed files</span>
        <strong>{int(summary["indexed_files"])}</strong>
      </article>
      <article class="metric">
        <span>Total bytes</span>
        <strong>{int(summary["total_bytes"]):,}</strong>
      </article>
    </section>

    <section class="panel">
      <h2 class="section-title">Container information</h2>
      <dl class="metadata">
        <dt>ID</dt><dd><code>{container_id}</code></dd>
        <dt>Path</dt><dd><code>{path}</code></dd>
        <dt>Generated</dt><dd>{generated_at}</dd>
      </dl>
    </section>

    <section class="panel" style="margin-top:18px">
      <h2 class="section-title">Files</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Path</th>
              <th>Media type</th>
              <th class="number">Bytes</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>

    <footer>Generated locally by OntoBDC.</footer>
  </main>
</body>
</html>
'''
