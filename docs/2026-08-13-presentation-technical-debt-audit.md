# Presentation Layer Technical Debt Audit — 2026-08-13

Audited directory: `/presentation` (both `src/ontobdc_view` production code and `lab/workstream-generalization/reference` legacy reference material)

Audit date: 2026-08-13
Auditor: automated, assisted by LLM (OntoBDC repo rules: SOLID, KISS, DRY, Clean Architecture, no hardcoded-path-free)

---

## TL;DR Summary

| # | Severity | Title | Count (src/ (production) | Count lab/reference |
|---|----------|-------|---------------------------|----------------|
| 1 | 🟡 Medium | Hardcoded ontology namespace URIs (bypasses ontobdc.shared.adapter.ontology) | **19 occurrences · 12 files | N/A |
| 2 | 🟡 Medium | Hardcoded personal `author=` URI in every Tile/Page plugin metadata | **12 occurrences · 12 files | N/A |
| 3 | 🟠 Low    | Pyodide `<script>` load without Subresource Integrity (SRI) hash pinning | **1 occurrence** | N/A |
| 4 | 🔴 Resolved | Write/Read in forbidden path `.__ontobdc__/relation/work_stream/<id>.ttl` | **0** (✅ fixed 2026-08-13) | 2 left in reference/ |
| 5 | 🔴 Legacy only | `urn:infobim:...` URN hardcoded (`workstream-resource` + `infobim:project-opened` event API | 0 (only explanatory comment) | **4 occurrences** |

**Net result after the 2026-08-13 corrective commits: 0 remaining HIGH-severity findings inside `presentation/src/`. Everything remaining findings are architectural debt (Medium / Low) or confined to lab/reference material (NOT part of the ontobdc-view published wheel).

---

## 🔴 Resolved (already fixed in this session)

### HIGH #1 — Forbidden `.relation/ directory writes (1 grave production bug.

Root cause: old `relationFileHandle()` function in `presentation/src/ontobdc_view/page/asset/work_stream_view.js` wrote curated dimension↔resource DirectedBinaryLink files under:
```
.<projeto>/.__ontobdc__/relation/work_stream/<work_stream/<workstream-id>.ttl
```
This path is **explicitly outside the canonical project's official ICDD ISO 21597 structure which mandates `.__ontobdc__/linkset/` and the `LINKSET_DIRECTORY_NAME = "linkset"` constant from
Fixed by refactored:
```
.__ontobdc__/linkset/ WorkStreamResource.ttl (Related  = confirmed curated links .ttl   Suggested lifecycle links, Proposed → → →  →
`relationFileHandle() was renamed to a generic linksetFileHandle()`-parameterised by kind; the old Python script was subsumed into a single `runLinksetOperation((.
* The forbidden directory tree .__ontobdc__/relation/ no longer written **zero grep matches inside `src/*.js`. All references to the `runRelationOperation` / `loadAllRelations` legacy API legacy APIs are now are are the the the legacy legacy APIs in in the the the
| Resolved references: legacy code is 0, 2 left in lab (`workstream_5w2h.js.parts reference/*)

---

## 🟡 MEDIUM severity — production debt (src/)

### MEDIUM #1 — Hardcoded ontology namespace string literals (19 occurrences · 12 files)

Violates user rule #15:
> _"Reuse the official ontology adapter (`get_ontology_path / get_ontology_content / OntologyConfigAdapter) BEFORE manually resolving ontology URIs. It is forbidden to invent parallel hardcoded local ad-hoc access when the official adapter exists._

The presentation package instead copies string literals of every ontology namespace base URI in every module. If the canonical URIs are ever migrated (e.g. `http://ontobdc.org/ontology/domain/ns.ttl#` → `https://w3id.org/ontobdc/ontology/ns#`, or `http://datacenter.app.br/...` → a branded URI), every consumer must grep & replace 19+ touchpoints, 3 of them inside the same `work_stream_view.js` triple duplicates the OBDC_NS literal 4 independent times (lines 3, 507, 786, 832) and another file, which invites inconsistency.

#### Python (Namespace literal occurrences (`src/ontobdc_view/**/*.py`:

| File | Line(s) | Literal | Adapter replacement |
|------|----------|---------|-------------------|
| `component/adapter/surface_definition.py` | 16 | `Namespace("http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#")` (`VIEW`) | `get_ontology_by_prefix("view")` → concat `#` |
| `page/plugin/work_stream_view.py` | 4–7 | `WORK_STREAM_TYPE_URI = "http://datacenter.app.br/ontology/productivity/entity/work_stream/type.ttl#WorkStream"` | `get_ontology_by_prefix("work_stream_type")` + suffix |

#### JS / JS-in-Pyodide occurrences (`src/ontobdc_view/**/*.js):

| File | Line(s) | Literal(s) |
|------|----------|------------|
| `page/asset/work_stream_view.js` | 2–3 | `WORK_STREAM_TYPE_NS`, `OBDC_NS` |
| `page/asset/work_stream_view.js` | 507 | `SUGGESTION_STATUS_NS` (duplicate of `OBDC_NS` same string) |
| `page/asset/work_stream_view.js` | 786–787 | Pyodide Python inline `OBDC = Namespace("http://ontobdc.org/...")`, `SIG = Namespace("...signature.ttl#")` |
| `page/asset/work_stream_view.js` | 832 | `FILE_DISPLAY_STATUS_NS` (3rd copy of the exact same OBDC_NS literal) |
| `component/asset/onto-workstream-tile.js` | 1 | `WORK_STREAM_TYPE_NS` (same URI duplicated from work_stream_view.js) |
| `component/asset/onto-file-tree-tile.js` | 377, 392 | `http://ontobdc.org/ontology/domain/ns.ttl#filePath` predicate (2×) |
| `component/asset/onto-generic-file-tile.js` | 224, 227 | `...#filePath`, `...#fileSize` predicates (2×) |
| `component/asset/onto-csv-file-tile.js` | 338 | `...#filePath` predicate |
| `component/asset/onto-image-file-tile.js` | 224 | `...#filePath` predicate |
| `component/asset/onto-pdf-file-tile.js` | 237, 239 | `...#filePath`, `...#fileSize` predicates (2×) |
| Test files: | L32–33 L13 L10 L12 | `test_work_stream_view_browser.py`, `test_surface_resolution.py`, `test_surface_definition.py`, `test_default_surface_layout_definition.py`, `surface_preview.py` |
#### Recommended fix:
1. Add `presentation Python side): introduce a dedicated ontology constants module (e.g. `ontobdc_view.shared.adapter.ontology_namespaces.py`) that thin-wraps the shared `OntologyConfigAdapter`/`get_ontology_by_prefix` and exposes only exposes the resolved namespace prefixes `obdc`, `view`, `workstream_type`, `signature`, `file_display`) as frozen constants.
2. (Jinja2 template side): inject a `<meta>` tag per registered ontology prefix (e.g. `<meta name="ontology:obdc" content="https://w3id.org/ontobdc/ontology/ns#"/>)` into `work_stream_view.html.j2` during page render — then the JS layer reads `document.querySelector('meta[name="ontology:*"]') once and populates an NS map from the DOM instead of carrying strings.
3. Deduplicate the four `OBDC_NS` in `work_stream_view.js` to a single top-level const. Everything else (SUGGESTION_STATUS_NS, FILE_DISPLAY_STATUS_NS) = assignment `= OBDC_NS;` so there's a single source of truth for the `filePath/fileSize/file predicates: move into a single `const PRED = { filePath: new URL(${OBDC_NS}filePath }` literal so grep & replace them 1 touchpoint.

---

### MEDIUM #2 — `author=` personal URI in every plugin metadata (12 occurrences · 12 files)

Every Tile and Page plugin under `src/ontobdc_view/{component,page}/plugin/` contains a `PageMetadata` / `TileMetadata` with a verbatim copy of
```python
author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"]
```
| File | Line |
|------|------|
| `component/plugin/workstream_tile.py` | 31 |
| `component/plugin/photo_tile.py` | 28 |
| `page/plugin/work_stream_view.py` | 26 |
| `component/plugin/generic_file_tile.py` | 21 |
| `component/plugin/theme_tile.py` | 26 |
| `component/plugin/csv_file_tile.py` | 15 |
| `component/plugin/logo_tile.py` | 26 |
| `component/plugin/data_container_tile.py` | 25 |
| `component/plugin/image_file_tile.py` | 15 |
| `component/plugin/file_tree_tile.py` | 20 |
| `component/plugin/language_tile.py` | 26 |
| `component/plugin/pdf_file_tile.py` | 15 |

#### Risk
* If the personal knowledge-base domain (`kb.elias.eng.br) is ever migrated to a project-owned person ontology (e.g. `https://w3id.org/ontobdc/person/elias#`), 12 edits required — invites silent inconsistency if one is forgotten.
* New contributors contributing a new Tile cannot follow because they have to copy-paste someone else's URI string — there is no module-wide authorship policy for the ontobdc-view package.

#### Recommended fix
1. Create a `ontobdc_view.shared.domain.authorship.DEFAULT_AUTHORS` frozen list (a central constant.
2. If per-plugin additional authorship is ever required (a plugin was written by a 3rd party) then the plugin overrides `DEFAULT_AUTHORS + extras. For today's 12 plugin plugins DEFAULT_AUTHORS is identical across all 12 so `DEFAULT_AUTHORS` zero touch → single touch 1 edit changes them all.

---

## 🟠 LOW severity — production debt (src/)

### LOW #1 — Pyodide `<script>` load without SRI integrity hash (1 occurrence)

File `page/asset/work_stream_view.js`, line 495:
```javascript
const PYODIDE_CDN_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js";
```
The version is correctly pinned (✅ good). But `ensurePyodide()` creates a `<script>` element and sets its `.src` without setting `element.integrity = "sha384-<hash of the exact v0.27.2/full/pyodide.js>"` + `element.crossOrigin = "anonymous"`. Without Subresource Integrity, a compromised CDN or network attacker would run arbitrary code in the page context without any detection.

#### Recommended fix
1. Download a trusted copy of the exact pyodide v0.27.2 `full/pyodide.js` locally.
2. `cat pyodide.js | openssl dgst -sha384 -binary | openssl base64 -A
3. Append the base64 output as `integrity = "sha384-..."`.
4. Set both `integrity` + `crossOrigin` on the `<script>` before appending to `<head>`.

---

## 🔴 HIGH — LAB / REFERENCE-only debt (NOT production)

These findings live **exclusively inside `presentation/lab/workstream-generalization/reference/` legacy and are **not shipped** in the ontobdc-view package. They are documented because the reference material was described in `AGENTS.md` rule #17 ("Claudia") explicitly says: *"Treat those files as source evidence, not as code to move verbatim. Do not resurrect those paths blindly."* — knowing where the legacy skeletons are helps future contributors avoid accidentally copying the deprecated patterns back into production.

| Legacy anti-pattern | File in reference/ | Line |
|--------------------|---------------------|------|
| `urn:infobim:linkset:workstream-resource:` deprecated InfoBIM URN (must use `urn:ontobdc:linkset:`) | workstream_5w2h.js.parts/004.js | 250 |
| `infobim:project-opened` custom event coupling the generic ontobdc surface declares no such contract) | `workstream_5w2h.js.parts/001.js` | 117 |
| Event listener for same `infobim:project-opened` | annotation_query_integration.js | 11 |
| `__infobim__` legacy special folder name hardcoded in reference generator | html.py | 91 |

---

## Recommended remediation order (causal-root-first, per architectural risk exposure descending):

1. 🟡 MEDIUM #1 Hardcoded ontology URIs → the one with highest fan-out19 touchpoints across Python + JS) — the single most likely source of a silent multi-file inconsistency.
2. 🟡 MEDIUM #2 author= author policy central → 12 files, zero logic change (pure metadata)
3. 🟠 LOW #3 Pyodide SRI integrity hash → 5 line edit
4. 🔴 LAB reference deprecated anti-patterns → leave them there are intentionally (low touch as long as the lab directory is not imported into production wheel build. Delete them when reference material retire when the the ontobdc-view migration is declared 100% generic.

---

## Scan evidence (reproducibility)

Exact grep patterns used for this audit are reproducible with `rg` (ripgrep) from the repository root:

```bash
# forbidden path relation/
rg -n --glob '*.js' '.__ontobdc__/relation' presentation/
# absolute personal hardcoded authorship URI
rg -n --glob '*.py' 'kb\.elias\.eng\.br.*ttl#Elias' presentation/src
# ontology literal ns
rg -n --glob '*.{js,py,html}' 'http://ontobdc.org/ontology|http://datacenter.app.br/ontology' presentation/src
# legacy InfoBIM hardcodes
rg -n --glob '*.{js,html,py}' 'urn:infobim:|infobim:project-opened|__infobim__' presentation
```
