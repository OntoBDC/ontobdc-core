# RO-Crate Modeling for WhatsApp Workbench
> **Status:** Draft / Conceptual
> **Context:** Layer 2 (Semantic) modeling for OntoBDC WhatsApp Workbench.
> **Goal:** Represent abstract entities (Threads, Tasks, Suggestions) using Schema.org vocabulary within an RO-Crate structure, independent of physical file storage.

## 1. Conceptual Distinction

| Layer | Standard | Responsibility | Entities Managed |
| :--- | :--- | :--- | :--- |
| **Layer 1 (Physical)** | Frictionless Data Package | File catalog, validation, types, paths. | `messages.json`, `threads.json`, `datapackage.json` |
| **Layer 2 (Semantic)** | RO-Crate (JSON-LD) | Knowledge Graph, relationships, provenance. | `Conversation`, `Thread`, `Task`, `Person`, `AIModel` |

## 2. Core Entities Modeling (JSON-LD)

The following entities are "lifted" from the JSON files into the Knowledge Graph.

### 2.1 The Root Dataset (The Chat)
Represented as a `Dataset` or `Conversation` (using extensions).

```json
{
  "@id": "./",
  "@type": "Dataset",
  "name": "WhatsApp Chat Analysis: Project X",
  "description": "Semantic analysis of conversation regarding Project X, processed by OntoBDC.",
  "datePublished": "2024-05-20",
  "creator": { "@id": "#person-elias" },
  "mentions": [
    { "@id": "#thread-1" },
    { "@id": "#thread-2" }
  ]
}
```

### 2.2 The Thread (A Semantic Cluster)
A thread is not a file; it's a logical grouping of messages.
*   **Schema.org Mapping:** `CreativeWork` or `Conversation` (pending proposal).
*   **Properties:** `about` (topic), `hasPart` (messages), `potentialAction` (tasks).

```json
{
  "@id": "#thread-1",
  "@type": "CreativeWork",
  "name": "Discussion on API Architecture",
  "description": "Technical debate about REST vs GraphQL endpoints.",
  "dateCreated": "2024-05-19T10:00:00Z",
  "author": [
    { "@id": "#person-alice" },
    { "@id": "#person-bob" }
  ],
  "hasPart": [
    { "@id": "urn:whatsapp:msg:12345" },
    { "@id": "urn:whatsapp:msg:12346" }
  ]
}
```

### 2.3 The Task (Actionable Insight)
Tasks are extracted intents.
*   **Schema.org Mapping:** `Action` or `PlanAction`.
*   **Properties:** `agent` (assignee), `object` (target), `startTime` (due date), `status`.

```json
{
  "@id": "#task-101",
  "@type": "PlanAction",
  "name": "Refactor Endpoint X",
  "agent": { "@id": "#person-alice" },
  "instrument": { "@id": "#thread-1" },
  "actionStatus": "http://schema.org/PotentialActionStatus",
  "description": "Alice needs to refactor the legacy endpoint by Friday."
}
```

### 2.4 The Suggestion (AI Generated Draft)
*   **Schema.org Mapping:** `Comment` or `CreativeWork`.
*   **Properties:** `text`, `about` (the thread), `creator` (the AI Agent).

```json
{
  "@id": "#suggestion-001",
  "@type": "Comment",
  "text": "I suggest we stick to REST for now to avoid breaking legacy clients...",
  "about": { "@id": "#thread-1" },
  "creator": { "@id": "#agent-gemini-pro" },
  "encodingFormat": "text/markdown"
}
```

## 3. Provenance Modeling (Who did what?)

Crucial for the "Onto" part. We explicitly state that the AI created the structure.

```json
{
  "@id": "#agent-gemini-pro",
  "@type": "SoftwareApplication",
  "name": "Gemini 1.5 Pro",
  "version": "1.5-pro-preview-0514"
}
```

```json
{
  "@id": "#inference-activity-1",
  "@type": "CreateAction",
  "agent": { "@id": "#agent-gemini-pro" },
  "result": [
    { "@id": "#thread-1" },
    { "@id": "#task-101" }
  ],
  "object": { "@id": "./" }, 
  "startTime": "2024-05-20T14:30:00Z"
}
```

## 4. RO-Crate Metadata Structure (Example)

This would be the content of `ro-crate-metadata.json`, sitting alongside `datapackage.json`.

```json
{
  "@context": "https://w3id.org/ro/crate/1.1/context",
  "@graph": [
    {
      "@id": "./",
      "@type": "Dataset",
      "name": "Chat Analysis Bundle",
      "hasPart": [
        { "@id": "threads.json" },
        { "@id": "tasks.json" }
      ],
      "mentions": [
        { "@id": "#thread-1" }
      ]
    },
    {
      "@id": "threads.json",
      "@type": "File",
      "name": "Threads Data Source",
      "encodingFormat": "application/json"
    },
    {
      "@id": "#thread-1",
      "@type": "CreativeWork",
      "name": "Project Kickoff",
      "description": "Initial discussion about timelines.",
      "about": { "@id": "http://dbpedia.org/resource/Project_management" } 
    }
  ]
}
```

## 5. Implementation Strategy

1.  **Generate Layer 1 (Frictionless):** As currently implemented (`whatsapp_messages.py`).
2.  **Lift to Layer 2 (RO-Crate):** A new capability (e.g., `WhatsappToROCrateCapability`) that:
    *   Reads the `datapackage.json` and resource files (`threads.json`, etc.).
    *   Instantiates the JSON-LD objects.
    *   Writes `ro-crate-metadata.json`.
3.  **Ontology Binding:**
    *   Use `schema.org` as the base.
    *   Use specific extensions (e.g., `FOAF`) only if strictly necessary.

This approach keeps the physical storage simple (JSONs) while allowing the semantic complexity to grow indefinitely in the Graph layer without breaking legacy tools.
