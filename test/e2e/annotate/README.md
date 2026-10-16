# Annotation command tests

Run from the repository with its editable CLI installed:

```sh
PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/machine/annotation
```

The CLI runs in real subprocesses in temporary roots. No Qt is needed for
ontobdc: absent repository injection must fail before a viewer is requested.
Known defect assertions intentionally fail; see the annotation test report.
See [REPORT.md](REPORT.md) for coverage, deliberate mutation checks and active defect assertions.

Annotations optionally record their completion time as `completed_at` (ISO 8601).
Create or update it with `--completed-at 2026-10-15T10:30:00-03:00`, or remove
it with `--guid <id> --clear completed_at`. Omitting it leaves a new annotation
open and preserves the existing value when changing another field. Legacy rows
without this column are read as having no completion time. The facade declares
the new column, which the existing entity-write pipeline adds when writing the
dataset; listing and Excel export include it.
