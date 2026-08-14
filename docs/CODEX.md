You are implementing a narrowly scoped AI-assisted resource suggestion feature
for OntoBDC WorkStreams. Small, functional, inspectable, easy to replace later
— but not architecturally careless.

======================================================================
0. VERIFIED FACTS — DO NOT RE-INVESTIGATE THESE
======================================================================

The two biggest open questions in earlier drafts of this task are already
answered by inspecting the real repos. Do not spend time re-deriving them;
verify with a single read of the cited files/lines if you want to double-check,
then move straight to implementation.

**A. Suggested already exists in the View. It is not "discontinued InfoBIM
behavior" to restore.**

`ontobdc-view` branch `v0.3`, `src/ontobdc_view/page/asset/work_stream_view.js`
already has a full Related / Suggested / Found tab set per WorkStream
dimension (search `data-tab="suggested"`, `resource-suggest-btn`,
`toggleSuggestion`). Suggested already has a Proposed/Rejected status
lifecycle. Do NOT rebuild this UI. Your job is to make the CLI able to write
into the same persisted state the View already renders, then confirm it
shows up — not to add tabs, buttons, or a new tree/preview system.

**B. The `.__ontobdc__/relation/work_stream/` concern is already fixed —
in the *browser* half of the system.**

Two commits already landed on `ontobdc-view` `v0.3` before this task starts:

- `7bde423` — "fix: use official linkset directory instead of forbidden
  relation folder for WorkStream resource linksets"
- `67780a5` — "feat: add Suggested dimension-resource linkset tab with
  Proposed/Rejected lifecycle"

The canonical persistence today (client-side, in `work_stream_view.js`) is:

```
<connected-folder>/.__ontobdc__/linkset/WorkStreamResource.ttl    (Related)
<connected-folder>/.__ontobdc__/linkset/WorkStreamSuggested.ttl   (Suggested)
```

Exact RDF shape already in production use (see `LINKSET_PYTHON_SCRIPT` in
`work_stream_view.js`, ~line 608 — it's an inline Python script run through
Pyodide+rdflib **in the browser**, there is no server-side/CLI equivalent
yet):

- Vocabulary: ISO 21597 Linkset — `https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#`
  (prefix `ls`), plus `http://ontobdc.org/ontology/domain/ns.ttl#` (prefix
  `obdc`) for the status extension.
- Each link is one `ls:DirectedBinaryLink` resource, IRI
  `<nsPrefix>:<sha256(from+"|"+to)[:16]>` where `nsPrefix` is
  `urn:ontobdc:linkset:workstream-resource` (Related) or
  `urn:ontobdc:linkset:workstream-suggested` (Suggested).
- `ls:hasFromLinkElement` → blank node → `ls:hasIdentifier` → blank node
  `a ls:URIBasedIdentifier ; ls:uri "<dimension URI>"^^xsd:anyURI`.
- `ls:hasToLinkElement` → same shape, `ls:uri` = the resource's URI.
- Suggested-only: `obdc:suggestionStatus` =
  `http://ontobdc.org/ontology/domain/ns.ttl#Proposed` or `#Rejected`, plus
  `obdc:suggestionModifiedAt` (`xsd:dateTimeStamp`, ISO 8601 UTC). Related
  links carry neither predicate — add/remove is a straight graph add/remove,
  no status lifecycle.
- On "remove" for a *suggested* link: don't delete the triple, flip status to
  `Rejected` (soft-reject, keeps history). On "remove" for a *related* link:
  delete the triples outright.
- Rejected suggestions are excluded from the active `entries` map the View
  reads, but stay in `allStatus` and in the file.

**The actual gap this task fills**: there is no Python/server-side code
anywhere in `ontobdc-wip` that reads/writes this file format — it only
exists as a JS string executed via Pyodide in the browser. Your new CLI
command needs a Python port of the logic above (same predicates, same IRI
scheme, same status semantics) so that a `.ttl` it writes is byte-for-byte
compatible with what the browser's Pyodide script already reads, and vice
versa. Put this port behind a small, reusable module — do not inline rdflib
graph-walking code directly in the CLI command class.

**C. GlobalId: the field exists, a reusable CLI parameter strategy does
not.**

`GlobalId` is an established identifying field for entity instances (see
`ontobdc/shared/adapter/entity_workbook.py:270-273`,
`ontobdc/context/plugin/command/entity.py` multiple references). But there
is no `--global-id` flag and no generic "resolve an entity instance by
GlobalId" parameter strategy yet. The one existing parameter-strategy
precedent to copy the shape of is
`ontobdc/context/plugin/parameter/language.py`'s `ViewLanguageStrategy`
(`ParameterPort` + `CliContextStrategyPort`, a `ParameterMetadata`, a small
`execute(context)`). Build the GlobalId strategy the same way, in
`ontobdc/context/plugin/parameter/`, generic over entity type — not
WorkStream-specific — since the concern ("resolve an instance by GlobalId")
belongs to entity identity, not to this feature.

Files/resources still do NOT have GlobalId and must not be given one.

======================================================================
1. WHAT TO STILL INVESTIGATE YOURSELF
======================================================================

The above removes the two largest unknowns. You still need to look at, in
the active `ontobdc-wip` v0.16 code (not `old/`, `lab/`, or `reference/`):

- The current resource inventory/facade/manifest mechanism (how existing
  code already enumerates a container's resources — reuse it, don't scan
  the filesystem yourself).
- How WorkStream dimensions (`what/why/who/where/when/how/how-much`) are
  actually declared in the ontology/facade today, so you derive the valid
  set instead of hardcoding a second copy of it.
- `ontobdc context` command discovery (`context/plugin/command/entity.py`
  is the pattern to follow: `CliCommandPort`, `CliCommandMetadata`,
  `arguments`, `--container`/`--container-id` resolution — reuse that
  container resolution, don't reinvent it).
- Whether `AGENTS.md`/`CLAUDE.md` in `ontobdc-wip` add any constraint not
  covered here.

If something here turns out to be stale by the time you run this (code
moved, file renamed), trust the live repo over this document, but say so
explicitly in your final report.

======================================================================
2. FEATURE GOAL
======================================================================

Add AI-assisted resource suggestions for ONE WorkStream dimension at a time.

For a selected WorkStream + dimension, ask an external AI agent: "Which of
these existing project resources are plausible evidence for THIS dimension
of THIS WorkStream?" This is a narrow candidate-selection operation — not
generic search, not RAG, not a chatbot, not autonomous graph mutation.

State progression: `Found/All → Suggested → Related`. The AI only ever
proposes into Suggested. A human accepts a suggestion to promote it to
Related, through the same linkset mechanism the View already uses for
manual Relate. The AI must never create a Related link directly.

======================================================================
3. CLI CONTRACT
======================================================================

```
ontobdc context \
  --entity WorkStream \
  --global-id <WORKSTREAM_GLOBAL_ID> \
  --dimension <dimension> \
  --suggest
```

Examples: `--dimension who --suggest`, `--dimension where --suggest`,
`--dimension when --suggest`.

`--global-id` identifies the WorkStream instance. Do not substitute `--id`.
Resources are identified by their existing canonical OntoBDC resource
identity (from the inventory/facade), not by GlobalId — do not invent one
for them. For the LLM prompt only, map resource identities to ephemeral
short tokens `R001`, `R002`, ... and map them back after validation.

Verify whether this belongs as a new file
(`src/ontobdc/context/plugin/command/suggest.py`,
`class ContextSuggestCommand(CliCommandPort)`) or as a `--suggest` flag
added to the existing `context entity` command — check which fits the
current one-command-per-concern convention better before deciding; default
to a new file unless the existing command's `arguments` shape makes a flag
clearly more consistent.

The command must fail clearly if the GlobalId can't be resolved. Never fall
back to title, filename, row number, UI index, or a freshly generated UUID.

======================================================================
4. COMMAND PIPELINE
======================================================================

A. Resolve container the same way other `context` commands do (don't add a
   second resolution mechanism).
B. Resolve entity type = WorkStream via the current entity catalog/facade.
C. Resolve the WorkStream instance via `--global-id`, using the parameter
   strategy from §0.C.
D. Resolve `--dimension` against the actual WorkStream ontology/facade
   dimension set (§1), normalizing CLI spelling (`how-much` etc.) to the
   canonical semantic dimension URI at the boundary only.
E. Gather minimal WorkStream/dimension context: WorkStream title/description,
   selected dimension's canonical label/URI, and whatever value is already
   recorded for that dimension. Do not dump the whole container graph.
F. Gather candidate resources from the canonical inventory/facade, excluding
   OntoBDC-generated artifacts, internal metadata, and View artifacts per
   existing exclusion rules.
G. Read existing Related links for this dimension via the Python linkset
   port from §0.B (kind = `related`). Resources already Related should
   normally not be re-suggested.
H. Build bounded candidate objects with an ephemeral key (`R001`, ...) and
   only fields that already exist (title, path, media type, description/
   snippet, dates, etc.) — never fabricate metadata that isn't present.
I. Build the prompt (§6).
J. Invoke the external AI CLI (§5).
K. Parse and strictly validate the JSON result (§7).
L. Persist each valid suggestion via the Python linkset port from §0.B
   (kind = `suggested`, action = add → status `Proposed`).
M. Return a structured `CommandResponse` (machine-readable JSON, no
   arbitrary `print()`).

======================================================================
5. EXTERNAL AI EXECUTION
======================================================================

No provider abstraction today. Check what's actually installed
(`codex --version`, `claude --version` or equivalent) — don't assume either
exists. Use whichever is available and simplest to invoke non-interactively;
if both are available, pick the one with the least fragile non-interactive
invocation in this environment and say which and why in your report.

Wrap it behind one small function: `invoke_suggestion_agent(prompt: str) -> str`.
No provider ecosystem, no SDK dependency if a CLI already does the job.

If neither CLI is available: fail explicitly with the exact missing
prerequisite. Never fabricate a suggestion result, and never turn an
invocation failure into a silently empty suggestion list — an empty list is
only valid when the model itself returns `{"suggested":[]}`.

Security: subprocess argument arrays, not `shell=True`. Never concatenate
resource content into shell syntax. Prompt via stdin or a temp file per
whatever the chosen CLI wants; clean up temp files. The agent is a selector,
not an executor — it must not be given any permission or instruction to
modify repository/project files.

======================================================================
6. THE MODEL PROMPT
======================================================================

Deterministic construction. Core semantic rule to state explicitly in the
prompt: evaluate relevance for the *selected dimension specifically*, not
"is this resource related to the WorkStream in general" — the same resource
can be relevant for one dimension (e.g. Who) and irrelevant for another
(e.g. Where).

```
SYSTEM/ROLE: constrained project-information evidence selector. Not a
project database. Cannot invent resources. Cannot modify project state.
Must select zero or more candidates ONLY from the provided set.

CONTEXT:
  Entity type: WorkStream
  WorkStream GlobalId: <global-id>
  WorkStream title: <if available>
  WorkStream description: <if available>
  Selected dimension: <canonical label>
  Dimension semantic identity: <URI>
  Current dimension value: <if available>

QUESTION: Which candidates are plausibly relevant as evidence, source
material, documentation, communication, reference, or supporting
information for the SELECTED DIMENSION of THIS WorkStream specifically?

CANDIDATES:
  R001
    title: ...
    path: ...
    media_type: ...
    description/snippet: ...
  R002
    ...

OUTPUT CONTRACT — JSON ONLY, exact schema:
{"suggested": ["R001", "R007"]}

Rules: array of exactly-supplied candidate keys only; no explanations, no
markdown, no confidence scores, no extra metadata, no invented keys; empty
array is valid.
```

======================================================================
7. STRICT OUTPUT VALIDATION
======================================================================

Treat the model's output as untrusted:

1. Must parse as a JSON object with a `suggested` array.
2. Every member must be a string that exists in the candidate map — no
   fuzzy matching, no accepting a path/URI directly from the model.
3. Any unknown candidate key → fail the whole operation, don't silently drop it.
4. Prose around the JSON → fail rather than attempt repair.
5. Deduplicate deterministically; preserve a stable candidate order.

Only candidate keys OntoBDC itself supplied may ever come back accepted —
this is the hallucination guardrail.

======================================================================
8. RELATED MUST NOT REGRESS
======================================================================

Related already uses the correct `.__ontobdc__/linkset/WorkStreamResource.ttl`
mechanism client-side (§0.B) — don't touch that. Your new Python linkset
port must produce/consume files compatible with it. If, while building the
Python port, you find any actual remaining `.__ontobdc__/relation/` write
path still active somewhere in the current v0.3/v0.16 code (not `old/`),
report it and fix it as part of this task; if you find nothing, say so
explicitly in the report rather than assuming.

======================================================================
9. RESOURCE IDENTITY — DO NOT CONFLATE
======================================================================

- WorkStream: selected by GlobalId.
- Resource/file: existing canonical OntoBDC resource identity (URI from the
  inventory/facade). No GlobalId, ever, for files.
- Prompt alias (`R001`...): exists only for AI input/output validation, map
  explicitly both ways, never persisted as an identifier anywhere.

======================================================================
10. OUT OF SCOPE TODAY
======================================================================

Embeddings, vector DB, RAG, generic chat UI, autonomous agents, NL command
parser, AI provider framework, confidence scoring/visualization, AI-written
explanations, full provenance UI, multi-agent review, automatic acceptance,
background daemon/watcher, central web service, new DB, new JS framework,
new bundler, auth/login, telemetry, migration framework, file GlobalIds,
reimplementing the WorkStream model, rebuilding the View's tab/tree/preview
UI (it already exists — §0.A).

Also skip for today unless trivial: reject/dismiss UI action. If it maps
directly onto the existing `Rejected` status write, fine; otherwise omit
rather than invent a new persistence shape for it.

======================================================================
11. ARCHITECTURAL PRINCIPLE
======================================================================

Deterministic (OntoBDC): container, WorkStream, GlobalId, dimension,
candidate universe/identity, existing Related, output schema, validation,
persistence, acceptance semantics.

Probabilistic (LLM): candidate relevance selection only, from a closed set.

Human: decides whether a suggestion becomes Related.

======================================================================
12. TESTS
======================================================================

- Command discovery finds the new command/flag.
- `--global-id` required; invalid GlobalId fails clearly.
- Invalid dimension fails clearly.
- Candidates come from the canonical inventory, not a fresh filesystem scan.
- Already-Related resources are excluded/handled correctly.
- Valid JSON suggestions accepted; unknown candidate key fails; malformed
  JSON fails; empty `suggested` list succeeds.
- Suggested persistence produces the exact RDF shape from §0.B (round-trip:
  Python-written `.ttl` parses correctly under the existing browser Pyodide
  script's assumptions — at minimum assert the triple shape/predicates
  match, since you can't run Pyodide in a Python test).
- Acceptance promotes Suggested → Related through the same linkset port,
  not a separate code path.
- `node --check` on every modified JS file (there should be few to none —
  see §0.A).
- Run focused pytest targets first, then the broader relevant suite.

======================================================================
13. BRANCH DISCIPLINE
======================================================================

Do not touch `master`. Base on the active branches: `ontobdc-wip` v0.16,
`ontobdc-view` — verify current branch (this document was written against
`v0.3`; confirm nothing newer exists before starting). New branch,
e.g. `feat/workstream-ai-suggestions`. Commit with clear messages. Push if
the environment allows it. No PR unless explicitly requested. No merge, no
tag, no PyPI publish.

======================================================================
14. REQUIRED FINAL REPORT
======================================================================

- Confirm or correct §0's facts against what you actually found (call out
  any drift from this document).
- Which AI CLI was used, detected version, invocation mode, and why.
- Exact generated prompt structure and response schema actually implemented.
- Where the GlobalId parameter strategy landed and why (new vs. reused).
- Confirm no file GlobalId was introduced.
- Tests executed and results.
- Files changed.
- Any unresolved architectural question.

======================================================================
15. DEFINITION OF DONE
======================================================================

1. `ontobdc context --entity WorkStream --global-id <ID> --dimension who --suggest`
   resolves the WorkStream, resolves Who, gathers bounded candidates, calls
   a real AI CLI, validates the response, and persists Proposed suggestions
   into `.__ontobdc__/linkset/WorkStreamSuggested.ttl` in the existing RDF
   shape.
2. Opening that WorkStream's page in the browser (existing View, untouched)
   shows those resources under the Suggested tab for Who, with no code
   changes needed on the View side.
3. Running the same command with `--dimension where` can produce a
   different suggestion set from the same resource universe.
4. Accepting a suggestion in the View promotes it to Related through the
   existing linkset mechanism; the AI never wrote a Related link directly.
5. No `.__ontobdc__/relation/`, no invented predicate/class, no file
   GlobalId, no new persistence sidecar was introduced.
6. Everything runs local-first, no central platform dependency.
