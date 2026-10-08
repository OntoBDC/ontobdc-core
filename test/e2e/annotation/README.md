# Annotation command tests

Run from the repository with its editable CLI installed:

```sh
PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/machine/annotation
```

The CLI runs in real subprocesses in temporary roots. No Qt is needed for
ontobdc: absent repository injection must fail before a viewer is requested.
Known defect assertions intentionally fail; see the annotation test report.
See [REPORT.md](REPORT.md) for coverage, deliberate mutation checks and active defect assertions.
