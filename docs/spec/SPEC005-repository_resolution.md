# Repository Resolution Specification

## Context
The `ontobdc` CLI tool operates on a document repository. The repository root is typically identified by the presence of a `.__ontobdc__` directory containing metadata (e.g., `datapackage.json`).
Users may run the tool from the repository root, a subdirectory, or a parent directory (in a workspace context).

## Resolution Logic
The `run.py` script is responsible for resolving the repository root path before initializing the repository adapter. The resolution logic is as follows:

1. **Explicit Override**:
   - If `--root-path` or `--repository` argument is provided, use it as the repository root.

2. **Current Working Directory (CWD)**:
   - Check if the current working directory contains a `.__ontobdc__` directory.
   - If yes, use CWD as repository root.

3. **Workspace Heuristic (Downwards)**:
   - If CWD does not match, check if a `projects` subdirectory exists in CWD and contains `.__ontobdc__`.
   - If yes, use `CWD/projects` as repository root.

4. **Parent Directory (Upwards)**:
   - If not found, walk up the directory tree (to a reasonable limit or filesystem root).
   - If a parent directory contains `.__ontobdc__`, use it as repository root.

5. **Fallback**:
   - If no repository is found, default to CWD (and let capabilities fail gracefully or report error if they require a valid repo).

## Implementation Details
- The logic should be implemented in `run.py`'s `main` function before initializing `SimpleFileRepository`.
- The resolved path must be absolute.
- Extraneous arguments should be preserved for capabilities.

## Rationale
This approach supports:
- Running from the root of a project.
- Running from the root of a workspace (containing a `projects` folder).
- Running from deep within a project (finding the root upwards).
