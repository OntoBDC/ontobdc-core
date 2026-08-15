# OntoBDC CLI Command Reference

> All commands listed here are implemented under `ontobdc/src/ontobdc/{cli,storage,context,view,dev}/plugin/command/`.
> Audited & compiled: 2026-08-14
> Audited codebase: 14 registered commands across 5 logical components.

---

## Logical component map

All `ontobdc` CLI invocations follow a two-level routing pattern:

```
ontobdc [component] <flags/parameters>
#   component can be one of: init, --version, storage, context, view, dev
```

| Component | Module | Audited commands | Typical user goal |
|-----------|--------|------------------|-------------------|
| `cli` (bootstrap) | `cli/plugin/command/` | **2** | initialize a new workspace, print package version |
| `storage` | `storage/plugin/command/` | **6** | create/attach/update/delete containers, create datasets inside them, get help |
| `context` | `context/plugin/command/` | **4** | import PDFs, analyse files to guess entity types, list/create entity instances, learn an entity profile from files |
| `view` | `view/plugin/command/` | **1** | generate a static HTML Surface view of a container and open in browser |
| `dev` | `dev/plugin/command/` | **1** | delegate everything else to the standalone ontobdc-dev workspace CLI |

---

## 1. CLI bootstrap commands

### 1.1. `ontobdc init` — Initialize ontobdc in the current directory

**Goal** (user perspective): Turn an ordinary empty directory into an OntoBDC workspace, so you can later run storage, context and view commands inside it. Creates the hidden config and index artifacts that identify the directory as an OntoBDC project root.

| Field | Value |
|-------|-------|
| Metadata id | `init` |
| Logical component | `cli` |
| Class | `CliInitCommand` |
| Implementation file | `ontobdc/src/ontobdc/cli/plugin/command/init.py` |
| State transitions | `CliInitStateTransitionHandler` (machine) |
| Accepts exactly | `["init"]` |
| Usage | `ontobdc init` |
| Prerequisite / `check()` passes only if | no project root is already configured for the directory. If a root was already set, the command refuses to re-run to avoid overwriting existing workspaces. |
| Produces | initialised workspace root (`.__ontobdc__/` config + storage index skeleton). |

---

### 1.2. `ontobdc --version | -v` — Print the installed ontobdc package version

**Goal** (user perspective): Quickly verify which ontobdc version is currently active in the virtualenv, for bug reports or pinning.

| Field | Value |
|-------|-------|
| Metadata id | `version` |
| Logical component | `cli` |
| Class | `CliVersionCommand` |
| Implementation file | `ontobdc/src/ontobdc/cli/plugin/command/version.py` |
| State machine | none — pure `importlib.metadata.version("ontobdc")` call. |
| Accepts exactly | `["--version"]` or `["-v"]` |
| Usage | `ontobdc --version` / `ontobdc -v` |
| Response content | JSON key `"version": "X.Y.Z"`; falls back to the string `"unknown"` if the package metadata cannot be read. |

---

## 2. Storage component commands

All commands are routed under `ontobdc storage ...`.

Run `ontobdc storage --help` to list all storage options in the terminal.

### 2.1. `ontobdc storage --help | -h` — Storage component help summary

**Goal** (user perspective): Print the available storage flags and their usage lines without running anything.

| Field | Value |
|-------|-------|
| Metadata id | `help` |
| Logical component | `storage` |
| Class | `StorageHelpCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/help.py` |
| Accepts | any `storage` invocation followed by `--help` or `-h` |
| Usage | `ontobdc storage --help` |
| Response content | structured HelpResponse with two maps: `"Usage"` keys per subcommand id; `"Options"` flags + one-line human descriptions gathered dynamically from every registered `storage` command metadata. |

---

### 2.2. `ontobdc storage --create <path>` — Create a new local storage container at the given path

**Goal** (user perspective): Provision a brand-new, empty OntoBDC container (folder) that you will later import datasets, documents, view Surfaces, and entity workbooks into. The path becomes the container root.

| Field | Value |
|-------|-------|
| Metadata id | `ct_create` (container create) |
| Logical component | `storage` |
| Class | `StorageCreateCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/container/create.py` |
| State machine | `ContainerCreateStateTransitionHandler` |
| Route | args[0] = `storage`; args[1] = `--create`; args[2] is the path |
| Usage | `ontobdc storage --create <container_path>` |
| `check()` behaviour | strips any stale `dataset_path` from context; sets `container_path` = flag value for the state machine. |
| Produces | fresh container with .__ontobdc__ skeleton, datapackage.json, empty linkset folder and registered container id in the root storage index. |

---

### 2.3. `ontobdc storage --container-path <cp> --attach` — Attach an imported container to the project root

**Goal** (user perspective): You copied/downloaded an existing OntoBDC container folder (exported from another project) onto your disk. Now you want to "plug it in" to the current workspace so storage and views recognise its URN, datasets, and metadata. This reconciles the identity + datasets + storage index in one step.

| Field | Value |
|-------|-------|
| Metadata id | `container_attach` |
| Logical component | `storage` |
| Class | `StorageAttachCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/container/attach.py` |
| State machine | `ContainerAttachStateTransitionHandler` (uses a formal plan + ATTACH_PLAN/ERROR/COMPLETED parameters). |
| Route | `storage --container-path <existing_dir> --attach` (4 args total, positional order enforced) |
| Usage | `ontobdc storage --container-path <path> --attach` |
| `check()` behaviour | only passes if `<path>`: resolves to a real directory after expanduser/resolve; trims/validates; clears stale `ATTACH_*` run artefacts from previous failed attempts. |
| Produces | container appears in the workspace registry with its canonical URN identity; datasets become usable by `context`/`view`. |

---

### 2.4. `ontobdc storage --update` (or `--container-id <id> --update`) — Run cleanup + metadata update + Surface regeneration for a registered container

**Goal** (user perspective): The container's contents drifted since creation (you added/removed files by hand, or a new plugin was installed). Re-running `--update` walks the container through its standard lifecycle: cleanup, metadata re-sync, manifest synchronisation, RO-Crate sync, and HTML Surface regeneration. The result is a container fully consistent with the current workspace rules.

| Field | Value |
|-------|-------|
| Metadata id | `container_update` |
| Logical component | `storage` |
| Class | `StorageUpdateCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/container/update.py` |
| State machine | `ContainerUpdateStateTransitionHandler` |
| Route (2 forms) | 1) `storage --update` → container inferred from the current working directory<br>2) `storage --container-id <full-urn-or-short-id> --update` → explicit selection. The short id form (without `urn:ontobdc:storage/local/`) is automatically expanded. |
| Usage | `ontobdc storage --update`<br>`ontobdc storage --container-id urn:ontobdc:storage/local/<uuid> --update` |
| `check()` behaviour | resolves the container through the `is_container_id_registered` check; if no explicit id is passed and the cwd is not inside a registered container, raises `CliCommandArgumentException` with a human hint. |
| Produces | refreshed container metadata, HTML surface updated, all the storage/ro-crate/datapackage/manifest indices re-synchronised. |

---

### 2.5. `ontobdc storage --delete <container-id>` — Deregister a container from the root storage index

**Goal** (user perspective): A container is obsolete/duplicated/was attached by mistake. Remove all references to it from the master storage index so it no longer shows up in queries. Does **not** touch the files on disk — it only unlinks the container from the workspace registry (safe: you can re-attach it later if needed).

| Field | Value |
|-------|-------|
| Metadata id | `delete` |
| Logical component | `storage` |
| Class | `StorageDeleteCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/container/delete.py` |
| State machine | none — low-level direct graph edit on `storage_graph.ttl` via RDFlib. |
| Route | `storage --delete <urn-or-short-id>` |
| Usage | `ontobdc storage --delete <container-id>` |
| Normalisation of `<container-id>` | bare short ids are prefixed with `urn:ontobdc:storage/local/...`; full URNs are left untouched. |
| Resolution | looks up the container in the root storage graph by its `dcterms:identifier` matching any registered `OBDC.DataContainer`. If no subject exists, the command returns an explicit "Container is not registered" error payload instead of deleting anything. |
| Deletion strategy | removes both (container_subject, pred, obj) AND (anySubject, pred, container_subject) triples so no dangling references remain in the index. |
| Safety | actual folder contents are left on disk untouched — purely an index-level deregistration operation. |

---

### 2.6. `ontobdc storage --container <id-or-path> --create <dataset_path>` — Create a new dataset inside a container

**Goal** (user perspective): You have a registered container and now want to create the first logical dataset inside it. A dataset groups one entity type's instances (e.g. all WorkStreams, all Projects, or all Inspection Reports) with its own workbook, datapackage, type ontology, and future view surface.

| Field | Value |
|-------|-------|
| Metadata id | `ds_create` |
| Logical component | `storage` |
| Class | `DatasetCreateCommand` |
| Implementation file | `ontobdc/src/ontobdc/storage/plugin/command/dataset/create.py` |
| State machine | `DatasetCreateStateTransitionHandler` |
| Route | `storage --container <id-or-path> --create <path>` (5 positional args total). `<id-or-path>` accepts either the `urn:ontobdc:storage/local/...` short id or a filesystem path or a URN; `ContainerIdStrategy` disambiguates it. |
| Usage | `ontobdc storage --container <id-or-path> --create <dataset_path>` |
| Strict dataset constraints (from `_resolve_dataset_path`) | the dataset MUST be a single child folder directly inside the container (so `relative_to(container).parts` has length exactly 1). Cannot equal the container itself. Cannot be a nested subdirectory two levels deep. Cannot point at an existing non-directory file. Absolute paths are allowed and collapsed. |
| Produces | dataset folder populated with the dataset skeleton: `.__ontobdc__/datapackage.json`, storage index, and a registered dataset identity tied back to the parent container. |

---

## 3. Context component commands

All commands are routed under `ontobdc context ...`.

### 3.1. `ontobdc context --analyse <file_path>` — Analyse a PDF file against entity vectors and guess the closest entity type

**Goal** (user perspective): You received a PDF and you don't know which entity type in the Brasidata catalog it is. Run `--analyse` to compare the file against the pre-computed entity profiles (vectors) in the workspace and get back the best-matching entity type + classification evidence. Useful before importing it as an entity workbook instance.

| Field | Value |
|-------|-------|
| Metadata id | `analyse` |
| Logical component | `context` |
| Class | `ContextAnalyseCommand` |
| Implementation file | `ontobdc/src/ontobdc/context/plugin/command/analyse.py` |
| State machine | `EntityAnalysisStateTransitionHandler`, backed by a persistent `EntityAnalysisStepRepository` that stores intermediate artefacts. |
| Route | `context --analyse <file_path>` (3 args total) |
| Usage | `ontobdc context --analyse /path/to/report.pdf` |
| Hard format restriction | **currently only `.pdf` files are accepted** by `check()` — any other extension raises `CliCommandArgumentException` with a clear error message. |
| Response content on error | wraps errors into ExceptionCommandResponse with the offending source path echoed back and the exception message. |

---

### 3.2. `ontobdc context --entity ...` — Entity operations (4 modes)

**Goal** (user perspective): Swiss-army knife for anything about entities. A single `--entity` flag branches into four distinct modes, depending on the companion flags you pass. Every path flows through `ContextEntityCommand`.

| Field | Value |
|-------|-------|
| Metadata id | `entity` |
| Logical component | `context` |
| Class | `ContextEntityCommand` |
| Implementation file | `ontobdc/src/ontobdc/context/plugin/command/entity.py` |

Four distinct routing branches (mode auto-detected from argument shape):

#### Mode 3.2.1. `--entity --all` — List every entity published by the Brasidata catalog

**Goal** (user perspective): I want to browse all entity definitions officially supported in the workspace to know what I can work with (e.g. WorkStream, Project, Contract, PurchaseOrder, Supplier, etc.)

- Route: `["context", "--entity", "--all"]`
- Usage: `ontobdc context --entity --all`
- Data source: `BrasidataEntityCatalogRepositoryAdapter.list_entities()`
- Response payload: `entity_count`, `source_repository`, the full listing.

#### Mode 3.2.2. `--entity <entity_uri>` (URI/CURIE form, contains `:`) — Look up one persisted entity

**Goal** (user perspective): I have a concrete entity URN from an error message or log, and want to retrieve its definition/description in a single API call.

- Route: 3-arg form, third arg contains the colon character (disambiguation marker telling "this is a concrete URI, not a type name")
- Usage: `ontobdc context --entity urn:br:entity:abc123`
- Response: echoes `entity_uri` through for downstream renderers / tooling.

#### Mode 3.2.3. `--entity <TypeName>` (or `--container <id> --entity <TypeName>`) — List instances of a particular entity type already present in a container

**Goal** (user perspective): I want to see every WorkStream, every InspectionPhoto, every Project that has already been materialised inside a given container — useful before creating new instances to avoid duplicates.

- Route: either 3-arg short form (container inferred from the current working directory, exactly the same heuristic used by `ontobdc view`) OR 5-arg long form with explicit `--container`.
- Data source: `ContainerEntityInstanceRepository.list_instances(container_path, entity)`
- Response payload: container id/path, resolved entity URI, resolution path, dataset count, datasets list, instance count, and the full instances list.

#### Mode 3.2.4. `--create <instance_name> --entity <TypeName> [--container <id>]` — Create one new entity instance in a container

**Goal** (user perspective): Bootstrapping a new dataset the first time (e.g. creating WorkStream "Reforma Predial 2026"). The command performs the whole entity-instance lifecycle end-to-end in one go:
1. Resolves the entity facade → figure out the correct workbook sheet name, schema, fields.
2. Creates a dedicated dataset folder via `DatasetCreateStateTransitionHandler`.
3. Generates or opens the entity workbook (XLSX) in `payload/document/<uuid>.xlsx` with the correct frictionless fields, primary key, worksheet name matching the entity type.
4. Inserts a blank row with the user-given instance name filled into the appropriate required target field (prefers identifiers marked `:isRequired true` then falls back to the first non-GlobalId text field).
5. Copies the facade `.ttl` and sibling `type.ttl` into the dataset's `linkset/` folder so storage-layer views and checks never need the context machinery.
6. Writes the new entity subject, RDF type, facade conformance, dcterms:identifier/title into the dataset-level graph (`EntityDataset hasDataEntity ...`).
7. Propagates any `obdc:SurfaceableEntity` markers so the Surface engine can pick it up immediately without loading the domain ontology.

- Route: 5 or 7 args depending on whether `--container` is explicit
- Workbook field resolution logic: identifier requirement-map read from the facade ontology (`:isRequired` predicate on field URIs). GlobalId is skipped on the initial pass.
- Dataset naming: `<entity_identifier>-<slugified-instance-name>` (auto-increments a -2, -3 suffix on collision to avoid overwriting)
- Idempotency: UUID-based `instance_identifier` always regenerated, never overwrites existing workbook rows — it just appends.

---

### 3.3. `ontobdc context --container-id <cid> --entity <uri> --import-from <file>` — Import a file into a container as an entity document attachment

**Goal** (user perspective): You have a target container + a concrete entity already inside it. Now you want to attach a file (PDF, Excel, DWG, photo, email...) to that specific entity instance — the file then appears on the entity catalog's "Related documents" list and is tracked through the formal document import state machine (extracted → identified → scored → analysed → published ...).

| Field | Value |
|-------|-------|
| Metadata id | `import` |
| Logical component | `context` |
| Class | `DocumentImportCommand` |
| Implementation file | `ontobdc/src/ontobdc/context/plugin/command/import.py` |
| State machine | `DocumentImportStateTransitionHandler` (context layer) |
| Route | 7-arg fixed form: `context --container-id <cid> --entity <entity_uri> --import-from <file_path>` (all three valued flags must appear — positional permutation allowed as long as they're paired) |
| Usage | `ontobdc context --container-id <cid> --entity <entity_uri> --import-from /abs/path/to/file.ext` |
| `check()` behaviour | validates that container_id is registered (runs `is_container_id_registered` check); resolves container_path via registry; verifies entity_uri and import_from_path were both set; checks the file actually exists on disk before handing to the state machine. |
| Produces | file copied into the container payload, entity↔document DirectedBinaryLink registered, import state machine persisted. |

---

### 3.4. `ontobdc context --entity <entity_uri> --learn-from <file_or_folder>` — Learn an entity profile from one or many PDF examples

**Goal** (user perspective): The built-in Brasidata catalog doesn't cover a niche entity type you need (say, "Laudo de Inspeção Predial de Incêndio"). You have 5 example PDFs of that same document type. Point `--learn-from` at the folder; the workspace will vectorise them and store a reusable profile so `--analyse` and the Surface classification engines can recognise it in the future.

| Field | Value |
|-------|-------|
| Metadata id | `learn_from` |
| Logical component | `context` |
| Class | `ContextLearnFromCommand` |
| Implementation file | `ontobdc/src/ontobdc/context/plugin/command/learning.py` |
| State machine | `EntityLearningStateTransitionHandler` with one persistent step repo per input file. |
| Route | `context --entity <entity_uri> --learn-from <path>` (5 args total; flag order permutable as long as paired) |
| Usage | `ontobdc context --entity urn:onto:custom-fire-report --learn-from ./laudos_incendio_pasta/` |
| Argument validation | entity_uri must contain a colon (valid URI/CURIE). `--learn-from` must point to something that exists after expanduser/resolve. |
| File traversal | If `<path>` is a single PDF file → a single learning run is executed. If it's a directory → recursively (`rglob`) picks up **every `*.pdf` in the tree** and runs learning sequentially on each, aggregating results. Any non-PDF in a folder is silently skipped. Empty folders raise error "No PDF files found". |
| Response content | entity_uri echoed, processed_files count, per-file result list with state machine content per source, or aggregated ExceptionCommandResponse if the pipeline crashed anywhere. |

---

## 4. View component commands

### 4.1. `ontobdc view [--container <id-or-path>] [--type standard] [--representation html] [--language <lang>]` — Generate static HTML Surface and open in browser

**Goal** (user perspective): You have a container with populated datasets and want to look at its visual, browsable surface (the `ontobdc-view` tiles, pages, resource trees, and WorkStream detail views) — this command runs the Surface ETL and opens the resulting `index.html` in the default system browser.

| Field | Value |
|-------|-------|
| Metadata id | `view_generate` |
| Logical component | `view` |
| Class | `ContainerViewCommand` |
| Implementation file | `ontobdc/src/ontobdc/view/plugin/command/view.py` |
| State machine | `SurfaceGenerationStateTransitionHandler` + capabilities (e.g. `DataGatheredCapability`). |
| Route | first arg is `view`. Any number of the valued flags below, each used at most once; their order doesn't matter. The container is optional: if you are `cd`'d inside a container or its child, the command auto-resolves it via `ContainerIdStrategy`. |
| Usage | `ontobdc view`<br>`ontobdc view --container ./meu-projeto`<br>`ontobdc view --container urn:ontobdc:storage/local/<id> --language pt-br`<br>`ontobdc view --type standard --representation html` |

Flags:

| Flag | Valued | Default | Meaning |
|------|--------|---------|---------|
| `--container-id` / `--container` | yes | (auto-resolve from cwd) | select which container to surface. Both forms accept urn:id or filesystem path. |
| `--type` | yes | `standard` | Surface variant. Currently only `"standard"` is supported. |
| `--representation` | yes | `html` | Output format. Currently only `"html"` is supported. |
| `--language` | yes | `en` | Declared language of the view (e.g. en, pt-br). Used by i18n-aware tiles. |

Idempotency behaviour:
- Before starting, deletes any pre-existing `index.html` in the container root (avoids serving a half-generated stale file from an interrupted previous run).
- Wipes the `DATA_GATHERED` ETL state directory before re-entry (forces the Surface ETL to re-run data collection from scratch rather than resume on stale artefacts from a previous call).

Post-generation behaviour:
- If `index.html` was produced:
  1. Builds a `file://` URI (`Path.as_uri()`).
  2. Calls Python's stdlib `webbrowser.open(uri, new=2)` to launch the default browser in a new tab.
  3. Surface response content is extended with: `container_id`, `view_type`, `representation`, `language`, the absolute filesystem `index_path`, the browser `index_uri`, the boolean `browser_opened`, and optional `runtime_error` if the browser could not be started.

---

## 5. Dev component commands

### 5.1. `ontobdc dev <subcommand> [flags]` — Proxy everything to the separate ontobdc-dev workspace CLI

**Goal** (user perspective): The core ontobdc package intentionally ships only production-grade capabilities (storage / context / view / CLI init). Debugging utilities, live HTTP dashboards, local proxy servers, and experimental developer tooling live in a **separate, optional** `ontobdc-dev` package. This thin `dev` entry-point transparently finds that package and forwards the full remaining argv to it — so the CLI surface of ontobdc feels unified even though the implementation is split across two PyPI packages.

| Field | Value |
|-------|-------|
| Metadata id | `dev` |
| Logical component | `dev` |
| Class | `DevProxyCommand` |
| Implementation file | `ontobdc/src/ontobdc/dev/plugin/command/proxy.py` |
| State machine | none — pure process delegation. |
| Route | first arg is `dev`; anything following is forwarded verbatim. |
| Usage | `ontobdc dev --help`<br>`ontobdc dev dashboard`<br>`ontobdc dev proxy --port 8000` |

Dev package discovery strategy (in priority order):
1. **Installed package lookup**: `importlib.util.find_spec("ontobdc_dev")` — if `ontobdc-dev` is pip-installed in the venv, that location is used immediately (both `submodule_search_locations` AND fallback via `__file__` origin path, in case the installed package is laid out as `src/ontobdc_dev/`).
2. **Workspace checkout lookup**: if the package isn't installed, walks up from cwd and from the proxy.py file parent directory searching for either:
   - `<workspace_root>/src/ontobdc_dev/__main__.py` (dev checkout alongside this repo), OR
   - `<workspace_root>/ontobdc-dev/src/ontobdc_dev/__main__.py` (sibling repo checkout).

If neither succeeds, a clear `ModuleNotFoundError` is raised instructing the user to install ontobdc-dev or put its checkout beneath the workspace root.

Execution strategy:
- Inserts the discovered ontobdc-dev `src/` root at position 0 of `PYTHONPATH` (preserving any existing entries) so the forwarded command sees the dev package even when it's not formally pip-installed.
- On **Windows (`os.name == nt`)**: runs via `subprocess.run(...)` and raises `SystemExit(returncode)` (since Windows doesn't support `execvpe`).
- On **POSIX (Linux / macOS)**: uses `os.execvpe(sys.executable, [sys.executable, "-m", "ontobdc_dev", *args], env)` — **replaces the ontobdc Python process in place** so the dev CLI inherits signals, stdio, and the terminal cleanly (no orphan wrapper Python process).

---

## Appendix A. Quick lookup — all 14 commands by usage one-liner

| # | User-facing one-liner | Command id | Component | Purpose |
|---|----------------------|------------|-----------|---------|
| 1 | `ontobdc init` | `init` | cli | create workspace |
| 2 | `ontobdc --version` | `version` | cli | print version |
| 3 | `ontobdc storage --help` | `help` | storage | show storage help |
| 4 | `ontobdc storage --create <container_path>` | `ct_create` | storage | create empty container |
| 5 | `ontobdc storage --container-path <path> --attach` | `container_attach` | storage | attach existing container |
| 6 | `ontobdc storage --update` | `container_update` | storage | refresh container (sync indices + regen Surface) |
| 7 | `ontobdc storage --container-id <id> --update` | same | storage | explicit container form of above |
| 8 | `ontobdc storage --delete <container_id>` | `delete` | storage | deregister container from index |
| 9 | `ontobdc storage --container <sel> --create <ds_path>` | `ds_create` | storage | create dataset inside a container |
| 10 | `ontobdc context --analyse <pdf_path>` | `analyse` | context | classify PDF against entity vectors |
| 11 | `ontobdc context --entity [--all] [--container <c>] [<uri>] [--create name]` | `entity` | context | entity catalog, lookup, list instances, create instance (4 modes) |
| 12 | `ontobdc context --container-id <cid> --entity <uri> --import-from <file>` | `import` | context | attach document file to entity instance |
| 13 | `ontobdc context --entity <uri> --learn-from <pdf_or_folder>` | `learn_from` | context | create / refine an entity classification profile |
| 14 | `ontobdc view [options]` | `view_generate` | view | generate html surface and open in browser |
| 15 | `ontobdc dev <cmd> [args]` | `dev` | dev | forward to ontobdc-dev CLI |
