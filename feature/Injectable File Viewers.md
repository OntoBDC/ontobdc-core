# Prompt — Implement Injectable File Viewers

Implement the **Injectable File Viewers** feature for InfoBIM/OntoBDC.

## Branch rule for this feature

Before making **any code or architecture change**, create a **new branch dedicated specifically to this feature** from the current appropriate baseline branch of `EliasMPJunior/ontobdc-wip`.

Use a feature-specific branch name such as:

`feat/injectable-file-viewers`

Do all implementation work for this feature on that separate branch. Do not implement this feature directly on `master`/the default branch and do not reuse an unrelated existing branch.

Treat this document as the authoritative functional/architectural specification for this feature. Do not simplify it into a generic plugin system and do not move BIM-specific behavior into OntoBDC core.

## Repositories to inspect

At minimum inspect the current branches/default branches of:

- `EliasMPJunior/ontobdc-wip`  
- `EliasMPJunior/ontobdc-view`  
- `EliasMPJunior/infobim-wip`

Also inspect the historical InfoBIM implementation that previously handled DWG visualization, especially the old same-stem representation lookup behavior. Use old code only as behavioral evidence; adapt it to the current architecture rather than copying obsolete structure.

## First: verify current architecture before editing

Before changing code, determine from the current codebase:

1. the exact OntoBDC View Sismic/statechart pipeline used by `infobim view`;  
2. where file-tree/file-preview JavaScript is currently assembled and packaged;  
3. how MIME/type-specific viewers are represented or dispatched today;  
4. the current extension mechanism used by InfoBIM to specialize OntoBDC View generation;  
5. where the cleanest generation state/transition for viewer assembly belongs;  
6. how offline JavaScript assets are embedded/copied into the final Surface;  
7. how generic OntoBDC code currently falls back for unsupported resources.

Do not assume names or paths from older versions. Follow the current architecture and existing conventions.

## Architectural target

OntoBDC must remain generic.

The generic architecture must support assembly/registration of available file-viewer JavaScript modules during Surface generation. A viewer is selected at browser runtime according to the resource MIME/type and viewer availability.

InfoBIM must extend that mechanism by contributing BIM-specific viewers. The first required domain viewer is DWG.

Do **not** teach OntoBDC core what DWG is.

The intended conceptual flow is:

`generic OntoBDC View generation -> assemble available file viewers -> domain/plugin contributions -> package offline Surface -> browser selects available viewer by MIME/type`

Use Sismic/statecharts to orchestrate the generation concern. Do not use Sismic to model the DWG viewer's internal PDF/image search.

## DWG viewer behavior

Implement the DWG-specific behavior inside the DWG viewer JavaScript.

For a logical resource such as `drawing.dwg`:

1. keep `drawing.dwg` as the logical resource;  
2. inspect the same folder for `drawing.pdf`;  
3. if it exists, use the PDF as display representation;  
4. otherwise inspect the same folder for a supported same-stem image (`drawing.png`, `drawing.jpg`, etc., according to existing supported image viewer behavior);  
5. if found, use that image as display representation;  
6. if neither exists, fall back cleanly to the generic unsupported/default behavior;  
7. do not implement native DWG/vector rendering.

Required priority:

`DWG -> same-stem PDF -> same-stem image -> fallback`

The PDF/image is a **display representation only**. Do not replace the DWG's identity in the tree, semantic relations, WorkStream relations, annotations or resource model.

## Chain of Responsibility

If the current architecture benefits from it, model generation-time viewer contributions as an ordered Chain of Responsibility (or reuse an existing equivalent extension chain):

`core viewer contributors -> installed/domain viewer contributors -> assembled viewer set`

The chain concerns contribution/assembly during generation.

Do **not** implement the PDF-then-image DWG lookup as a generic Chain of Responsibility in OntoBDC. That lookup belongs inside the DWG viewer JS because it is specific to that MIME/domain behavior.

## Statechart requirement

Add or extend the View generation statechart so viewer assembly is an explicit generation responsibility if the current pipeline does not already expose an equivalent state.

Important constraints:

- preserve the standard OntoBDC View pipeline as authoritative;  
- InfoBIM should specialize/extend the existing flow, not build a second HTML generation pipeline;  
- reuse current transition/capability conventions;  
- preserve state preconditions/postconditions and existing architecture patterns;  
- no giant procedural helper that bypasses the machine;  
- no direct InfoBIM HTML construction if `ontobdc-view` already owns final packaging.

If an existing state already naturally performs asset/component assembly, extend that responsibility cleanly rather than creating a redundant state merely to match this prompt's wording.

## Browser/runtime requirement

The generic file tree/runtime must not contain logic like:

- `if InfoBIM ...`  
- `if extension === '.dwg' ...`  
- BIM-specific same-stem lookup rules.

It should only do the generic equivalent of:

- determine the file MIME/type;  
- find an available viewer registered for that type;  
- invoke it;  
- use generic fallback when none is available.

The domain-specific viewer owns domain-specific resolution rules.

## Platform independence / offline requirement

The final generated Surface must remain self-contained/offline according to current OntoBDC View rules.

No server, cloud API or installed CAD application may be required to preview DWG through its sibling PDF/image representation.

The browser should be agnostic to whether the viewer came from OntoBDC or InfoBIM once generation has packaged it.

## Tests required

Add regression tests at the appropriate layers. At minimum prove:

1. OntoBDC alone still generates a valid Surface without InfoBIM-specific DWG knowledge.  
2. The generation pipeline can assemble/accept viewer contributions.  
3. InfoBIM contributes/registers/packages the DWG viewer.  
4. A DWG with a same-stem PDF resolves to the PDF representation.  
5. A DWG without PDF but with same-stem supported image resolves to that image.  
6. PDF takes precedence when both PDF and image exist.  
7. A DWG with neither representation falls back cleanly.  
8. The logical resource remains the DWG even when another display representation is used.  
9. Existing generic file-tree/viewer behavior does not regress.  
10. The generated Surface remains offline/self-contained.

Prefer tests against real current interfaces/contracts rather than brittle string-only tests where a behavioral test is practical.

## Architecture guardrails

Do not:

- add DWG semantics to OntoBDC ontology/core unless an already-existing generic representation concept legitimately needs reuse;  
- hard-code future BIM formats into generic code;  
- create a native DWG renderer;  
- replace the generic file tree with an InfoBIM-specific tree;  
- create a second View pipeline;  
- change logical resource identity when choosing a display representation;  
- copy old InfoBIM modules blindly if they violate current architecture;  
- introduce a new abstraction when the current code already has an equivalent extension mechanism.

## Work procedure

1. Inspect current code and historical DWG behavior.  
2. Write down the exact current flow and the minimal extension point you will use.  
3. Implement the generic viewer-contribution/assembly support in the correct repository/layer.  
4. Implement the InfoBIM DWG viewer contribution.  
5. Restore the same-stem PDF/image behavior inside that viewer.  
6. Integrate with current offline packaging.  
7. Add/update tests.  
8. Run the relevant test suites for all touched repositories.  
9. Run an end-to-end `infobim view` scenario that produces a Surface containing the DWG viewer and exercise the three cases: PDF sibling, image-only sibling, no sibling representation.  
10. Inspect the generated HTML/assets to confirm the viewer is actually packaged and used, not merely registered in Python code.

## Deliverable

Return a concise implementation report containing:

- repositories and files changed;  
- statechart/state/transitions affected;  
- exact extension mechanism used;  
- how viewer registration/dispatch works;  
- how the DWG viewer resolves PDF/image siblings;  
- tests run and their results;  
- end-to-end evidence that generated InfoBIM HTML can display the DWG through the intended representation;  
- any architectural deviation from this specification, with justification.

Do not claim completion unless the feature is actually wired into generated InfoBIM output and exercised end to end.
