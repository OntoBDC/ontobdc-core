# Changelog

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
