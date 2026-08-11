# Changelog

## Unreleased

### Removed

- Removed both competing CLI response-rendering systems: the ANSI logo+markdown+JSON path (`cli.adapter.response.ResponseAnsiInformationAdapterLoader` and its adapters) that `main()` actually executed in `rich` mode, and the parallel, never-wired-up message-box system (`view.plugin.render.rich.layout.RichMessageBoxLayout`, `view.adapter.response.*MessageBoxAdapter`, `view.adapter.loader.ResponseMessageBoxAdapterLoader`, `view.domain.port.layout`, `view.domain.port.response`, and the private table-marker convention in `view.domain.model.table`). Neither survives; see `docs/notes/2026-08-10-ontobdc-terminal-presentation-surface-concept.md` for the rationale.

### Added

- Added a `Widget` port (`view.domain.port.widget`) and its concrete terminal implementations (`view.component.widget.python`: `TextWidget`, `KeyValueWidget`, `TableWidget`, `CodeBlockWidget`, `ErrorWidget`). A Widget only knows how to turn itself into lines of text given a granted column count.
- `TerminalSurface` (`view.component.surface.python`) now hosts Widgets: `place(widgets)` renders each one against the current terminal width and stacks the results. This fulfills what the class's own docstring already claimed ("Terminal implementation of a PresentationSurface").
- `cli.adapter.response` now maps each `CommandResponse` type to a `list[Widget]` (via the new `ResponseWidgetAdapterPort` / `ResponseWidgetAdapterLoader`) instead of rendering a single fixed block. The "harmonious record/table" content detection is preserved from the discarded message-box system and extended to recurse: a flat dict of scalars becomes a `KeyValueWidget`; a dict of two or more same-shaped record dicts becomes a `TableWidget` (outer key as the first column); a list of same-shaped dicts becomes a `TableWidget`; a list of scalars becomes a bullet list; a dict that is none of these gets one heading + decomposed widget per key instead of collapsing to JSON. This is what makes `ontobdc --help`/`ontobdc` (whose content is `{"Usage": [...], "Commands": {flag: {...}}}`) render as a labeled list and table instead of one opaque JSON block — previously neither rendering system handled that shape.
- `_render_rich_response` now prints the OntoBDC logo banner once per CLI invocation, above the response, instead of once per response adapter.
- The logo Tile now has two sizes instead of always rendering the large ANSI-art banner: `LogoComponent.render_compact()` — a one-line `>_ OntoBDC` — is the default; the existing `render()` (full pyfiglet banner) is now opt-in via the new `--large-logo` flag.
- Added `GridWidget` (`view.component.widget.python`), `GridCommandResponse`, and `GridCommandResponseWidgetAdapter` that draw a PresentationSurface's Tile grid to scale — `columns` x `rows` cells of `slot_width` x `slot_height` characters each, each cell labeled with its `row,column` coordinate and `slot_width x slot_height` size on two lines. `rows` is only the tile-content rows (e.g. `TerminalSurface.visible_logical_rows`); when `operation_enabled`/`pinned_enabled` are set, `GridWidget` also draws the space `TerminalSurface` reserves for those bars as an explicit labeled band above/below the grid, at its real `slot_height`, instead of that space silently vanishing from the rows count with nothing shown for it — on a short terminal this reservation (2x `slot_height` by default) can consume most of the height, which was confusing without the band drawn. These are reusable library primitives; the actual CLI command that exercises them (`debug --grid terminal`) lives in the `ontobdc-dev` workspace CLI, not here — see that package's changelog.
- Added `obdc:SurfaceableEntity` to the domain ontology (`brasidatacenter/ontology/ontobdc/domain/ns.ttl`): a marker class an entity type asserts to become eligible for a direct Tile representation on a Presentation Surface. `obdc:DataContainer` and `WorkStream` are marked this way; `SurfaceMatchedCapability._is_surfaceable()` gates auto-matching on it, and `DataGatheredCapability` re-enables merging each dataset's own graph into `DATA_GATHERED`, restricted to entities carrying the marker.
- Added the WorkStream Tile: a `ComponentPort` descriptor (now living in `ontobdc-view`, see that package's changelog) plus the server-side materialization that reads each dataset's `facade.ttl`-declared `FacadeField`s and writes their populated values as literal triples onto the entity subject during `DATA_GATHERED` (`view.plugin.capability.transformation.data_gathered._add_dataset_field_values`), so the Tile can render real 5W2H field values without depending on the `context` layer at request time.
- Added `dataset_healthy` (`storage.plugin.capability.transformation.dataset_healthy`) and wired it into the container update statechart. It repairs stale per-dataset state, including a new `is_dataset_surfaceable_synced` check/hotfix pair that re-materializes a dataset's `obdc:SurfaceableEntity` marker locally (from a `linkset/type.ttl` copy made at entity-creation time) if it's missing from `dataset.ttl` — this is what lets `ontobdc storage --update` self-heal a Tile that stopped appearing after its class was marked `SurfaceableEntity` later than the dataset was created.
- `context entity --create` now infers `--container` from the current working directory, creates one dataset per instance (instead of writing into the shared container graph), and materializes the resolved `linkset/facade.ttl` and `linkset/type.ttl` locally into the dataset directory, so later `storage`-layer checks can read them without depending on `context`'s ontology-resolution machinery.
- Added per-file entities and type-specific display Tiles (image, PDF, CSV, generic file) that stay closed until their file is opened from the file tree, instead of all appearing on page load.

### Fixed

- `context --entity <Type>` (three bare arguments, no `:` in the value) now routes to the entity list instead of always hitting the dead URI-lookup stub.
- `storage --update`'s HTML regeneration step no longer requires an externally injected `container_html_view_update_capability`; it now calls the Surface generation pipeline directly and re-syncs the Data Package/RO-Crate state that regeneration touches.
- Frictionless resource reads in `context.adapter.dataset_instance` no longer fail with "path is not safe" for absolute local dataset paths (wrapped in `frictionless.system.use_context(trusted=True)`).
- `SurfaceMatchedCapability`'s auto-match order is now deterministic — container, then file tree, then everything else — instead of following RDF graph subject iteration order, which produced a different (and sometimes visually wrong) Tile order on each regeneration.

### Changed

- Removed the redundant "OntoBDC" prefix from response titles across the CLI, since the message box already shows it once via the `title_type` badge (`>_ OntoBDC ...` / `>_ ERROR ...`). Affected defaults and command titles: `ExceptionCommandResponse.title` ("OntoBDC Run Exception" → "Run Exception"), the top-level CLI's unhandled-exception title ("OntoBDC Run" → "Run"), `ontobdc --version` ("OntoBDC Version" → "Version"), `ontobdc context` ("OntoBDC Context" → "Context"), `ontobdc context entity` ("OntoBDC Context Entity" → "Context Entity"), and `ontobdc init` ("OntoBDC Init" → "Init"). `WelcomeCommandResponse`'s "InfoBIM Welcome" default is unrelated (a different product name, not a duplication) and was left unchanged.
- Moved the Presentation Surface's Tile `ComponentPort` descriptors out of `view.plugin.component` and into the `ontobdc-view` package (`ontobdc_view.component.plugin`, singular naming throughout). `shared.adapter.loader.ComponentLoader` now discovers them via an explicit scan of the installed `ontobdc_view` package rather than the generic `plugin/<resource>/` filesystem walk, since `ontobdc_view` uses an inverted `component/plugin/` layout. **This makes `ontobdc-view` a runtime dependency of the `view` layer's Tile discovery** — see "Known gaps" below.

### Known gaps

- `ontobdc-view` is imported at runtime (`shared.adapter.loader.ComponentLoader._load_ontobdc_view_components`) but is **not yet declared as a dependency** in `pyproject.toml`, and is not published to PyPI. The import is guarded (`except ImportError: return []`), so a production install without it simply renders no Tiles instead of failing — but this is silent and needs to be resolved (publish `ontobdc-view` and declare the dependency for real) before relying on Tiles in a packaged release.

## Unreleased — v0.12

### Breaking changes

- Replaces the previous annotation payload with strict annotation schema 2.
- Removes legacy-schema detection, fallback, repair, aliases, and automatic migration.
- Requires one of five concrete categories: Note, Issue, Classification, Location, or Record.
- Treats `EnrichmentAnnotation` as the shared semantic abstraction, never as a concrete Note.

### Added

- Generic typed editor and category-specific validation.
- Point, multiple-point, and bounding-box geometry tools.
- Canonical visual-contract projection and rendering.
- Authorship, modification, assignment, resolution, recording roles, and optional Subjects.
- Generic entity resolver contract.
- Annotation workspace with combined filters, counters, details, and visual selection.
- Subject Page with Space, Timeline, People, unassigned Subjects, and deep links.
- Strict local persistence with revision checks and post-write verification.
- Anonymous integration fixture spanning the complete annotation matrix.
