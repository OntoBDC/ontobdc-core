# OntoBDC

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> **If you just landed**: OntoBDC is a **local-first semantic runtime that gives
> executable context to portable data and files**, allowing them to be identified,
> related and operated through capabilities without depending on a central
> platform.

OntoBDC turns ordinary folders into **self-describing containers**: each
container carries data, metadata, semantic links (in RDF / JSON-LD / TTL),
validation rules, computational capabilities and instructions for how to render
itself as static HTML.

The architecture is **offline-first** and built on open standards: ICDD ISO 21597
for organizing documents + linksets, OWL/RDF/SKOS for semantics,
`skos:Concept` for Subjects and W3C `oa:Annotation` for annotations.

---

## 3-minute Quickstart

```bash
# 1. Install the package (editable, for development)
pip install ontobdc

# 2. Create a workspace (the "root" where everything is indexed)
mkdir -p ~/my-workspace && cd ~/my-workspace
ontobdc init

# 3. Create a generic container
ontobdc storage --create ~/my-workspace/first-container

# 4. Drop files into the container (PDFs, images, spreadsheets, ...)
#    then refresh its semantic facades:
cd ~/my-workspace/first-container
ontobdc storage --container-id "$(cat .__ontobdc__/container_id 2>/dev/null || echo resolve-by-path)" --update

# 5. Generate a static HTML Surface and open it in the default browser
ontobdc view
```

---

## Core concepts

Before diving in, internalize these 9 terms. They show up across the whole
codebase, tests, documentation and CLI. Hierarchical relationship:

```
OntoBDC Workspace
  └── Storage (global index + registrations)
        ├── Container 1  ← (e.g. one project, one dBriefcase)
        │     ├── Dataset A (document.pdf, photo.png, spreadsheet.xlsx ...)
        │     ├── Dataset B
        │     ├── Linkset (semantic links between datasets)
        │     └── .__ontobdc__/  (container metadata: ontologies, manifests,
        │                         semantic facades, indexes and views)
        └── Container 2 ...
```

### 1. Workspace

The **root directory** where you ran `ontobdc init`. It holds the global index
of every known container. Inside a workspace OntoBDC can:

- list all registered containers;
- cross-relate containers;
- provide the implicit context for parameter strategies (when you `cd` into a
  container folder, its identity is inferred automatically).

A workspace is identified by the hidden `.__ontobdc__/` folder at its root.

### 2. Storage

OntoBDC's **persistence subsystem**. Responsible for:

- registering (`attach`) / unregistering (`delete`) containers in the workspace;
- driving the create (`create`) and update (`update`) lifecycle of containers
  and datasets;
- generating and maintaining "dataset facades": indexed, ready-to-consume
  semantic caches of each dataset inside a container.

Corresponding CLI commands: `ontobdc storage --help`.

### 3. Container

A container is **any self-describing data folder** OntoBDC recognizes.
Formally it satisfies the ICDD ISO 21597 contract:

- It has a `payload_documents/` (or equivalent) folder with the raw files.
- It has a `.__ontobdc__/linkset/` folder containing `.ttl` files of
  `ls:DirectedBinaryLink` (semantic bindings between documents).
- It has manifests and metadata inside `.__ontobdc__/`.

A container is identified by a stable UUID (`container_id`) and a filesystem
location. You can have as many containers as you want registered in a single
workspace.

### 4. Dataset

The smallest **concrete** data unit inside a container:

- a `.pdf` document;
- an inspection `.jpg` photo;
- a budget or schedule `.xlsx` spreadsheet;
- a `.docx` file;
- and so on.

Each dataset has, alongside the original file:

- **metadata** (MIME type, size, hash, semantic type declared by URI);
- a **dataset facade** (processed semantic cache consumed by annotations,
  WorkStreams, views and search).

### 5. Linkset (semantic binding)

Linksets are `.ttl` (RDF Turtle) files inside the canonical
`.__ontobdc__/linkset/` folder that encode **bindings between datasets** using
the standard ICDD ISO 21597 class `ls:DirectedBinaryLink`.

Concrete example from the codebase:

- OntoBDC's WorkStream uses two separate linkset files:
  - `WorkStreamResource.ttl` → "confirmed / related" resources (Related tab).
  - `WorkStreamSuggested.ttl` → suggested / rejected resources, with a full
    audit trail (`obdc:suggestionStatus = Proposed | Rejected`,
    `obdc:suggestionModifiedAt = xsd:dateTimeStamp`).

**Project golden rule**: never use `.__ontobdc__/relation/` or ad-hoc folders.
The canonical structure is ALWAYS `.__ontobdc__/linkset/`.

### 6. dBriefcase — "portable digital briefcase"

A **dBriefcase** is a portable artifact operated by OntoBDC. Think of it as:

> "The dBriefcase is the portable briefcase (transportable via pen-drive /
> QR Code / ZIP / file sharing) that holds all your data, identity, rules,
> events and capabilities. OntoBDC is the program that opens, organizes,
> interprets and uses dBriefcases."

Principles of a dBriefcase:

- **User sovereignty**: no central platform owns it. The user decides what
  enters and what is shared.
- **Self-contained**: carries semantics + presentation together. You reopen
  it 5 years from now without depending on any SaaS.
- **Offline-first**: works on `file://` in the browser via File System Access
  API, no authentication required.
- **Composable**: a person can own a personal dBriefcase, share it via QR
  Code; the recipient creates a private local annotation layer on top of it
  ("the published dBriefcase says who the person is; my local annotation says
  who they are *to me*").

Mental one-liner:
> **OntoBDC = program. dBriefcase = what it carries.**

### 7. dDock — "digital dock" for events

The `dDock` is the **runtime or hardware infrastructure that receives, stores,
persists and delivers events** — with zero domain intelligence. It is proudly
dumb: store-and-forward.

Physical analogy: imagine a docking station you plug your phone into. The dock
does not understand *what* an event means; it only guarantees events arrive,
are stored safely, and are dispatched at the right time to whoever is listening.

Characteristics:

- Does not render UI.
- Does not interpret intent.
- Persists events for replay and audit.
- Can be implemented as:
  1. a **browser** with File System Access API support (universal runtime!);
  2. a BLE/USB/mesh hardware device on the field;
  3. a LAN gateway.

> **Axiom**: *every dDock has a PresentationLayer*. Without presentation the
> events stored inside are invisible to the user.

### 8. PresentationLayer & Presentation Surface

The **PresentationLayer** is the layer that materializes dDock events and
intentions into something perceptible to the user. In OntoBDC the final
materialization is a **Presentation Surface**: a static HTML file (generated
by `ontobdc view`) with tiles, web components, WorkStreams, annotations and
semantic links.

Summary flow:
```
Event / intent  →  dDock (store & forward)  →  Presentation Agent
              →  Tile (web component)  →  Surface layout
              →  User interaction  →  new event flows back to dDock
```

Presentation is fully decoupled from semantics: the same container can have
multiple views (flags `--type standard`, `--representation html`,
`--language pt/en`).

### 9. dWorker — "digital workers" / agents

**dWorkers** are specialized workers that perform bounded work over data and
artifacts. They are an architectural concept of their own and must not be
collapsed into OntoBDC's internal runtime mechanisms.

A dWorker may expose or execute capabilities, but a **capability is not itself
a dWorker**. Likewise, state machines, checks and hotfixes are runtime
mechanisms used to coordinate, validate or repair execution; they are not
synonyms for dWorkers.

The important distinction is responsibility: capabilities describe what can
be done, state machines coordinate transitions, checks validate conditions,
hotfixes repair conditions when possible, and dWorkers are the specialized
workers that actually perform bounded work.

---

## Relationship between the "d-concepts"

```
┌───────────────────────────────────────────────────────────────┐
│                      dBriefcase (data)                        │
│  containers + datasets + linksets + ontologies + rules        │
└───────────────────────┬───────────────────────────────────────┘
                        │ is loaded / operated by
                        ▼
┌───────────────────────────────────────────────────────────────┐
│                      OntoBDC (runtime)                        │
│  CLI, storage, context, view, WorkStreams, annotations        │
└──┬───────────────────────────┬───────────────────────────────┬─┘
   │ events                    │ commands / work               │ events
   ▼                           ▼                               ▼
┌────────┐              ┌──────────────┐              ┌──────────────────────┐
│ dDock  │◀────────────▶│  dWorkers    │─────────────▶│ PresentationLayer /  │
│ store- │  events      │  (workers)   │  outcomes    │ Presentation Surface │
│ forward│              │              │              │  (HTML + tiles)      │
└────────┘              └──────────────┘              └──────────────────────┘
```

---

## What ships out-of-the-box with OntoBDC?

### · Typed annotations (5 categories, strict contract)

| Category | Purpose | Geometry |
|---|---|---|
| **Note** | Contextual explanation | one or many points |
| **Issue** | Problem or question with lifecycle | point, bounding box, or none |
| **Classification** | Semantic classification by URI | bounding box or none outside a representation |
| **Location** | Representation / geospatial / relative / positional location | depends on kind |
| **Record** | Evidence (photo, document, measurement, invoice) | point, bounding box, or none |

Each annotation strictly separates: annotated target (`oa:hasTarget`),
organizing Subjects (`dcterms:subject` as `skos:Concept`), person roles
(creator / modifier / assignee / resolver / recorder), logical source vs.
visual representation, and normalized geometry.

### · Annotation Workspace + Subject Page

The workspace unites spatial and non-spatial annotations with combinable
filters (category, status, person, Subject, WorkStream, dimension, date,
geometry presence), counters and legends all derived from the same visual
contracts.

The **Subject Page** (per-topic page) delivers 3 synchronized views:

- **Space**: groups by representation first.
- **Timeline**: creation, modification, recording, resolution events.
- **People**: groups by the actual role played.

### · Generic WorkStreams

Dimensional organization mechanism (5W2H: what, why, who, when, where, how,
how much) + related resources (Related tab), suggested resources (Suggested
tab — with Proposed/Rejected audit trail) and discovered resources (Found
tab).

### · Presentation Surface generation pipeline (static HTML)

Running `ontobdc view` inside a container the runtime:

1. deletes stale ETL caches for idempotency;
2. assembles the presentation model (`PresentationRepository`);
3. injects domain-registered JS component tiles;
4. runs the generation state machine;
5. opens the resulting `index.html` in the default browser via `webbrowser.open`.

---

## CLI — cheat-sheet (top commands)

Complete user-centric reference with detailed descriptions, guards, response
shapes and examples is cataloged in
[`docs/2026-08-14-cli-command-reference.md`](docs/2026-08-14-cli-command-reference.md)
(14 commands across 5 logical components).

| Intent | Command |
|---|---|
| Initialize workspace | `ontobdc init` |
| Check installed version | `ontobdc --version` \| `-v` |
| Create generic container | `ontobdc storage --create <path>` |
| List registered containers | `ontobdc storage --list` |
| Attach external container | `ontobdc storage --container-path <path> --attach` |
| Re-process container (refresh facades) | `ontobdc storage --container-id <id> --update` |
| Create dataset inside a container | `ontobdc storage --container-id <id> --dataset <name> --create` |
| Deregister a container from the index | `ontobdc storage --delete <container-id>` |
| Analyze / guess entity types inside a file | `ontobdc context --analyse <filepath>` |
| Browse the full entity catalog | `ontobdc context --entity --all` |
| List instances of one entity type | `ontobdc context --container-id <id> --entity <URI>` |
| Create a new entity instance | `ontobdc context --create "Name" --entity <URI> --container-id <id>` |
| Learn an entity profile from reference files | `ontobdc context --learn-from <folder_or_zip> --entity <URI>` |
| Import PDF / document into a container | `ontobdc context --import-from <filepath> --container-id <id>` |
| Generate Surface + open in browser | `ontobdc view` (in container) or with `--container-id <id>` |
| Delegate everything else to standalone dev CLI | `ontobdc dev <anything>` |

---

## High-level code structure

```
ontobdc/ (this package)
├── src/ontobdc/
│   ├── cli/            → entry-point, CommandLoader, argument routing
│   ├── storage/        → containers, datasets, manifests, facades, storage index
│   ├── context/        → entities, workbooks, file analysis, imports, learn
│   ├── view/           → HTML Surface generation, tiles, annotations UI
│   ├── dev/            → proxy onto the separate ontobdc-dev package
│   ├── shared/         → central adapters (ontology adapter, paths, config)
│   └── domain/         → models, value objects, ports, requests, responses, exceptions
├── tests/              → mirrors src/ package structure; part of the specification
└── docs/               → architecture & reference documentation
```

---

## Development

```bash
# install with dev extras
pip install ontobdc[dev]

# run full test suite
pytest

# JS syntax check (mandatory for any change in browser-side view assets)
node --check src/ontobdc/view/plugin/asset/js/**/*.js
```

Release validation targets: wheel/ZIP with proper package data, Surface opening
offline via `file://`, annotation save-reopen with no regression, keyboard
focus and visual contrast.

---

## Related documentation (inside this package)

| Title | Path |
|---|---|
| Presentation-layer technical debt audit report | [docs/2026-08-13-presentation-technical-debt-audit.md](docs/2026-08-13-presentation-technical-debt-audit.md) |
| Complete CLI reference (14 commands, 5 components) | [docs/2026-08-14-cli-command-reference.md](docs/2026-08-14-cli-command-reference.md) |
| AI agent rules — exhaustive architectural contract for contributors | [docs/AGENTS.md](docs/AGENTS.md) |

---

## License

[Apache License 2.0](LICENSE).
