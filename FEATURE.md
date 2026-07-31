---
feature: Navigable PDF WorkStream Publication
feature_id: navigable-pdf-publication
repository: OntoBDC/ontobdc-core
component_role: Generic container publication runtime, provenance, filtering and export orchestration
source_version: 0.11.0
source_branch: master
source_commit: 366bb665a9ee929ed16d173bd9e1818b8102bbb5
feature_branch: feat/navigable-pdf-publication
target_version: TBD
status: planning
created_at: 2026-07-31
related_repository: InfoBIM-Community/infobim-core
related_source_version: 0.3.0
related_feature_branch: feat/navigable-pdf-publication
---

# Navigable PDF WorkStream Publication

## 1. Summary

This feature introduces a publication layer that transforms a live OntoBDC/InfoBIM container into a filtered, navigable, portable and verifiable PDF snapshot.

The PDF is not the source of truth and is not intended to replace the live container. It is a derived publication artifact created for a specific audience, purpose and point in time.

The central idea is:

```text
Live WorkStream container
        ↓
Publication profile + audience + source revision
        ↓
Content selection, rendering and provenance capture
        ↓
Navigable PDF publication
```

The resulting PDF must be usable without granting the recipient access to the engineering OneDrive, the internal project folder, the InfoBIM runtime or the live WorkStream.

## 2. Problem and motivation

The immediate operational need is to share WorkStream information with recipients who cannot access the internal engineering information environment:

- a contractor outside the client organization;
- a client user inside the organization but without access to the engineering OneDrive;
- any external recipient who needs a controlled deliverable but must not receive the complete live WorkStream.

Existing approaches create unnecessary friction:

- requesting external accounts or temporary permissions;
- exposing an internal folder structure;
- sharing isolated files with no context or navigation;
- manually assembling project packages;
- duplicating and reorganizing information outside the source container;
- requiring installation, login, server access or training.

A PDF is already accepted as a normal engineering deliverable. Making it navigable allows the structured intelligence of the WorkStream to be published without presenting the recipient with a new platform.

## 3. Primary use cases

### 3.1 Executive project publication for a contractor

Generate a controlled PDF containing only the information required for execution, such as:

- current executive drawings and details;
- applicable scope;
- released areas;
- execution-relevant constraints and pending items;
- approved instructions;
- selected photos and evidence;
- links between locations, activities, drawings and documents.

Internal discussions, costs, private notes and unauthorized documents must remain excluded.

### 3.2 Databook publication for the client

Generate a navigable databook containing the final or approved project record, such as:

- final documents and drawings;
- revisions and approvals;
- inspections and checklists;
- photographic records;
- certificates;
- as-built information;
- activity and evidence timelines;
- traceability between location, activity, document and evidence.

### 3.3 Periodic publication

The same publication command may be executed automatically at defined intervals, for example:

- every day during a critical execution phase;
- weekly for contractor coordination;
- monthly for client reporting;
- at each formal revision or milestone;
- after a WorkStream reaches a publishable state.

The initial implementation should expose a deterministic command that can be called by Windows Task Scheduler, cron, CI or another external scheduler. A permanent internal daemon is not required for the MVP.

## 4. Product concept

The PDF is the publication interface of the WorkStream.

The architecture separates:

- **live operational source:** the OntoBDC/InfoBIM container;
- **publication rules:** profile, audience, filters and template;
- **published deliverable:** the generated PDF;
- **publication event:** who generated it, when, from which source state and for which purpose.

This gives the system a clean distinction between internal operation and external delivery.

## 5. Core principles

### 5.1 Container remains the source of truth

The PDF is always derived. Corrections must be made in the container and followed by a new publication. The generated PDF must never become the authoritative editable source.

### 5.2 Audience-specific publication

A publication must include only the information authorized and useful for its intended recipient.

The same WorkStream may produce different artifacts from the same source state:

```text
WorkStream revision X
    ├── contractor executive-project PDF
    ├── client databook PDF
    ├── internal coordination PDF
    └── management summary PDF
```

### 5.3 Static and portable by default

The baseline output must work offline and without scripts, plugins or application-specific runtime behavior.

### 5.4 Verifiable snapshot

A PDF file is not technically impossible to modify. Therefore, the feature must provide tamper evidence and provenance rather than relying on a vague claim of intrinsic immutability.

At minimum, each publication must record:

- publication identifier;
- source container identifier;
- source container revision or snapshot identifier;
- source container hash;
- publication profile;
- audience;
- generation timestamp;
- generator name and version;
- list or manifest of included resources;
- hash of the generated PDF, stored outside the PDF in the publication record.

Optional later support may include digital signatures, trusted timestamps and content-addressed storage.

### 5.5 Deterministic regeneration

Given the same source snapshot, profile, template and generator version, the system should produce functionally equivalent content. Byte-for-byte reproducibility is desirable but not mandatory for the first implementation because PDF metadata and rendering libraries may introduce nondeterministic values.

### 5.6 Conservative PDF compatibility

The primary navigation model must use broadly supported PDF features:

- bookmarks;
- internal page links;
- clickable table of contents;
- standard HTTP/HTTPS links;
- searchable text;
- visible navigation controls;
- static images and vector content.

JavaScript, embedded executable content, automatic local file opening and advanced multimedia must not be required.

## 6. Expected navigation model

A publication may contain the following sections:

1. Cover and publication metadata.
2. Executive dashboard or summary.
3. Navigation by area or location.
4. Navigation by subject or discipline.
5. Navigation by date or timeline.
6. Navigation by person or responsible party.
7. Drawings or plans with clickable hotspots.
8. WorkStream item or occurrence pages.
9. Evidence pages.
10. Documents and references.
11. Traceability and publication manifest.

Each detailed page should provide consistent navigation controls where applicable:

```text
Home | Back to plan | Previous | Next | Open evidence
```

The PDF may simulate prepared views and filters by generating separate indexed sections. It is not expected to support arbitrary live queries.

## 7. Publication profiles

A publication profile defines what is selected and how it is rendered.

Conceptual profile fields:

```yaml
id: executive-project
name: Executive Project for Contractor
audience: contractor
workstream_selector: infrastructure
include:
  entity_types: []
  states: []
  relationships: []
  document_categories: []
  evidence_categories: []
exclude:
  visibility: [internal, confidential]
  document_categories: [commercial, cost, internal_discussion]
navigation:
  by_area: true
  by_subject: true
  by_date: true
  by_person: false
  plan_hotspots: true
rendering:
  template: executive-project
  include_manifest: true
  include_qr_codes: false
```

Profiles must be declarative and versionable. They should not hard-code one project structure into the generic runtime.

Initial domain profiles are expected to be defined by InfoBIM:

- `executive-project`;
- `databook`.

OntoBDC should provide the generic profile loading, validation, selection, provenance and publication execution mechanisms.

## 8. Proposed command surface

The exact CLI syntax remains open, but the generic capability should support a flow equivalent to:

```bash
ontobdc run \
  --id publish_navigable_pdf \
  --dataset <container-or-dataset-id> \
  --profile <profile-file-or-id> \
  --output <publication.pdf>
```

InfoBIM is expected to expose the domain-oriented command, for example:

```bash
infobim publish workstream <workstream-id> \
  --profile executive-project \
  --audience contractor \
  --output project-executive-r07.pdf
```

and:

```bash
infobim publish workstream <workstream-id> \
  --profile databook \
  --audience client \
  --output databook-r03.pdf
```

## 9. OntoBDC responsibilities

This repository owns the generic runtime concerns.

### 9.1 Container and dataset resolution

- resolve the target container or registered dataset;
- read the RO-Crate and OntoBDC project metadata first;
- resolve only the resources required by the publication profile;
- preserve relationships and source identifiers during selection.

### 9.2 Publication profile infrastructure

- define or validate the generic publication-profile schema;
- load profiles from local files, container resources or registered modules;
- validate required fields and supported options;
- expose profile version and identity in provenance.

### 9.3 Selection and filtering

- select entities and resources by semantic type, state, relationship and category;
- enforce explicit exclusions;
- support visibility or confidentiality classifications when present;
- fail safely when access classification is ambiguous under a restrictive profile;
- produce an auditable list of included and excluded resources.

### 9.4 Publication snapshot

- identify or create the source snapshot used for publication;
- calculate the source container or relevant manifest hash;
- capture source revision information;
- create a publication record before or during generation;
- link the output artifact to its source snapshot.

### 9.5 Generic rendering pipeline

OntoBDC should orchestrate a rendering pipeline without owning all domain presentation rules.

Conceptual stages:

```text
resolve source
    ↓
validate profile
    ↓
select resources
    ↓
build publication model
    ↓
render pages
    ↓
create internal links and bookmarks
    ↓
write provenance and manifest
    ↓
calculate output hash
    ↓
register publication result
```

### 9.6 Publication record

A publication record should be materialized as structured data, for example JSON-LD, Turtle or JSON, and contain at least:

```yaml
publication_id: <id>
source_container_id: <id>
source_snapshot_id: <id>
source_hash: <sha256>
profile_id: <id>
profile_version: <version>
audience: <audience>
generated_at: <timestamp>
generator:
  name: ontobdc
  version: <version>
output:
  file: <name>
  media_type: application/pdf
  sha256: <hash>
included_resources: []
excluded_resource_summary: {}
```

The external record is important because the PDF cannot reliably contain its own final hash before the file is completed.

### 9.7 Automation compatibility

- command must be non-interactive when all required parameters are provided;
- exit codes must distinguish success, validation failure, missing resource and rendering failure;
- output naming may support timestamp, revision and profile placeholders;
- repeated scheduled executions must not silently overwrite a formally published revision unless explicitly allowed;
- logs and publication records must make periodic exports auditable.

## 10. InfoBIM responsibilities

The related InfoBIM branch owns the domain-specific interpretation and user-facing behavior:

- resolve WorkStreams and their 5W2H structure;
- define executive-project and databook publication profiles;
- map areas, subjects, people, dates, annotations, documents, photos, drawings and IFC-related information into publication sections;
- generate engineering-specific page layouts;
- create plan and drawing hotspots;
- define the `infobim publish workstream` CLI;
- provide user-facing validation messages and templates.

OntoBDC must remain usable as a generic publication runtime without embedding InfoBIM-specific assumptions in its core.

## 11. Packaging strategies

### 11.1 Single self-contained PDF

Preferred when portability and simple delivery matter most.

Possible contents:

- full navigation structure;
- essential images and evidence;
- selected drawings;
- publication manifest summary.

Advantages:

- one file;
- works offline;
- easy to email, archive and protocol;
- no broken relative paths.

Disadvantages:

- may become large;
- embedded attachments are not equally supported by all viewers.

### 11.2 PDF plus controlled payload package

Possible package:

```text
publication-package/
├── index.pdf
├── manifest.json
├── evidence/
├── drawings/
└── documents/
```

The package may itself be delivered as a ZIP or container snapshot.

Advantages:

- large evidence remains outside the PDF;
- files retain native format;
- lighter PDF.

Disadvantages:

- relative links may be blocked or broken;
- package structure must remain intact;
- SharePoint or email may separate the files.

The MVP should prioritize a self-contained PDF and treat external-payload packages as an optional mode.

## 12. Security and disclosure control

Publication is a disclosure operation. The feature must assume that the output may leave the internal organization.

Required safeguards:

- explicit audience in every profile or command;
- default-deny behavior for information classified as internal or confidential;
- preview or dry-run summary before formal release;
- manifest of included resources;
- warnings for unresolved visibility classification;
- no automatic inclusion of every referenced file merely because it is reachable;
- no hidden internal annotations in rendered layers or metadata;
- removal or control of sensitive PDF metadata;
- optional redaction or omission rules for future implementation.

## 13. Advantages

- avoids granting external access to internal repositories or OneDrive;
- delivers a familiar engineering artifact instead of requiring platform adoption;
- works offline;
- preserves structured navigation and context;
- provides a formal snapshot for contractual or audit purposes;
- supports different outputs for different audiences from one source;
- can be regenerated and automated;
- creates a traceable link between live information and delivered artifact;
- can be printed while retaining a richer digital navigation experience;
- reduces manual assembly of executive packages and databooks.

## 14. Disadvantages and limitations

- the PDF is static and must be regenerated after source changes;
- arbitrary live semantic queries are not available inside the PDF;
- large drawings, photos and evidence may create very large files;
- PDF viewer support varies;
- local relative links and embedded attachments may be blocked;
- collaboration and concurrent editing are outside the PDF model;
- comments added by recipients create divergent copies;
- strong tamper resistance requires hashes, controlled storage or digital signatures;
- accessibility requires deliberate indexes, reading order and textual alternatives to visual hotspots;
- advanced PDF JavaScript, 3D and multimedia are unsuitable as baseline dependencies;
- archival PDF standards may restrict active features.

## 15. Compatibility tiers

### Tier 1 — Baseline portable publication

Required for MVP:

- internal links;
- bookmarks;
- table of contents;
- searchable text;
- static drawings and images;
- standard URLs;
- provenance page;
- publication identifier and source hash reference.

### Tier 2 — Enhanced controlled publication

Optional:

- QR codes;
- embedded attachments;
- layers where supported;
- external package links;
- digital signature;
- trusted timestamp.

### Tier 3 — Viewer-specific experiments

Not part of the dependable baseline:

- JavaScript;
- 3D PDF;
- multimedia;
- automatic external file execution;
- complex interactive forms.

## 16. MVP scope

The first usable implementation should provide:

1. Publication of one selected WorkStream.
2. Declarative profile loading and validation.
3. Two InfoBIM profiles: executive project and databook.
4. Audience-based inclusion and exclusion.
5. Clickable table of contents and bookmarks.
6. Internal navigation between summary, location, item and evidence pages.
7. Static plan or drawing image with clickable hotspots when coordinates are available.
8. Publication metadata page.
9. Source snapshot/hash reference.
10. External publication record with PDF hash and included-resource manifest.
11. Non-interactive CLI execution suitable for scheduling.
12. No required JavaScript or online service.

## 17. Non-goals for the first iteration

- executing OntoBDC inside the PDF;
- replacing the live InfoBIM interface;
- arbitrary user-defined queries inside the PDF;
- real-time synchronization after publication;
- collaborative task management in the PDF;
- universal support for every PDF viewer feature;
- a full document-signing infrastructure;
- embedding every source file by default;
- internal scheduler or cloud service as a mandatory dependency.

## 18. Acceptance criteria

The feature is ready for an initial release when all of the following are true:

- a WorkStream can be published from a command without manually assembling pages;
- the source container remains unchanged except for intentional publication records;
- the output can be opened offline in at least Adobe Reader and a mainstream browser PDF viewer;
- table of contents, bookmarks and internal links work in the supported viewers;
- a contractor profile excludes resources classified as internal;
- a client databook profile produces a different selection from the same WorkStream;
- the PDF identifies its publication ID, source state, profile and generation date;
- an external record stores the final PDF SHA-256 hash;
- included resources can be traced back to source identifiers;
- a scheduled non-interactive invocation can generate a revisioned output without user prompts;
- generation failures return a non-zero exit code and leave an intelligible log.

## 19. Testing strategy

### Unit tests

- publication-profile validation;
- include/exclude rule evaluation;
- deterministic ordering;
- publication identifier and filename generation;
- hash calculation;
- manifest generation;
- safe handling of missing resources.

### Integration tests

- load a sample container and publish a complete PDF;
- verify internal destinations and links;
- verify bookmarks and page references;
- verify contractor/client selection differences;
- verify that excluded information is absent from extracted PDF text and metadata;
- verify publication record linkage and hashes;
- run the command twice under scheduled-mode options.

### Manual compatibility tests

- Adobe Acrobat Reader on Windows;
- browser PDF viewer on Windows;
- at least one mobile viewer;
- printing selected sections;
- opening without network access.

## 20. Open decisions

The following decisions remain intentionally open:

- rendering engine and libraries;
- exact publication-profile ontology or schema;
- whether the publication record is JSON-LD, Turtle, JSON or multiple serializations;
- exact definition of source hash for containers with external resources;
- whether attachments are enabled in the initial release;
- whether QR codes point to a live InfoBIM view, a package location or a verification endpoint;
- supported digital-signature mechanism;
- handling of very large drawings and photo collections;
- whether publication snapshots are copied, content-addressed or represented only by manifests;
- target OntoBDC and InfoBIM release versions.

## 21. Initial implementation sequence

1. Define the generic publication profile structure.
2. Define the publication record and provenance model.
3. Build resource selection and exclusion reporting.
4. Build an intermediate publication model independent of the PDF library.
5. Select and validate a PDF rendering engine.
6. Implement baseline page, bookmark and internal-link generation.
7. Integrate InfoBIM WorkStream mapping and templates.
8. Implement plan hotspots.
9. Add final hash registration and manifest output.
10. Add CLI automation behavior and tests.
11. Validate executive-project and databook outputs with a real WorkStream.

## 22. Design statement

OntoBDC operates and preserves the structured source. InfoBIM interprets the engineering WorkStream. The navigable PDF is a controlled publication of that state: familiar enough to cross organizational boundaries, rich enough to preserve context, and verifiable enough to serve as a formal project deliverable.
