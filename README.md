# OntoBDC

OntoBDC is a **domain and data layer** for engineering information.
It provides:

- Domain models (entities and schemas) for documents and datasets
- File and dataset repositories built on top of folders and filesystems
- Resource-oriented capabilities that can be composed into higher-level flows

You can use OntoBDC as a Python package, via its own CLI `ontobdc`, or integrated into other stacks.

---

## 🚀 Quick Start

### 1. Install as a Python package

From the root of this repository:

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e .
```

This makes the `ontobdc` package importable in your Python environment and installs the `ontobdc` command.

### 2. Configure the Environment

Before running capabilities, configure your environment (engine). This will create the necessary configuration files and verify your installation.

**For Local Environment (venv):**
```bash
ontobdc setup venv
```

**For Google Colab:**
```bash
ontobdc setup colab
```

The `setup` command automatically runs system checks (`ontobdc check --repair`) to ensure all dependencies and configurations are correct.

### 3. Run Capabilities

Use the CLI to run capabilities. If you don't provide a capability ID, an interactive menu will appear.

```bash
ontobdc run
```

To run a specific capability directly:

```bash
ontobdc run org.ontobdc.domain.resource.capability.list_documents_by_type
```

### 4. Other Commands

- `ontobdc check` → Runs infrastructure checks (internet, dependencies, engine config). Use `--repair` to attempt auto-fixes.
- `ontobdc plan …` → Plans capability execution flows.
- `ontobdc commit` / `ontobdc branch` → Git workflow helpers for this repo (development mode).

---

## 🧩 Capabilities

OntoBDC focuses on **resource and file-centric** capabilities. Examples:

### Resource Capabilities

These live under `ontobdc.module.resource.plugin.capability`:

| ID | Description |
|----|-------------|
| `org.ontobdc.domain.resource.capability.list_documents_by_name_pattern` | Lists documents filtered by name patterns (glob/regex). |
| `org.ontobdc.domain.resource.capability.list_documents_by_type` | Lists documents filtered by logical type. |

### Social / WhatsApp Capabilities

Under `ontobdc.module.social.plugin` you will find capabilities for social data processing:

- `org.ontobdc.domain.social.capability.list_whatsapp_accounts`
- Extract unanswered messages from WhatsApp exports

---

## 🏗️ Architecture

OntoBDC is structured as a set of **layers**:

- **Domain Ports and Entities**  
  - `ontobdc.core.domain.port.*` defines interfaces for entities and repositories.
  - `ontobdc.module.*.schema` describes how these resources are modeled.

- **Adapters**  
  - `ontobdc.module.*.adapter` provides concrete adapters for filesystem-based repositories and external services.
  - `ontobdc.core.adapter` includes presentation adapters, such as rich table rendering.

- **Capabilities**  
  - `ontobdc.module.*.plugin.capability` packages domain operations as reusable capabilities compatible with the InfoBIM execution model.

- **Runner Integration**  
  - `ontobdc.run` handles capability discovery, execution, and CLI interaction.

---

## 🤖 For AI Agents

OntoBDC is designed to be **agent-friendly**:

- Capabilities expose structured input and output schemas
- The runner supports a JSON catalog (`ontobdc run --json`) for automatic discovery
- Planning helpers can be used to build and visualize multi-step execution graphs

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

Licensed under **Apache 2.0**.
