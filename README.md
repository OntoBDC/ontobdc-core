# OntoBDC

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

OntoBDC is an offline-first semantic runtime for portable datasets and containers. Its annotation subsystem lets any host create, validate, persist, render, query, and navigate typed knowledge attached to files, representations, WorkStreams, and dimensions without requiring a central platform.

## Typed annotations

OntoBDC persists five concrete categories. The abstract enrichment class is never written as if it were a note.

| Category | Purpose | Geometry |
|---|---|---|
| Note | Contextual explanation | one or many points |
| Issue | Problem or question with lifecycle | point, bounding box, or none |
| Classification | Semantic classification by URI | bounding box or none outside a representation |
| Location | Representation, geospatial, relative, or positional location | depends on location kind |
| Record | Evidence such as a photo, document, measurement, or invoice | point, bounding box, or none |

Each annotation separates:

- the annotated target (`oa:hasTarget`);
- the organizing Subjects (`dcterms:subject`);
- creator and modifier;
- assignee, resolver, and recorder roles;
- logical source and visual representation;
- normalized selector geometry.

> **Illustration placeholder — semantic anatomy:** show one annotation connected independently to its target, two Subjects, creator, assignee, WorkStream dimension, logical source, and representation source.

## Editor

The generic editor is category-driven. The host provides labels, theme, actor context, and optional entity resolvers; OntoBDC owns forms, validation, geometry, persistence, and rendering.

The category is selected before category-specific fields and becomes immutable after the first save. Point, multiple-point, and bounding-box tools persist normalized coordinates so the same marker can be restored at the same position.

> **Illustration placeholder — typed editor:** capture the category chooser, an Issue form, geometry toolbar, bounding box, field-level validation, and save action.

## Workspace

The annotation workspace lists spatial and non-spatial annotations and exposes a stable API:

```javascript
workspace.setAnnotations(annotations);
workspace.setFilters({ category, subject, person, workStream });
workspace.selectAnnotation(annotationId);
workspace.clearSelection();
workspace.openAnnotation(annotation);
workspace.refresh();
```

Filters can combine category, controlled kinds/statuses, people and roles, Subject, source, WorkStream, dimension, date, and geometry presence. Counters and legend are derived from the same data and visual contracts used by the renderer.

> **Illustration placeholder — workspace:** show combined category/status/Subject filters, counters, a selected non-spatial Record, details, and the corresponding highlighted marker.

## Subject Page

A Subject is an optional reusable `skos:Concept`; it is not the annotation target. The Subject Page provides three synchronized views:

- **Space:** groups by representation first and only compares normalized geometry inside the same representation;
- **Timeline:** distinguishes creation, modification, recording, status, and resolution events;
- **People:** groups ordinary Person entities by author, modifier, assignee, resolver, and recorder roles.

Annotations without a Subject remain available under **Unassigned subjects**.

> **Illustration placeholder — Subject Page:** three captures of the same Subject in Space, Timeline, and People, including a group without spatial position and a person exercising two roles.

## WorkStream integration

WorkStream is an OntoBDC concept. A host can relate annotations to a WorkStream, one 5W2H dimension, one logical resource, and one representation. Selecting an item in the workspace can reopen its representation and marker; selecting a marker selects the same workspace item.

> **Illustration placeholder — WorkStream flow:** show WorkStream → dimension → resource → representation → annotation, with Subjects and people branching from the annotation.

## Offline persistence

The runtime is designed for local containers and `file://` use:

1. load the strict dataset;
2. calculate its revision;
3. validate the complete next serialization;
4. reject a save if the source changed externally;
5. write through the File System Access API;
6. reopen and verify the written content.

Invalid datasets are reported rather than partially ignored. There is no schema-1 reader, legacy fallback, automatic migration, or automatic RDF merge.

> **Illustration placeholder — persistence flow:** diagram load/revision/edit/validate/compare/write/verify, with the conflict and invalid-dataset stop paths highlighted.

## Host integration

Load the packaged annotation modules in dependency order and create the runtime with host-neutral context:

```javascript
const runtime = OntoBDCAnnotations.createRuntime({
  actorContext: { actorUri: "urn:person:example", displayName: "Example" },
  normalizeContext,
  labels,
  visual: { contract: OntoBDCAnnotationVisualContract, theme }
});
```

The host may implement `entityResolver.search(...)` and `entityResolver.resolve(...)` for people, Subjects, or resources. OntoBDC does not require a database or authentication system.

## Development validation

```bash
python -m pip install -e '.[dev]'
pytest
node --check src/ontobdc/view/plugin/asset/js/annotation/*.js
```

Browser coverage targets Edge/Chromium first because directory access depends on the File System Access API. A release candidate must also validate wheel/ZIP package data, an anonymous demo container, reopen-after-save, offline operation, keyboard navigation, and visual contrast.

## Breaking change

The annotation contract is strict. Existing schema-1 data must be corrected manually. OntoBDC does not interpret `EnrichmentAnnotation` as a Note and provides no legacy property aliases.

Licensed under Apache 2.0.
