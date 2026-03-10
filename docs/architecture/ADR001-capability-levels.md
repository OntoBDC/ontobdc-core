---
code: ADR001
title: Three-Level Agent Power Architecture (Capabilities, Actions, Use Cases)
status: Accepted
author: Elias M. P. Junior
date: 2024-05-20
tags: architecture, capability, standard
---

## Context
As OntoBDC evolves from a set of scripts into a platform for autonomous agents, we need to strictly define the "power levels" (permissions and side effects) of the tools available to these agents. Unrestricted access to file modifications or state transitions can lead to unpredictable behavior, data corruption, or security risks (especially when LLMs are "driving").

We observed that the initial design of "Capabilities" was implicitly read-only, but this was not formalized. We also identified a need for intermediate operations (data transformation) that are complex but stateless, and high-level operations that change business state.

## Decision
We will adopt a **Three-Level Architecture** for agent tools:

| Level | Name | Scope & Power | Side Effects? | Example |
| :--- | :--- | :--- | :--- | :--- |
| **L1** | **Capability** | **Read-Only / Discovery.** Pure interface to query the environment. | **NO.** Must be idempotent and safe to retry infinite times. | `list_documents`, `get_file_content`, `check_syntax`. |
| **L2** | **Action** | **Transformation / Creation.** Takes input data and produces new data/files without changing business state logic. | **Local Only.** Can create/write files but does not advance workflow state. | `unzip_file`, `convert_pdf_to_png`, `generate_ro_crate_json`. |
| **L3** | **Use Case** | **State Transition.** Orchestrates L1 and L2 to move the business process forward. | **YES.** Changes the "truth" of the system. | `process_chat_folder` (Raw -> Processed), `publish_dataset`. |

### Detailed Definitions

#### 1. Capabilities (The "Senses")
*   **Purpose:** Allow the agent to "see" and "read" the environment.
*   **Constraint:** MUST NOT modify any file, database, or external state.
*   **Usage:** Agents use these to gather context before deciding what to do.
*   **Naming Convention:** `list_*`, `get_*`, `check_*`.

#### 2. Actions (The "Hands")
*   **Purpose:** Perform specific, scoped units of work.
*   **Constraint:** They are functional in nature. Input -> Transformation -> Output. They don't care about "Project Status" or "Workflow Phase".
*   **Usage:** Agents use these to execute the steps of a plan.
*   **Naming Convention:** Verbs like `extract`, `convert`, `compress`, `generate`.
*   *Note:* Previously considered "overengineering" to have FSM states for every file change (e.g., zipped vs unzipped). Actions solve this by being stateless tools.

#### 3. Use Cases (The "Brain" / Workflow)
*   **Purpose:** Encapsulate a full business transaction.
*   **Constraint:** Only Use Cases can officially transition an entity from "Pending" to "Done". They orchestrate Capabilities and Actions.
*   **Usage:** High-level commands triggered by the user or a master agent.

## Consequences

### Positive
*   **Safety:** We can give an untrusted agent access to all **Capabilities** without fear of damage.
*   **Clarity:** Developers know exactly where to put logic. "Is this just reading?" -> Capability. "Is this making a PNG?" -> Action.
*   **Reusability:** Actions (like `unzip`) become reusable across different Use Cases.

### Negative
*   **Refactoring Cost:** Existing scripts (like `whatsapp_messages.py`) currently mix all three levels. They will need to be broken down over time.
*   **Verbosity:** Simple tasks might seem to require more "boilerplate" classes (one for the Capability, one for the Action).

## Compliance
New modules MUST follow this structure. Existing modules should be refactored when touched.
