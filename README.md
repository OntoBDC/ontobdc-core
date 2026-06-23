# OntoBDC WIP Board

Internal development board for the OntoBDC working package in `wip/`.

This file is not a public-facing README. It is the team's quick status board for:

- the current shape of the code in `src/ontobdc/`
- what is already usable
- what is still draft, partial, or temporarily disabled
- where to look first when changing the stack

## Working Definition

OntoBDC is currently being built as a Python CLI plus semantic runtime for:

- bootstrapping local project context
- validating environment and prerequisites
- discovering and executing capabilities
- managing local dataset references
- running artifact-driven semantic workflows such as `a3`

The current capability vocabulary exposed by the code is:

- **`QueryCapabilityPort`**: capability interface for discovery and read-only inspection.
- **`TransformationCapabilityPort`**: capability interface for transformations that create or reshape artifacts.
- **`ActionCapabilityPort`**: capability interface for executable actions in the runtime.

## Current Surface

The command surface that matters right now:

```bash
ontobdc init
ontobdc check
ontobdc list
ontobdc run
ontobdc storage
ontobdc dev
ontobdc a3
```

Typical local loop:

```bash
ontobdc init
ontobdc check
ontobdc list
ontobdc run --id <capability_id>
```

Storage loop:

```bash
ontobdc storage
ontobdc storage --local [path]
ontobdc storage --remove <dataset_id>
```

## Ready / Usable Now

These parts are safe to treat as the current working core of the stack:

- **`init`**: creates `.__ontobdc__/config.yaml` and establishes the minimum local project context.
- **`check`**: runs environment and infrastructure validation before execution.
- **`list` + `run`**: expose the main capability discovery and execution surface.
- **`storage --local` and `storage --remove`**: cover the current dataset registration workflow.
- **`dev`**: active and useful, but intentionally gated by project config.
- **`a3 --etl --source <file|url>`**: ingests a textual source and materializes a lifecycle package.
- **`a3 --work`**: processes lifecycle packages through the current state machine.
- **Plugin/module split**: the code is already organized around adapters, ports, plugins, and domain modules rather than a monolithic CLI.

## Draft / Partial / In Transition

These items exist in code, scripts, or drafts, but should not be treated as settled:

- **`ontobdc plan`**: legacy command path kept only as historical implementation residue; future planning behavior is expected to be unified under `ontobdc run`.
- **`ontobdc extra --enable a3`**: referenced by the codebase and help text, but not wired as a finished public flow.
- **`ontobdc storage --refresh`**: present in scripts, but currently treated as temporarily disabled in the intended workflow.
- **`ontobdc storage --resource`**: present in scripts, but also treated as temporarily disabled for now.
- **Entity-related flows**: drafts and checks reference entity support, but it is not a current public command surface.
- **`a3 --watch`**: appears in draft material, not in the active A3 CLI.

Rule for contributors:

- If it is in this section, do not document it as stable product behavior.
- If it is referenced by code but not by the intended workflow, treat it as implementation residue, draft work, or a future path.

## Code Map

Short map of `src/ontobdc/`:

- `cli/`
  - Top-level routing, initialization helpers, CLI messaging, and shared entrypoint logic.
- `check/`
  - Environment and infrastructure checks, with shell-backed validation and repair hooks.
- `run/`
  - Capability discovery, context/parameter resolution, selection, execution, and rendering.
- `list/`
  - Capability catalog output.
- `storage/`
  - Dataset registration, storage index handling, and storage adapters.
- `dev/`
  - Developer operations across repositories, branches, commits, and related config.
- `a3/`
  - Artifact-driven ETL and lifecycle processing.
- `module/`
  - Built-in domain modules and capability providers.
- `shared/`
  - Shared adapters, ports, ontology helpers, and plugin utilities.

Suggested reading order for newcomers:

1. `cli/`
2. `run/`
3. `storage/`
4. `a3/`
5. `shared/`

## A3 Notes

`a3` is the most explicit example of the stack's file-driven execution model.

Current entrypoints:

```bash
ontobdc a3 --etl --source <file|url>
ontobdc a3 --work
```

Current behavior:

- `--etl` resolves a source extraction strategy and writes a lifecycle package starting from `raw.txt`.
- `--work` scans the lifecycle area, creates one worker per package, and advances each package through the state machine.

Current canonical lifecycle:

```text
undefined -> received -> sanitized -> parsed -> translated -> validated -> reasoned -> dispatched
```

Current artifact progression:

- `received` -> `raw.txt`
- `sanitized` -> `sanitized.txt`
- `parsed` -> `parsed.json`
- `translated` -> `graph.ttl`
- `validated` -> `validated.txt`
- `reasoned` -> `reasoned.ttl`
- `dispatched` -> `dispatched.jsonld`

Why `a3` matters:

- State is inferred from files already present in the package directory.
- Processing is resumable from the latest valid artifact.
- The pipeline leaves a concrete trace for debugging and auditability.
- It is the clearest current implementation of OntoBDC as an artifact-oriented runtime.

Current caveats:

- A3 enablement UX is still awkward.
- The repository references `ontobdc extra --enable a3`, but practical setup still depends on installing the Python dependencies correctly.
- Some surrounding A3 documentation exists in draft form and is ahead of the final CLI UX.

## Important Artifacts

Core files that matter during development:

- `.__ontobdc__/config.yaml`
  - local project configuration and engine selection
- `.__ontobdc__/storage.ttl`
  - dataset storage index
- `.__ontobdc__/payload/lifecycle/...`
  - A3 lifecycle packages and intermediate artifacts

Practical point:

- if you need to understand system state, inspect files first
- OntoBDC currently externalizes a lot of runtime truth into disk artifacts

## Relationship Between `wip/` And `../docs/`

Use this split when deciding where to update documentation:

- `wip/`
  - internal working package
  - implementation-first
  - draft-friendly
  - team board and near-code notes
- `../docs/`
  - more formal stack-level documentation
  - use cases, specs, ontologies, and publishable material

When `wip/` and `../docs/` disagree:

- prefer `src/ontobdc/` as the source of truth for actual behavior
- treat documentation as lagging or leading depending on the feature

## Contribution Notes

Before describing something as done, check all three:

- is it routed by `cli/__init__.py`?
- is it still intended by the current workflow?
- is it documented as active rather than draft or temporarily disabled?

Before adding new docs in `wip/`, prefer:

- short status notes
- explicit caveats
- code-oriented navigation

Avoid turning this file into:

- a marketing README
- a PyPI landing page
- a polished product overview detached from implementation reality

## License

Licensed under **Apache 2.0**.
