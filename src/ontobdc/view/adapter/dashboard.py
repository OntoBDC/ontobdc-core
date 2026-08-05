from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.view.adapter.publication import (
    calculate_options_fingerprint,
    calculate_source_fingerprint,
    gather_view_data,
    is_data_gathered,
    resolve_container_path,
    resolve_view_options,
)


_DASHBOARD_TEMPLATE_MARKER = "infobim-project-dashboard"
_SOURCE_FINGERPRINT_META = "ontobdc-source-fingerprint"
_OPTIONS_FINGERPRINT_META = "ontobdc-options-fingerprint"

_WEEKDAY_NAMES = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_BASE_CSS = r"""
:root {
  --bg: #09101d;
  --bg-soft: #111b2d;
  --surface: rgba(14, 22, 38, 0.88);
  --surface-strong: #172338;
  --line: rgba(148, 163, 184, 0.18);
  --text: #e5eefc;
  --text-soft: #97a7bf;
  --accent: #67e8f9;
  --accent-strong: #38bdf8;
  --shadow: 0 28px 70px rgba(0, 0, 0, 0.36);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: "Segoe UI", Arial, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 28%),
    radial-gradient(circle at bottom right, rgba(103, 232, 249, 0.12), transparent 22%),
    linear-gradient(180deg, #08101c 0%, #060b14 100%);
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.96), transparent);
}
.view-shell { position: relative; max-width: 1520px; margin: 0 auto; padding: 28px; }
.view-topbar {
  display: grid;
  grid-template-columns: minmax(0,1.4fr) minmax(320px,.8fr);
  gap: 20px;
  margin-bottom: 22px;
}
.view-topbar-primary { display: grid; gap: 14px; min-width: 0; }
.view-hero-card, .view-hero-meta, .view-panel {
  border: 1px solid var(--line);
  border-radius: 28px;
  background: var(--surface);
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
}
.view-hero-card { padding: 22px 24px 20px; }
.view-brand { display: flex; align-items: center; gap: 18px; }
.view-brand-logo {
  width: 84px;
  height: 84px;
  object-fit: contain;
  border-radius: 18px;
  background: rgba(255,255,255,.04);
  padding: 8px;
}
.view-brand-copy { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.view-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: fit-content;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(103,232,249,.12);
  color: var(--accent);
  font-size: .8rem;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.view-eyebrow::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.view-eyebrow-meta {
  color: rgba(229,238,252,.68);
  font-family: Consolas, "Courier New", monospace;
  font-size: .82rem;
  overflow-wrap: anywhere;
}
.view-topbar h1 {
  margin: 16px 0 10px;
  font-size: clamp(2.8rem,5vw,4.9rem);
  line-height: .92;
  letter-spacing: -.05em;
  overflow-wrap: anywhere;
}
.view-topbar p { max-width: 70ch; margin: 0; color: var(--text-soft); line-height: 1.6; }
.view-menubar-card {
  min-height: 28px;
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 24px;
  background: var(--surface);
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
}
.view-menubar-track {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  width: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
}
.menubar-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  padding: 5px 10px;
  border: 1px solid rgba(56,189,248,.14);
  border-radius: 999px;
  color: inherit;
  background: rgba(255,255,255,.03);
  font: inherit;
  cursor: pointer;
}
.menubar-item-label {
  color: var(--text-soft);
  font-size: .7rem;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.menubar-item-value { color: var(--text); font-size: .86rem; font-weight: 700; }
.view-hero-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  padding: 24px;
}
.view-hero-meta:empty { display: none; }
.view-badge {
  display: grid;
  align-content: space-between;
  min-width: 0;
  min-height: 132px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: rgba(255,255,255,.03);
}
.view-badge-label {
  color: var(--text-soft);
  font-size: .76rem;
  text-transform: uppercase;
  letter-spacing: .08em;
}
.view-badge-value {
  margin-top: 10px;
  font-size: 1.05rem;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.view-grid {
  display: grid;
  grid-template-columns: repeat(4,minmax(0,1fr));
  gap: 20px;
  align-items: start;
}
.view-column { display: grid; gap: 20px; min-width: 0; }
.view-panel { overflow: hidden; }
.view-panel-head { padding: 20px 22px 12px; border-bottom: 1px solid var(--line); }
.view-panel-title { margin: 0; font-size: 1.05rem; }
.view-panel-copy {
  margin: 8px 0 0;
  color: var(--text-soft);
  line-height: 1.6;
  font-size: .93rem;
}
.view-panel-copy-diamond { margin-right: 8px; color: var(--accent-strong); }
.view-panel-body { padding: 18px; }
.metadata-list { display: grid; gap: 12px; margin: 0; }
.metadata-row {
  display: grid;
  grid-template-columns: 148px minmax(0,1fr);
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255,255,255,.02);
}
.metadata-row dt { margin: 0; color: var(--accent-strong); font-weight: 700; }
.metadata-row dd { margin: 0; color: var(--text); overflow-wrap: anywhere; }
.runtime-status { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.runtime-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 6px rgba(245,158,11,.18);
}
.runtime-dot.is-ready {
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34,197,94,.18);
}
.runtime-dot.is-error {
  background: #fb7185;
  box-shadow: 0 0 0 6px rgba(251,113,133,.18);
}
.runtime-console {
  margin: 0;
  padding: 16px;
  border: 1px solid rgba(56,189,248,.14);
  border-radius: 18px;
  color: #dbeafe;
  background: #08111d;
  font-family: Consolas, "Courier New", monospace;
  font-size: .88rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
"""

_LAYOUT_CSS = r"""
.view-topbar, .view-grid { grid-template-columns: repeat(12, minmax(0, 1fr)); }
.view-topbar-primary { grid-column: span 8; min-width: 0; }
.view-hero-meta {
  grid-column: span 4;
  align-self: stretch;
  min-width: 0;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.view-topbar:has(.view-hero-meta:empty) .view-topbar-primary { grid-column: 1 / -1; }
.view-column-third { grid-column: span 4; }
.view-column-main { grid-column: span 8; }
.view-topbar > *, .view-grid > *, .metadata-row > * { min-width: 0; }
.project-tabs-card { min-height: 720px; }
.project-tabs-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 620px;
}
.project-tabs-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 12px 18px 0;
  overflow-x: auto;
  overflow-y: hidden;
  border-bottom: 1px solid var(--line);
  scrollbar-width: thin;
}
.project-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex: 0 0 auto;
  min-height: 48px;
  padding: 10px 14px 13px;
  border: 0;
  border-radius: 14px 14px 0 0;
  color: var(--text-soft);
  background: transparent;
  font: inherit;
  font-size: .88rem;
  font-weight: 800;
  cursor: pointer;
  transition: color 160ms ease, background 160ms ease;
}
.project-tab::after {
  content: "";
  position: absolute;
  right: 10px;
  bottom: -1px;
  left: 10px;
  height: 2px;
  border-radius: 999px;
  background: transparent;
}
.project-tab:hover { color: var(--text); background: rgba(255,255,255,.03); }
.project-tab:focus-visible { outline: 2px solid var(--accent-strong); outline-offset: -2px; }
.project-tab[aria-selected="true"] { color: var(--accent); background: rgba(103,232,249,.08); }
.project-tab[aria-selected="true"]::after {
  background: linear-gradient(90deg, var(--accent), var(--accent-strong));
}
.project-tab-icon { font-size: 1rem; line-height: 1; }
.project-tabs-content { min-width: 0; min-height: 0; }
.project-tab-panel { min-height: 540px; padding: 28px; }
.project-tab-panel[hidden] { display: none; }
.project-tab-empty {
  display: grid;
  align-content: center;
  justify-items: center;
  min-height: 470px;
  padding: 36px;
  border: 1px dashed rgba(103,232,249,.22);
  border-radius: 22px;
  background:
    radial-gradient(circle at center, rgba(103,232,249,.07), transparent 62%),
    rgba(255,255,255,.018);
  text-align: center;
}
.project-tab-empty-icon {
  display: grid;
  place-items: center;
  width: 68px;
  height: 68px;
  margin-bottom: 18px;
  border: 1px solid rgba(103,232,249,.22);
  border-radius: 20px;
  color: var(--accent);
  background: rgba(103,232,249,.08);
  font-size: 1.8rem;
}
.project-tab-empty h3 { margin: 0; color: var(--text); font-size: clamp(1.35rem,2vw,1.8rem); }
.project-tab-empty p { max-width: 58ch; margin: 10px 0 0; color: var(--text-soft); line-height: 1.7; }
@media (max-width: 1200px) {
  .view-column-third, .view-column-main { grid-column: span 6; }
  .view-topbar h1 { font-size: clamp(2.45rem,5vw,4.2rem); }
}
@media (max-width: 1050px) {
  .view-topbar-primary, .view-hero-meta, .view-column-third, .view-column-main {
    grid-column: 1 / -1;
  }
  .metadata-row { grid-template-columns: minmax(92px,.35fr) minmax(0,1fr); }
}
@media (max-width: 760px) {
  .view-hero-meta { grid-template-columns: 1fr; }
  .view-brand { align-items: flex-start; }
  .view-topbar h1 { font-size: clamp(2.15rem,10vw,3.4rem); line-height: .98; }
  .metadata-row { grid-template-columns: 1fr; gap: 7px; }
  .project-tabs-card, .project-tabs-shell { min-height: 0; }
  .project-tab-panel { min-height: 430px; padding: 18px; }
  .project-tab-empty { min-height: 390px; padding: 24px; }
}
@media (max-width: 480px) {
  .view-shell { padding: 12px; }
  .view-topbar, .view-grid, .view-column { gap: 12px; }
  .view-hero-card, .view-panel, .view-hero-meta { border-radius: 20px; }
  .view-hero-card { padding: 18px; }
  .view-brand { gap: 12px; }
  .view-brand-logo { width: 64px; height: 64px; flex: 0 0 64px; }
  .view-eyebrow { padding: 8px 10px; font-size: .68rem; }
  .view-eyebrow-meta { font-size: .68rem; }
  .view-topbar h1 { margin-top: 14px; font-size: clamp(1.9rem,11vw,2.7rem); }
  .view-menubar-card { padding: 5px 8px; border-radius: 18px; }
  .view-hero-meta { padding: 14px; }
  .view-panel-head, .view-panel-body { padding-inline: 16px; }
  .project-tabs-nav { padding-inline: 10px; }
  .project-tab { min-height: 44px; padding-inline: 11px; font-size: .8rem; }
  .project-tab-panel { min-height: 360px; padding: 12px; }
  .project-tab-empty { min-height: 336px; padding: 20px; border-radius: 18px; }
}
"""

_FALLBACK_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
<defs>
  <linearGradient id="a" x1="0" y1="0" x2="1" y2="1">
    <stop stop-color="#38bdf8"/><stop offset="1" stop-color="#155eaa"/>
  </linearGradient>
  <linearGradient id="b" x1="0" y1="0" x2="1" y2="1">
    <stop stop-color="#67e8f9"/><stop offset="1" stop-color="#2563eb"/>
  </linearGradient>
</defs>
<rect width="400" height="400" rx="72" fill="#111b2d"/>
<path d="M70 142 150 96l80 46-80 46z" fill="#38bdf8"/>
<path d="M70 142v92l80 46v-92z" fill="#0b4f96"/>
<path d="M230 142v92l-80 46v-92z" fill="url(#a)"/>
<rect x="224" y="104" width="38" height="176" rx="8" fill="#0ea5e9"/>
<rect x="272" y="70" width="38" height="210" rx="8" fill="url(#b)"/>
<rect x="320" y="126" width="28" height="154" rx="8" fill="#60a5fa"/>
</svg>
"""


def generate_project_dashboard(context: CliContextPort) -> Dict[str, Any]:
    """Generate the approved InfoBIM project dashboard at the container root."""
    container_path = resolve_container_path(context)
    options = resolve_view_options(context)
    payload = gather_view_data(context)
    project = _project_metadata(container_path, payload)

    source_fingerprint = str(payload["source_fingerprint"])
    options_fingerprint = str(payload["options_fingerprint"])
    indexed_files = int(payload["summary"]["indexed_files"])

    _ensure_dashboard_assets(container_path)
    index_path = container_path / "index.html"
    _atomic_write_text(
        index_path,
        _render_dashboard(
            project=project,
            indexed_files=indexed_files,
            generated_label=_generated_label(),
            source_fingerprint=source_fingerprint,
            options_fingerprint=options_fingerprint,
        ),
    )
    ContainerDataPackageSynchronizer().sync(container_path)

    return {
        "container_path": str(container_path),
        "container_id": project["id"],
        "index_path": str(index_path),
        "index_uri": index_path.as_uri(),
        "indexed_files": indexed_files,
        "source_fingerprint": source_fingerprint,
        "options_fingerprint": options_fingerprint,
        "view_type": options["view_type"],
        "representation": options["representation"],
        "language": options["language"],
        "template": _DASHBOARD_TEMPLATE_MARKER,
    }


def is_project_dashboard_generated(context: CliContextPort) -> bool:
    try:
        container_path = resolve_container_path(context)
        options = resolve_view_options(context)
        index_path = container_path / "index.html"
        if not index_path.is_file():
            return False

        document = index_path.read_text(encoding="utf-8")
        return (
            _DASHBOARD_TEMPLATE_MARKER in document
            and _meta_value(document, _SOURCE_FINGERPRINT_META)
            == calculate_source_fingerprint(container_path)
            and _meta_value(document, _OPTIONS_FINGERPRINT_META)
            == calculate_options_fingerprint(options)
            and is_data_gathered(context)
        )
    except (OSError, TypeError, ValueError):
        return False


def _project_metadata(
    container_path: Path,
    payload: Dict[str, Any],
) -> Dict[str, str]:
    fallback = dict(payload.get("container") or {})
    metadata = {
        "id": str(fallback.get("id") or fallback.get("uri") or ""),
        "name": str(fallback.get("name") or container_path.name),
        "description": str(fallback.get("description") or ""),
        "path": str(container_path),
    }

    for project_file in _project_metadata_files(container_path):
        try:
            graph = Graph()
            graph.parse(str(project_file), format="turtle")
        except Exception:
            continue

        subject = _project_subject(graph)
        if subject is None:
            continue

        metadata["id"] = (
            _graph_text(graph, subject, DCTERMS.identifier)
            or str(subject)
            or metadata["id"]
        )
        metadata["name"] = (
            _graph_text(graph, subject, DCTERMS.title)
            or _graph_text(graph, subject, RDFS.label)
            or metadata["name"]
        )
        metadata["description"] = (
            _graph_text(graph, subject, DCTERMS.description)
            or _graph_text(graph, subject, RDFS.comment)
            or metadata["description"]
        )
        break

    return metadata


def _project_metadata_files(container_path: Path) -> Iterable[Path]:
    preferred = (
        container_path / ".__ontobdc__" / "__infobim__" / "project.ttl",
        container_path / ".__ontobdc__" / "project.ttl",
        container_path / "project.ttl",
    )
    yielded = set()
    for candidate in preferred:
        resolved = candidate.resolve()
        if resolved in yielded:
            continue
        yielded.add(resolved)
        if candidate.is_file():
            yield candidate

    try:
        for candidate in container_path.rglob("project.ttl"):
            resolved = candidate.resolve()
            if resolved in yielded:
                continue
            yielded.add(resolved)
            if candidate.is_file():
                yield candidate
    except OSError:
        return


def _project_subject(graph: Graph) -> Optional[URIRef]:
    for subject, _, object_value in graph.triples((None, RDF.type, None)):
        if isinstance(subject, URIRef) and str(object_value).lower().endswith(
            "ifcproject"
        ):
            return subject

    for predicate in (DCTERMS.title, RDFS.label):
        for subject in graph.subjects(predicate, None):
            if isinstance(subject, URIRef):
                return subject
    return None


def _graph_text(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    value = graph.value(subject, predicate)
    return str(value).strip() if value is not None else ""


def _generated_label() -> str:
    current = datetime.now().astimezone()
    weekday = _WEEKDAY_NAMES[current.weekday()]
    month = _MONTH_NAMES[current.month - 1]
    return (
        f"{weekday}, {current.day} de {month} de {current.year} "
        f"às {current:%H:%M}"
    )


def _ensure_dashboard_assets(container_path: Path) -> None:
    asset_root = (
        container_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
    )
    css_path = asset_root / "css" / "project_dashboard.css"
    logo_png = asset_root / "logo.png"
    logo_svg = asset_root / "logo.svg"

    if not css_path.is_file():
        _atomic_write_text(css_path, _BASE_CSS.strip() + "\n")
    if not logo_png.is_file() and not logo_svg.is_file():
        _atomic_write_text(logo_svg, _FALLBACK_LOGO_SVG)


def _render_dashboard(
    *,
    project: Dict[str, str],
    indexed_files: int,
    generated_label: str,
    source_fingerprint: str,
    options_fingerprint: str,
) -> str:
    project_id = html.escape(project["id"], quote=True)
    project_name = html.escape(project["name"])
    project_path = html.escape(project["path"])
    generated = html.escape(generated_label)
    dashboard_payload = json.dumps(
        {
            "projectId": project["id"],
            "name": project["name"],
            "path": project["path"],
        },
        ensure_ascii=False,
        indent=2,
    ).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="{_SOURCE_FINGERPRINT_META}" content="{html.escape(source_fingerprint, quote=True)}">
  <meta name="{_OPTIONS_FINGERPRINT_META}" content="{html.escape(options_fingerprint, quote=True)}">
  <meta name="ontobdc-view-template" content="{_DASHBOARD_TEMPLATE_MARKER}">
  <title>{project_name}</title>
  <link rel="stylesheet" href="./.__ontobdc__/asset/infobim-view/css/project_dashboard.css">
  <style>{_LAYOUT_CSS}</style>
</head>
<body>
  <main class="view-shell">
    <section class="view-topbar">
      <div class="view-topbar-primary">
        <article class="view-hero-card" data-card="hero-card">
          <div class="view-brand">
            <img
              class="view-brand-logo"
              src="./.__ontobdc__/asset/infobim-view/logo.png"
              onerror="this.onerror=null;this.src='./.__ontobdc__/asset/infobim-view/logo.svg';"
              alt="InfoBIM logo"
            >
            <div class="view-brand-copy">
              <span class="view-eyebrow">InfoBIM Dashboard</span>
              <span class="view-eyebrow-meta">{project_id}</span>
            </div>
          </div>
          <h1>{project_name}</h1>
        </article>
        <article class="view-menubar-card" data-card="dynamic-menubar-card">
          <div class="view-menubar-track">
            <button
              class="menubar-item"
              type="button"
              data-action="view/work_stream/7c7e9d91-046d-5bcb-ad09-a04c5821c6de.html"
              aria-label="WorkStream"
            >
              <span class="menubar-item-label" aria-hidden="true">5W2H</span>
              <span class="menubar-item-value">WorkStream</span>
            </button>
          </div>
        </article>
      </div>

      <aside class="view-hero-meta" data-card="numeric-data-grid"></aside>
    </section>

    <section class="view-grid">
      <div class="view-column view-column-third">
        <article class="view-panel" data-card="project-information-card">
          <header class="view-panel-head">
            <h2 class="view-panel-title">Project Information</h2>
            <p class="view-panel-copy" id="project-current-date">
              <span class="view-panel-copy-diamond">◆</span>{generated}
            </p>
          </header>
          <div class="view-panel-body">
            <dl class="metadata-list">
              <div class="metadata-row">
                <dt>Name</dt>
                <dd>{project_name}</dd>
              </div>
              <div class="metadata-row">
                <dt>Path</dt>
                <dd>{project_path}</dd>
              </div>
              <div class="metadata-row">
                <dt>Arquivos indexados</dt>
                <dd>{indexed_files}</dd>
              </div>
            </dl>
          </div>
        </article>

        <article class="view-panel" data-card="pyodide-runtime-card">
          <header class="view-panel-head">
            <h2 class="view-panel-title">Pyodide Runtime</h2>
            <p class="view-panel-copy">Bootstrap do ambiente Python no browser para as proximas etapas do dashboard.</p>
          </header>
          <div class="view-panel-body">
            <div class="runtime-status">
              <span class="runtime-dot" id="pyodide-status-dot"></span>
              <strong id="pyodide-status-label">Initializing Pyodide...</strong>
            </div>
            <pre class="runtime-console" id="pyodide-console">Waiting for runtime...</pre>
          </div>
        </article>
      </div>

      <div class="view-column view-column-main">
        <article class="view-panel project-tabs-card" data-card="project-tabs-card">
          <header class="view-panel-head">
            <h2 class="view-panel-title">Frentes de Trabalho</h2>
            <p class="view-panel-copy">Acompanhe as frentes do projeto em uma janela móvel de duas semanas.</p>
          </header>
          <div class="project-tabs-shell">
            <div class="project-tabs-nav" role="tablist" aria-label="Frentes de Trabalho" data-project-tablist>
              {_tab_button("workstreams", "Frentes de Trabalho", "≋", True)}
            </div>
            <div class="project-tabs-content">
              {_tab_panel("workstreams", "Frentes de Trabalho", "≋", "Frentes publicadas no grafo JSON-LD do projeto.", False)}
            </div>
          </div>
        </article>
      </div>
    </section>
  </main>

  <script>
    window.infoBimProjectDashboard = {dashboard_payload};
    (() => {{
      const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
      const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
      function selectTab(tab) {{
        tabs.forEach((item) => {{
          const active = item === tab;
          item.setAttribute('aria-selected', active ? 'true' : 'false');
          item.tabIndex = active ? 0 : -1;
        }});
        panels.forEach((panel) => {{
          panel.hidden = panel.id !== tab.getAttribute('aria-controls');
        }});
      }}
      document.querySelectorAll('.menubar-item[data-action]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const action = String(button.dataset.action || '').trim();
          if (action.startsWith('view/') || action.startsWith('./view/')) {{
            window.location.href = action;
          }}
        }});
      }});
      tabs.forEach((tab) => {{
        tab.addEventListener('click', () => selectTab(tab));
        tab.addEventListener('keydown', (event) => {{
          const index = tabs.indexOf(tab);
          if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {{
            event.preventDefault();
            const delta = event.key === 'ArrowRight' ? 1 : -1;
            const next = tabs[(index + delta + tabs.length) % tabs.length];
            selectTab(next);
            next.focus();
          }}
        }});
      }});
    }})();
  </script>
  <script defer src="https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js"></script>
  <script defer src="./.__ontobdc__/asset/infobim-view/js/pyodide_bootstrap.js"></script>
</body>
</html>
"""


def _tab_button(
    tab_id: str,
    label: str,
    icon: str,
    selected: bool,
) -> str:
    selected_text = "true" if selected else "false"
    tabindex = "0" if selected else "-1"
    return f"""<button
                class="project-tab"
                type="button"
                id="project-tab-{tab_id}"
                role="tab"
                aria-selected="{selected_text}"
                aria-controls="project-tab-panel-{tab_id}"
                tabindex="{tabindex}"
                data-tab-id="{tab_id}"
              >
                <span class="project-tab-icon" aria-hidden="true">{icon}</span>
                <span>{label}</span>
              </button>"""


def _tab_panel(
    tab_id: str,
    title: str,
    icon: str,
    description: str,
    hidden: bool,
) -> str:
    hidden_attribute = " hidden" if hidden else ""
    return f"""<section
                class="project-tab-panel"
                id="project-tab-panel-{tab_id}"
                role="tabpanel"
                aria-labelledby="project-tab-{tab_id}"
                tabindex="0"{hidden_attribute}
              >
                <div class="project-tab-empty">
                  <span class="project-tab-empty-icon" aria-hidden="true">{icon}</span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </div>
              </section>"""


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _meta_value(document: str, name: str) -> str:
    pattern = re.compile(
        rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"\s*/?>',
        re.IGNORECASE,
    )
    match = pattern.search(document)
    return html.unescape(match.group(1)) if match else ""
