# AGENTS.md — OntoBDC

This file defines how AI coding agents must work in this repository. It applies to the entire repository unless a more specific `AGENTS.md` exists in a subdirectory.

## 1. Project identity

OntoBDC is an **offline-first semantic runtime for portable datasets and containers**. It is not a conventional CRUD application and must not be treated as one.

The project combines:

- deterministic semantic data processing;
- RDF/JSON-LD and controlled vocabularies;
- validation and constraints;
- portable, self-contained datasets and containers;
- dynamically discovered commands, capabilities, checks, hotfixes, and parameter strategies;
- local HTML views that must work without a central platform;
- CLI execution and browser-side interaction;
- strict typed annotations attached to resources, representations, WorkStreams, and dimensions.

The core architectural objective is **data with executable context**: the dataset/container carries enough semantics, metadata, rules, and capabilities to be understood and processed independently.

## 2. Branch and release discipline

- The active development branch for this file is `v0.14`.
- `v0.13` is a released line and must not receive new development changes unless explicitly instructed.
- Do not modify `master`, another release branch, or `ontobdc-core` unless explicitly instructed.
- Do not merge, rebase, tag, publish, or open a pull request unless explicitly requested.
- Keep changes narrowly scoped to the requested behavior.
- Do not mix opportunistic cleanup with a functional change.
- Preserve backward compatibility only when the current contract explicitly requires it. Do not invent compatibility layers.
- Before changing a public contract, identify all tests, serializers, loaders, views, and package-data rules affected by that contract.

## 3. Sources of truth

Before making changes, inspect the relevant source and tests. In order of precedence:

1. explicit user instruction;
2. the current branch implementation and tests;
3. this `AGENTS.md`;
4. `README.md`, `pyproject.toml`, and repository documentation;
5. inferred behavior.

Never replace repository behavior with generic framework conventions merely because they are more familiar.

When the code and documentation disagree, do not silently choose one. State the conflict and make the smallest change that satisfies the explicit task.

## 4. Repository architecture

The Python package is under `src/ontobdc` and follows a port/adapter/plugin-oriented structure. Common layers include:

- `domain/`: models, value objects, requests, responses, exceptions, and ports;
- `facade/`: stable contracts exposed across logical components;
- `adapter/`: concrete implementations of ports and external integration;
- `plugin/`: dynamically discovered commands, capabilities, checks, hotfixes, renderers, and parameter strategies;
- `module/`: optional logical modules discovered by the same plugin mechanisms;
- `shared/`: cross-cutting contracts and reusable infrastructure;
- `cli/`: command discovery, argument resolution, execution, logging, prompting, and response rendering;
- `context/`: semantic context and entity instance access;
- `storage/`: container and dataset storage, manifests, indexes, metadata, and filesystem behavior;
- `view/`: HTML generation, browser assets, response renderers, dataset views, and annotation UI;
- `tests/`: mirrors the package responsibilities and is part of the specification.

Do not collapse these boundaries into a monolithic service. Add behavior at the correct layer.

### Dependency direction

- Domain contracts must not depend on adapters, UI code, filesystem details, or concrete plugin implementations.
- Adapters implement ports; ports must not import adapters.
- Plugins may compose ports and adapters but should expose stable metadata and deterministic behavior.
- Shared code must remain genuinely cross-cutting. Do not move feature-specific logic into `shared` merely to avoid choosing a bounded context.
- Browser assets must not become the authoritative source of semantic truth.

## 5. Plugin discovery rules

OntoBDC discovers plugins dynamically. Discovery scans logical components and modules for resource directories such as `plugin/capability`, `plugin/command`, and `plugin/parameter`.

When adding or moving a plugin:

- preserve package discovery and importability;
- provide the required metadata object and stable ID/name;
- follow the existing base class or port;
- ensure the class is discoverable without manual registration unless the current subsystem explicitly uses registration;
- avoid import-time side effects;
- do not catch and suppress errors that should make an invalid plugin visible;
- test discovery, not only direct instantiation;
- include all required files in package data.

A class that works only when imported directly but cannot be found by the loader is incomplete.

## 6. CLI contract

The CLI entry point is `ontobdc.cli:main`.

Preserve these behaviors:

- render modes: rich, JSON, and HTML;
- silent mode via `--silent` or `-s`;
- command-specific metadata and valued arguments;
- parameter strategies applied only to required parameters;
- structured `CommandResponse` objects;
- non-zero exit status for failed execution;
- logging selected according to render strategy;
- prompts injected through ports rather than hard-coded throughout the domain.

Rules for CLI changes:

- do not print arbitrary output from domain code;
- use the response and logging abstractions already present;
- maintain JSON output as machine-readable JSON without human logging noise;
- do not turn all internal exceptions into the generic `Invalid command arguments` message;
- preserve the original cause when translating exceptions at a boundary;
- add tests for each capability or command path involved, not only a single end-to-end happy path;
- validate Windows path behavior when filesystem paths are involved.

## 7. Semantic and data-model rules

OntoBDC is semantic-first. Treat URIs, RDF classes, predicates, shapes, linksets, facades, and manifests as contracts—not decorative metadata.

### General rules

- Reuse established project vocabularies and existing namespaces.
- Do not create a new predicate when an existing project or standard predicate already represents the concept.
- Keep identifiers stable and deterministic where the project contract requires determinism.
- Do not use display labels as identifiers.
- Do not infer identity from filenames alone.
- Preserve the distinction between TBox/schema resources and ABox/instance resources.
- Keep resource identity independent from visual representation.
- Validate complete semantic output before replacing valid persisted state.
- Reject invalid datasets explicitly; do not partially ignore malformed triples or records.
- Do not add silent schema migration, legacy aliases, or RDF merge behavior unless explicitly requested.
- Keep serializers deterministic so tests, hashes, revisions, and portable packages remain reproducible.

### Containers and datasets

- Treat the hidden `.__ontobdc__` structure as runtime metadata, not an arbitrary cache.
- Do not duplicate authoritative metadata in multiple files without an explicit synchronization contract.
- Maintain container/dataset manifests, storage indexes, facades, linksets, and package descriptors coherently.
- A dataset feature is not complete if it works only in the source checkout but fails in an installed wheel or ZIP distribution.
- Generated views must reflect real serialized data. Hard-coded data is permitted only for a clearly identified mock/prototype and must not masquerade as runtime behavior.

## 8. Current annotation contract

The strict annotation contract introduced in v0.13 remains authoritative in v0.14 unless the current task explicitly changes it.

### Concrete annotation categories

Only these concrete categories are persisted:

1. `Note` — contextual explanation;
2. `Issue` — problem or question with lifecycle;
3. `Classification` — semantic classification by URI;
4. `Location` — representation, geospatial, relative, or positional location;
5. `Record` — evidence such as a photo, document, measurement, or invoice.

The abstract enrichment class is **not** a concrete note and must never be serialized as one.

### Required conceptual separations

Keep these concepts independent:

- annotated target (`oa:hasTarget`);
- organizing Subject (`dcterms:subject`), represented as an optional reusable `skos:Concept`;
- creator and modifier;
- assignee, resolver, and recorder roles;
- logical source and visual representation;
- annotation category, controlled kind, and lifecycle status;
- normalized selector geometry.

A Subject is not the target. A representation is not the logical resource. A person role is not interchangeable with authorship.

### Editing and persistence

- Category is selected before category-specific fields.
- Category becomes immutable after the first save.
- Point, multiple-point, and bounding-box selectors use normalized coordinates.
- Persist enough context to restore a marker in the same representation and position.
- Validate the complete next serialization before writing.
- Detect external source revision changes and reject conflicting saves.
- Write through the supported local filesystem flow and reopen/verify persisted content.
- Do not introduce a schema-1 reader, automatic migration, legacy fallback, or property aliases unless explicitly requested.

### Workspace and Subject Page

The annotation workspace must keep spatial and non-spatial annotations in one coherent data model. Its public behavior includes setting annotations, applying filters, selecting/opening annotations, clearing selection, and refreshing.

Filters, counters, legends, markers, and detail panels must derive from the same semantic and visual contracts.

The Subject Page has synchronized views:

- **Space**: group by representation first; compare normalized geometry only within the same representation;
- **Timeline**: distinguish creation, modification, recording, status, and resolution events;
- **People**: group ordinary Person entities by their actual roles;
- annotations without a Subject remain accessible under an unassigned grouping.

Do not group spatial coordinates from unrelated representations as if they shared a coordinate system.

## 9. Views and browser assets

The view subsystem must support local/offline use and `file://` execution where intended.

- Prefer plain browser-compatible JavaScript consistent with the existing assets.
- Do not introduce a framework, bundler, package manager, or remote CDN dependency without explicit approval.
- Preserve script dependency order.
- Avoid network requirements for core interaction.
- Keep semantic data embedded or packaged in a form that can be read locally.
- Use stable instance IDs in generated filenames and links when the current contract requires instance identity.
- Views must consume serialized facades/JSON-LD rather than scrape presentation text.
- Navigation must remain within the portable package unless an external link is intentional.
- Support keyboard navigation and visible focus.
- Preserve acceptable contrast and readable responsive behavior.
- Do not remove Saturday or Sunday from calendar logic unless the business rule explicitly calls for business days.

For JavaScript changes, run syntax checks for every modified file:

```bash
node --check path/to/file.js
```

For the annotation asset tree:

```bash
node --check src/ontobdc/view/plugin/asset/js/annotation/*.js
```

## 10. Python implementation rules

- Python requirement: 3.10 or newer.
- Use type hints for new or materially changed public functions.
- Follow the existing naming and module layout.
- Prefer small functions and explicit contracts over hidden global state.
- Use ports for external behavior and adapters for concrete implementations.
- Preserve meaningful exception types.
- Do not use broad `except Exception: pass` in new code.
- Do not add dead compatibility branches, commented-out replacements, or duplicate implementations.
- Avoid unnecessary dependencies. Adding a dependency requires explicit justification and package/distribution validation.
- Do not mutate caller-owned collections unexpectedly.
- Keep filesystem operations deterministic and testable.
- Account for Windows paths and PowerShell usage as first-class scenarios.

## 11. Testing requirements

Install development dependencies with:

```bash
python -m pip install -e '.[dev]'
```

Run the full test suite with:

```bash
pytest
```

For a focused change, run targeted tests first, then the relevant broader suite, then the full suite when feasible.

Minimum testing expectations by change type:

- command change: command discovery, argument validation, response rendering, and failure path;
- capability change: direct behavior, loader discovery, state transition, and integration path;
- context/storage change: valid state, missing state, malformed state, path resolution, and concurrency/revision behavior;
- semantic change: serialization, parsing, validation, round trip, deterministic output, and invalid input rejection;
- view change: generation test, packaged asset presence, JavaScript syntax, data binding, and local navigation;
- annotation change: all five categories where applicable, geometry variants, non-spatial entries, role separation, Subject behavior, save/reopen, and conflict rejection;
- package change: wheel/ZIP contents and installed execution, not only editable-install execution.

Do not weaken a test merely to match a regression. Fix the implementation or document the intentional contract change.

## 12. Packaging and release validation

`pyproject.toml` defines package data and the CLI entry point. When adding non-Python assets:

- verify they are included by setuptools package-data rules;
- test from an installed wheel or equivalent clean environment;
- do not rely on files that exist only in the repository root;
- preserve the ability to distribute an anonymous demonstration container;
- verify offline operation after installation;
- ensure the version and release branch remain coherent when explicitly preparing a release.

A feature that disappears from the wheel is not done.

## 13. Change workflow for AI agents

Before editing:

1. confirm the current repository and branch;
2. read this file and any closer `AGENTS.md`;
3. inspect the implementation, tests, and relevant semantic assets;
4. identify public contracts and generated/package artifacts affected;
5. state assumptions only when they cannot be resolved from the repository.

While editing:

1. make the smallest coherent change;
2. keep architecture boundaries intact;
3. add or update tests in the same change;
4. avoid unrelated formatting churn;
5. preserve deterministic output;
6. do not fabricate data, identifiers, ontologies, or business rules;
7. do not silently replace real data with mocks.

After editing:

1. run targeted tests;
2. run JavaScript syntax checks when applicable;
3. run the full Python test suite when feasible;
4. inspect the diff for generated noise, secrets, absolute local paths, and accidental binary files;
5. report exactly what changed, what was tested, and what remains uncertain.

## 14. Prohibited actions

Unless explicitly requested, do not:

- push changes to `master`;
- modify `ontobdc-core`;
- merge branches or publish releases;
- rewrite history;
- commit credentials, tokens, personal data, private client data, or machine-specific paths;
- add telemetry or cloud-only dependencies;
- introduce a database or server requirement for an offline feature;
- replace semantic contracts with ad hoc JSON objects;
- create silent legacy fallbacks;
- swallow validation failures;
- bypass plugin loaders with hard-coded registrations;
- duplicate source-of-truth metadata across files;
- use a UI mock as proof that persistence or semantic integration works;
- remove tests because the implementation is difficult to fix.

## 15. Definition of done

A change is complete only when:

- the requested behavior is implemented in the correct architectural layer;
- semantic identity and validation rules are preserved;
- discovery and packaging still work;
- relevant tests pass;
- browser assets pass syntax checks where applicable;
- offline/local behavior remains functional;
- errors are specific enough to diagnose;
- documentation is updated when a public contract changes;
- no unrelated changes are included;
- the agent reports any untested environment or unresolved risk honestly.

## 16. Communication style

Be literal and operational.

- Distinguish observed repository facts from inference.
- Do not claim success without verifying the resulting branch/file/test state.
- Do not hide failures behind optimistic summaries.
- When a task is underspecified, inspect the repository before asking a question.
- Ask only when a decision cannot be recovered from existing code, tests, documentation, or branch history.
