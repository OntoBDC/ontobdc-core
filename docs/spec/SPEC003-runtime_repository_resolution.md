---
code: SPEC003
title: Runtime Repository Resolution Specification
status: Accepted
author: Elias M. P. Junior
date: 2026-02-26
tags: architecture, runtime, repository, injection
---

# Runtime Repository Resolution Specification

This document defines how the OntoBDC runtime (`run.py`) resolves and injects the `Repository` instance into Capabilities and Actions.

## 1. Responsibility
The runtime entry point (`run.py`) is solely responsible for:
1.  Determining the root path for the repository.
2.  Instantiating the concrete Repository implementation (e.g., `SimpleFileRepository`).
3.  Injecting this repository instance into the `CLI Strategy` and `Capability/Action` execution context.

Capabilities and Actions **must not** instantiate repositories themselves. They must rely on the dependency injection provided by the runtime.

## 2. Root Path Resolution
The root path of the repository is determined in the following order of precedence:

1.  **CLI Argument**: The `--root-path <path>` argument passed to `ontobdc run`.
2.  **Current Working Directory**: If no argument is provided, `os.getcwd()` is used.

## 3. Implementation Details

### CLI Argument Parsing
`run.py` manually parses `--root-path` from `sys.argv` *before* standard argument parsing to ensure the repository is available for the Capability/Action selection phase (which might depend on repository state in the future).

```python
    if "--root-path" in sys.argv:
        # Extract path value
        root_path = sys.argv[sys.argv.index("--root-path") + 1]
    else:
        root_path = os.getcwd()
```

### Repository Instantiation
The runtime instantiates `SimpleFileRepository` with the resolved root path.

```python
    simple_repo = SimpleFileRepository(root_path)
```

### Dependency Injection
The repository instance is added to the `capabilities_attrs` dictionary, which serves as the context for:
1.  **Filtering**: Determining which Capabilities/Actions are available based on required inputs (e.g., `repository`).
2.  **Execution**: Passed to the `get_default_cli_strategy` factory method.

```python
    capabilities_attrs = {
        "org.ontobdc.domain.resource.document.repository.incoming": simple_repo,
        "repository": simple_repo,
    }
```

## 4. Usage in CLI Strategies
When a Capability or Action is selected, the runtime passes the `simple_repo` instance to the strategy factory.

```python
    strategy = cap.get_default_cli_strategy(repository=simple_repo)
```

The CLI Strategy receives this repository in its `__init__` method and uses it to invoke the Capability's `execute` method.

## 5. Constraint
Capabilities and Actions **MUST** declare `repository` (or a specific repository port type) in their `input_schema` to receive the injected instance.
