# OntoBDC

OntoBDC is a **domain and data layer** for engineering information.
It provides:

- Domain models (entities and schemas) for documents and datasets
- File and dataset repositories built on top of folders and filesystems
- Resource-oriented capabilities that can be composed into higher-level flows

You can use OntoBDC as a Python package, via its own CLI
(`ontobdc.sh` / `run/run.sh`), or integrated into other stacks.

---

## 🚀 Quick Start

### 1. Install as a Python package

From the root of this repository:

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e .
```

This makes the `ontobdc` package importable in your Python environment.

### 2. Run capabilities via ontobdc CLI

This repository provides a thin CLI wrapper in `ontobdc.sh` that dispatches
to development tools and the capability runner:

```bash
./ontobdc.sh -h
```

Main commands:

- `./ontobdc.sh run …`  → runs capabilities through `ontobdc/run/run.py`
- `./ontobdc.sh plan …` → plans capability execution flows
- `./ontobdc.sh commit` / `./ontobdc.sh branch` → Git workflow helpers for this repo

You can also call the runner script directly:

```bash
./ontobdc/run/run.sh run --json
```

This prints a JSON catalog of registered capabilities, including those
coming from OntoBDC itself and, if configured, other plugin packages.

OntoBDC ships resource-oriented capabilities, for example
to list documents from a repository:

- `org.ontobdc.domain.resource.capability.list_documents_by_bbox`
- `org.ontobdc.domain.resource.capability.list_documents_by_type`
- `org.ontobdc.domain.resource.capability.list_documents_by_name_pattern`

These capabilities are designed to work over a `FileRepositoryPort`
implementation, typically backed by local folders or other storage
adapters.

## 🧩 Capabilities

OntoBDC focuses on **resource and file-centric** capabilities. Examples:

### Resource Capabilities

These live under `ontobdc.resource.plugin.capability`:

| ID | Description |
|----|-------------|
| `org.ontobdc.domain.resource.capability.list_documents_by_bbox` | Lists documents from a `FileRepositoryPort` filtered by bounding box and optional mimetypes. |
| `org.ontobdc.domain.resource.capability.list_documents_by_type` | Lists documents filtered by logical type (e.g., models, drawings, reports). |
| `org.ontobdc.domain.resource.capability.list_documents_by_name_pattern` | Lists documents filtered by name patterns (glob or regex-style matching). |

These capabilities consume repositories defined in
`ontobdc.resource.src.domain.port.repository` and adapters in
`ontobdc.resource.src.adapter`.

### Drive / PDF Capabilities

Under `ontobdc.tmp.src.drive.plugin.capability.pdf` you will find
experimental capabilities such as:

- Attaching images to PDF files
- Converting PDF pages to PNG
- Extracting PDF pages to markdown
- Counting pages in a PDF

They are meant for document processing workflows that sit on top of
OntoBDC’s file and dataset abstractions.

---

## 🏗️ Architecture

OntoBDC is structured as a set of **layers**:

- **Domain Ports and Entities**  
  - `ontobdc.resource.src.domain.port.*` defines interfaces for entities
    (documents, folders, datasets) and repositories.
  - `ontobdc.resource.src.domain.entity` and schemas describe how these
    resources are modeled.

- **Adapters**  
  - `ontobdc.resource.src.adapter` provides concrete adapters for
    filesystem-based repositories and folder structures.
  - `ontobdc.core.src.adapter` includes presentation adapters, such as
    rich table rendering for terminal output.

- **Capabilities**  
  - `ontobdc.resource.plugin.capability` packages domain operations as
    reusable capabilities compatible with the InfoBIM execution model.
  - Drive / PDF capabilities live under `ontobdc.tmp.src.drive.plugin.capability`.

- **Runner Integration**  
  - `ontobdc/run/run.py` registers capabilities in a shared
    `CapabilityRegistry` and wires them to the CLI, including
    `--json` catalog export and an interactive menu when no capability ID
    is provided.

---

## 🤖 For AI Agents

OntoBDC is designed to be **agent-friendly**:

- Capabilities expose structured input and output schemas
- The runner supports a JSON catalog (`--json`) for automatic discovery
- Planning helpers in `ontobdc/run/plan.py` can be used to build and
  visualize multi-step execution graphs

---

## 🔗 Integration with other stacks (including InfoBIM IFC)

OntoBDC can be embedded into larger stacks. One concrete example is the
InfoBIM IFC stack, where:

- OntoBDC provides the **domain model** and **resource capabilities**
  (documents, repositories, datasets)
- The stack adds IFC-centric capabilities (pipes, units, materials) and
  a higher-level CLI

In that scenario, capabilities from OntoBDC and from the host stack share
the same capability registry and can be combined in planning/automation
workflows.

---

## 📄 License

OntoBDC is part of the **InfoBIM Community** ecosystem.  
Licensed under **Apache 2.0**.***
