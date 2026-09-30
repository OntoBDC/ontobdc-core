# CLI end-to-end tests

Run from the OntoBDC repository, using the virtual environment containing the
installed `ontobdc` entrypoint, runtime dependencies and pytest:

```sh
PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e
```

The explicit source path makes subprocesses exercise this checkout even when
the environment's editable installation points to a different worktree.
The runner resolves the real executable next to the current Python interpreter
and always adds `--json`. These tests do not exercise terminal formatting.

## Isolation and setup

Each test uses pytest's temporary directory. CLI calls run in an isolated
storage root or its selected container, never in the developer's Project.
There are no mocked commands, mocked capabilities, skipped cases or expected
failures in the new command coverage.

`ContainerE2eWorkspace` initializes the temporary root through the CLI, then
prepares container metadata, its storage index, Data Package and RO-Crate with
the existing standalone hotfixes. This is deliberate fixture construction, not
a fallback after a failed creation command. The tested operations still go
through the actual CLI subprocess, parameter resolution and production handlers.
The independent setup lets their tests run even when `container --create` is
broken; existing creation tests remain unchanged.

## Added command coverage

- `container --attach`: imported containers moved between storage roots,
  implicit selection and both path flags, identity and user-file preservation,
  manifest refresh, repeated attachment, missing paths and invalid arguments.
- `container --delete`: URN and bare-UUID selection, unregistering only the
  selected entry, preserving all user files, unknown/empty IDs and routing errors.
- `container --health`: current-directory, ID and path selection, healthy and
  stale manifests, no automatic repair and invalid/missing selectors.
- `container --refresh`: the three selectors, added and removed files, Data
  Package/RO-Crate synchronization, stray-file cleanup and repeated execution.
- `container --create-dataset`: ID/path selection, title and slug, persisted
  RDF ownership and indexing, duplicate protection and invalid arguments.
- `run --capability`: a real read-only health capability and a real manifest
  transformation, container selectors, unknown IDs and missing arguments.
- `run --tag`: supported separators, stable deduplication, invalid inputs and
  the explicit unavailability response returned by the current implementation.

## Response contracts and validation history

Several handlers return a structured error response without raising an
exception. Consequently, an exit code of zero alone does not establish domain
success. Tests also assert response titles, error fields, health status and
filesystem effects. In particular, `run --tag` currently returns
`Tag Run Not Available`; the tests do not claim that tagged capabilities run.
Deletion with unknown/empty identifiers likewise returns a failure response
with exit code zero. Argument-routing errors raise an exception and exit one.

During validation on 2026-09-14, before adding the tests, nine existing E2E
cases already failed because `ContainerCreateStateTransitionHandler` calls a
missing `_state_sequence` method. The new cleanup test additionally reproduces
`container --refresh` reporting completion while leaving `.DS_Store` behind.

Production fixes now share the creation statechart sequence between its
evaluator and handler, validate refresh prerequisites in order against the
current filesystem, and initialize a new Data Package with its required
resources collection. Existing malformed descriptors remain invalid.

Validation of production revision `5d9cdbdc` on 2026-09-14 passed all 93 E2E
tests and all 26 existing container check tests. No test cases, fixtures or
assertions were changed or suppressed for these fixes.
