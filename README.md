# OntoBDC

> OntoBDC is a domain-driven data architecture for engineering systems.

OntoBDC provides a structured way to define capabilities, actions, and use cases over engineering data.

<p align="left">
  <img src="./images/ontobdc_colab_example_02.png" width="55%" />
</p>

It enables reproducible, auditable, and automation-ready workflows across technical domains.

## 🏗️ Used by

OntoBDC is currently used as the core data and execution layer of:

- <a href="https://infobim.org" target="_blank" rel="noopener noreferrer">InfoBIM</a>

InfoBIM leverages OntoBDC to define capabilities, execute checks, and orchestrate engineering data workflows.

## 📦 Requirements

- Python 3.11+
- pip

## 🚀 Getting Started

Install the package:

```sh
pip install ontobdc
```


After installation, the `ontobdc` CLI becomes available:

```sh
ontobdc --version
```
<img src="./docs/images/version.png" width="80%" />

Initialize the project to create the local configuration:

```bash
ontobdc init
```

The `init` command automatically detects the environment (e.g., `venv` or `Google Colab`) and creates the `.__ontobdc__` directory with the base configuration:

<img src="./docs/images/init.png" width="80%" />

Execute capabilities interactively:

```bash
ontobdc run
```

This command launches an interactive menu to discover and execute available capabilities:

<img src="./docs/images/run.png" width="80%" />

From there, you can run other capabilities, perform actions, and interact with registered use cases.


### Alternative: Google Colab

You can try OntoBDC directly in Google Colab without installing anything locally.

<a href="examples/ontobdc_example.ipynb" target="_blank">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

View or download the [example notebook](examples/ontobdc_example.ipynb) to see capabilities in action.

## ✅ Checking

The `check` command validates engineering data against defined capabilities and rules.

```sh
ontobdc check --repair
```

It executes registered checks over the target dataset, reports inconsistencies, and optionally applies automated repairs when `--repair` is enabled.

<p align="left">
  <img src="./images/ontobdc_colab_example_01.png" width="55%" />
</p>

This ensures reproducibility, auditability, and deterministic validation of engineering workflows.

## Project Map (mini-modules)

OntoBDC is intentionally split into small modules so you can quickly find “where a concern lives”. A simple mental model:
- If it is a top-level CLI command, start in `src/ontobdc/<command>/` or `src/ontobdc/cli/`.
- If it is about discovery, parsing flags, selecting, and executing, start in `src/ontobdc/run/`.
- If it is a domain feature (documents, social, etc.), start in `src/ontobdc/module/<domain>/`.

Mini-modules (by responsibility):
- **CLI / command routing**: [src/ontobdc/cli](src/ontobdc/cli) — main dispatcher (`ontobdc <command> ...`), init logic, message-box/log helpers.
- **Infrastructure checks**: [src/ontobdc/check](src/ontobdc/check) — check runner and infra checks (`ontobdc check --repair`).
- **Runtime (discovery/execution)**: [src/ontobdc/run](src/ontobdc/run) — capability discovery, CLI context resolution (strategies), interactive selection UI, execution.
- **Catalog/listing**: [src/ontobdc/list](src/ontobdc/list) — “what is available?” tooling (`ontobdc list`), including JSON output for automation.
- **Storage (dataset index)**: [src/ontobdc/storage](src/ontobdc/storage) — storage index management (`ontobdc storage ...`), refresh/remove/local dataset registration.
- **Plan (semantic execution plan)**: [src/ontobdc/plan](src/ontobdc/plan) — generates RDF/Turtle artifacts linking capability IDs, parameters, and resolved context.
- **Entity tools (optional framework/CLI)**: [src/ontobdc/entity](src/ontobdc/entity) — entity-related scripts and utilities (typically enabled via config).
- **Developer tools (scripts)**: [src/ontobdc/dev](src/ontobdc/dev) — local developer workflows (branch/commit helpers, etc.).
- **Core (shared ports/adapters)**: [src/ontobdc/core](src/ontobdc/core) — foundational abstractions used by other modules (ports, verification utilities).
- **Domain modules (plugins/capabilities per domain)**: [src/ontobdc/module](src/ontobdc/module)
  - **Resource**: [src/ontobdc/module/resource](src/ontobdc/module/resource) — document repository abstractions, renderers, and “resource” capabilities.
  - **Social**: [src/ontobdc/module/social](src/ontobdc/module/social) — social/account concepts and early CLI strategies (e.g., WhatsApp-related).
- **UI/output templates**: [src/ontobdc/plugin/template](src/ontobdc/plugin/template) — reusable CLI rendering components (cards/tables).

## Contributing

We are always on the lookout for contributors to help us fix bugs, create new features, or help us improve project documentation. If you are interested, feel free to create a [PR](https://github.com/OntoBDC/ontobdc-core/pulls) or open an [issue](https://github.com/OntoBDC/ontobdc-core/issues) on this topic.

## 🔜 Next Steps

Generate an RDF execution plan (Turtle) with stable URNs/prefixes linking plans, capabilities, inputs/outputs, and resolved parameters (with values). Add CLI flags and minimal tests/validation (e.g., Protégé/Graphviz) to inspect and verify the generated graph.

## 📄 License

Licensed under **Apache 2.0**.
