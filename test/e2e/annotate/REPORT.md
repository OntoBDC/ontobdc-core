# Annotation test report

## Scope and final execution

Both checkouts are on `daybreak-release`. The final runs used ontobdc
`2a2041d7` and infobim `20ef455d`, Python 3.14 and PySide6 6.11.2.
Only new files under `test/` are delivered. No production changes remain.
The pre-existing change to infobim's `pyproject.toml` was preserved.

| Repository / command | Final result |
| --- | --- |
| ontobdc: `PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/machine/annotation` | **64 passed, 10 failed**, 10.68 s |
| infobim: `QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/annotation test/unit/annotation` | **32 passed, 3 failed**, 60.68 s |
| Existing infobim baseline: `PYTHONPATH="$PWD/src:$PWD" python -m pytest -q test/e2e/project/test_project_update_command.py -k persists_metadata` | **6 failed, 12 deselected**, 19.25 s; excluded from annotation results |

The actual interpreter was `../.venv/bin/python` from each checkout. All failing
new tests assert the requested behavior and remain active, without skip/xfail.
The 109 new collected cases comprise 96 passing cases and 13 defect assertions.
Deprecation warnings from rdflib JSON-LD and SWIG do not change the results.

## Coverage

- **Installed CLI / e2e:** module help, invalid and incomplete routes, both flag
  orders, immediate repository requirement and unchanged container snapshot;
  real project creation, real DXF loading, point capture and form input,
  JSON response, exact eight-column CSV and complete values, UUID, date, WKT,
  typed dataset, percent-encoded origin IRI, directed ISO linkset and ETL;
  IRI/identifier/Portuguese type names, unknown and ambiguous names;
  consecutive commands sharing a CSV, cancellation, location/project guards,
  DWG failure contract and immutable persistent context file.
- **Annotation FSM:** prerequisites and failure boundary, actual persisted
  observations, existing action ETL never completing a new invocation,
  resume/backfill with empty events, four unregistered MIME/empty-chain errors,
  missing title, valid and invalid MIME maps, actual capability dispatch,
  live-object serialization and atomic ETL replacement. InfoBIM's in-process
  real Qt test compares performed events against transition targets read from
  the actual YAML, rather than comparing two constants.
- **Entity writing:** every observed state, partial resume, idempotence,
  same-ID content replacement and removal of optional text, facade validation,
  missing repository/facade, directory collision, document union and retained
  links. A test-owned `EntityRepositoryPort` implementation is the only fake
  production port; all FSMs, capabilities, RDF metadata and checks are real.
- **Dataset / identity / facade:** each dataset state, invalid file target,
  idempotence, declared entity type and custom title, general and entity-aware
  metadata checks, untyped datasets, encoded identifiers/accents/spaces/path
  separators and outside-container rejection, real published facade column
  order and required fields.
- **Model / repository / Qt:** blank required model fields, empty point list,
  point and line geometry including negative/scientific values, omitted optional
  fields, context preservation/leak contracts; CSV header creation, idempotent
  columns, physical row order and replacement, append, invalid input without
  modifying the file, Unicode/commas/quotes/newlines/WKT, no temporary residue,
  newest-file selection and deterministic public-upsert concurrency;
  required form title, optional fields and whitespace trimming, cancellation,
  double-click behavior, annotation/IFC window lifecycle.

Unit/machine fixtures prepare temporary config and disk metadata through real
standalone check/hotfix APIs, **without CLI subprocesses**. E2e fixtures use real
installed commands. The Qt driver invokes the actual `infobim.cli.main()` in a
subprocess; its QTimers simulate human interaction only. Its pre-CLI ezdxf Qt
binding announcement goes to stderr, so the harness does not pollute JSON stdout.

Ambiguity requires conflicting ontology data: tests copy the published taxonomy,
add the same label to two existing types, and redirect the external
brasidatacenter resource provider to that temporary catalog. Ontobdc/InfoBIM
functions are not mocked. Catalog paths are derived from the published IRI;
there is no prefix/namespace lookup table and no developer ontology is changed.

The command always allocates a new UUID and exposes no global-ID argument.
The same-ID e2e case therefore creates an annotation through the command, then
resaves its actual ID through the public `Annotation.save` API in a second real
subprocess. It verifies physical CSV replacement; it does not pretend that the
CLI has a nonexistent update option.

## All twelve suspected issues

| # | Finding and proving test | Classification |
| --- | --- | --- |
| 1 | `test_save_restores_callers_existing_context_parameters` fails for **all five keys**: container_path, dataset_path, dataset_entity_iri, entity_records, entity_source_documents. After a successful save their previous values are gone. | Confirmed defect; 5 failing cases |
| 2 | `test_save_does_not_leak_dataset_title_into_caller_context` and `test_nonisolated_save_must_not_persist_internal_dataset_title` both fail: the facade title survives and a fresh persistent context reads it. `test_isolated_save_keeps_persistent_context_file_unchanged` and the CLI happy cases pass. | Persistent/in-memory leak confirmed; 2 failing cases. Isolated CLI disk persistence does **not** leak. |
| 3 | `test_geometry_preserves_cad_coordinate_precision` fails: 7500123.456 becomes 7500120; 1234567.891 becomes 1234570. The 1e-07, 1.5, integer and -0.25 spelling cases pass. | Confirmed defect; 1 failing case. Scientific notation itself is acceptable, but six significant digits are insufficient for CAD fidelity. |
| 4 | `test_immediate_pre_double_click_is_discarded_and_previous_click_retained` passes, including a previous committed point and the final point. | Confirmed intended contract, not a defect |
| 5 | `test_linkset_unions_sources_and_retains_previous_document_after_replacement` checks RDF using imported ICDD vocabulary and separately confirms HTTPS versus existing CT's HTTP. E2e validates the CSV document and directed origin link. | Divergence confirmed. No assertion about which namespace ISO officially prescribes. |
| 6 | The existing six update cases still fail. Three cwd variants raise FileNotFoundError for the absent resource facade; three ID variants fail routing with CliCommandArgumentException before loading it. Direct `DataContainerFacade.read()` also raises FileNotFoundError. | Known unrelated baseline; not repaired and not counted as annotation regressions |
| 7 | `test_two_public_upserts_interleaved_at_read_boundary_lose_first_row` pauses two real public upserts at `_read` return using Python tracing and Events. A writes, then B replaces its stale snapshot; only B remains. No repository method is replaced. | Lost update confirmed. Passing documentation of the explicitly requested current behavior; no locking fix. |
| 8 | `test_newest_csv_receives_writes_and_older_csv_is_ignored` passes: only newer rows are read, the new row goes to the newer file, older bytes stay unchanged. | Confirmed current behavior |
| 9 | `test_linkset_unions_sources_and_retains_previous_document_after_replacement` passes: moving the single stored annotation from plan-a to plan-b retains both links. | Monotonic retention confirmed. There is no public annotation-delete API, so no nonexistent deletion operation is simulated. |
| 10 | CLI `test_unhandled_type_or_dwg_is_clear_and_does_not_persist[dwg]` and machine `test_missing_mime_metadata_must_not_block_before_responsibility_lookup` fail: actual exception is PostconditionError, not the requested LookupError. `SingleFileMetadataExtractedCapability.is_satisfied` rejects MIME None for a file with a suffix. | Unsupported DWG confirmed; **clear MIME LookupError behavior not confirmed**. 2 failing cases across repositories. |
| 11 | `test_directory_collision_is_not_silently_adopted` passes with FileExistsError and zero repository writes. | Confirmed contract |
| 12 | `test_undefined_transition_validation_does_not_hide_action_error` passes: validation returns False, but the actual collision still raises the original FileExistsError. Invalid rows and missing facade also raise their original errors. | False return confirmed. Error masking was **not reproduced** in the exercised real action failures. |

## Additional differences from the description

1. **Initial ETL is absent.** The complete flow writes seven state JSON files
   plus the annotation type JSON-LD: eight files total, not eight state JSON
   files. E2e checks that actual eight-file total. The separate
   `test_initial_undefined_state_has_its_own_etl_event` remains failing against
   the requested event-per-state contract. The failure-boundary test independently
   passes and verifies only type and metadata events precede the failed loader.
2. **Viewer survives but becomes hidden.** The annotation points capability
   does not destroy the session, but `DxfViewerSession.capture_points()` accepts
   its modal dialog when capture finishes, hiding the window. Two active tests
   remain failing: `test_viewer_stays_visible_while_annotation_details_are_requested`
   and `test_point_capabilities_keep_annotation_window_but_close_ifc_window[annotation]`.
   The original IFC capture still destroys its window; cancellation always
   closes the annotation session; both contracts pass.
3. **JSON error strings contain Rich line wrapping.** E2e message matching reads
   parsed `content.error` and removes inserted newline characters. Exception
   classes are checked separately in JSON `description`, preserving the real
   command's machine-readable contract without mistaking wrapping for a defect.
4. During mutation work an append-instead-of-replace mutation initially survived
   a dictionary-only assertion because `rows()` collapses repeated IDs. The test
   was strengthened to inspect the physical CSV rows, then the mutation was
   rerun and detected. No surviving mutation is counted as a successful proof.

## Mutation proof

Every row below had a passing selected baseline (exit 0), then a failing selected
pytest run (exit 1, an actual FAILED test, not a collection error). Production
bytes were restored in `finally`. All **34 original SHA-256 hashes** were checked
again after the final mutation run; both production source diffs are empty.

The reproducible explicit runner is
`test/machine/annotation/mutation_check.py`; its machine-readable evidence is
`test/machine/annotation/mutation_results.json`. It is never executed by ordinary
pytest collection. Run it separately with the shared virtualenv, with no other
process editing the affected source files. Already-failing defect assertions are
reported above rather than mislabeled as passing mutation baselines.

| # | Deliberate break | Test that caught it | Baseline → mutant exit |
| --- | --- | --- | --- |
| 1 | WKT coordinate order | `test/machine/annotation/test_annotation_model.py::test_geometry_preserves_order_and_numeric_forms` | 0 → 1 |
| 2 | Required nonblank model fields | `test/machine/annotation/test_annotation_model.py::test_rejects_blank_required_fields` | 0 → 1 |
| 3 | Omitted optional fields | `test/machine/annotation/test_annotation_model.py::test_record_omits_only_missing_optional_values` | 0 → 1 |
| 4 | Repository must be injected | `test/machine/annotation/test_entity_write.py::test_repository_is_required_at_handler_construction` | 0 → 1 |
| 5 | Columns must be synchronized | `test/machine/annotation/test_entity_write.py::test_resume_only_fills_missing_columns_rows_and_links` | 0 → 1 |
| 6 | Rows must be persisted | `test/machine/annotation/test_entity_write.py::test_resume_only_fills_missing_columns_rows_and_links` | 0 → 1 |
| 7 | Facade row validation | `test/machine/annotation/test_entity_write.py::test_invalid_row_fails_before_repository_writes_and_blocks_links` | 0 → 1 |
| 8 | Content changes must trigger rewriting | `test/machine/annotation/test_entity_write.py::test_changed_content_replaces_existing_row_and_removed_text_becomes_empty` | 0 → 1 |
| 9 | Link union must preserve previous origins | `test/machine/annotation/test_entity_write.py::test_linkset_unions_sources_and_retains_previous_document_after_replacement` | 0 → 1 |
| 10 | Dataset title must be applied | `test/machine/annotation/test_dataset_and_document.py::test_dataset_states_typing_title_and_idempotence` | 0 → 1 |
| 11 | Dataset must carry entity type | `test/machine/annotation/test_dataset_and_document.py::test_dataset_states_typing_title_and_idempotence` | 0 → 1 |
| 12 | Document paths must be encoded | `test/machine/annotation/test_dataset_and_document.py::test_document_iri_encodes_identifier_accents_spaces_but_preserves_directory_separator` | 0 → 1 |
| 13 | Type event must match requested type | `test/machine/annotation/test_creation_machine.py::test_resolves_real_published_type_and_observes_matching_event` | 0 → 1 |
| 14 | Ambiguous type must be rejected | `test/machine/annotation/test_creation_machine.py::test_ambiguous_external_ontology_data_reports_all_matches` | 0 → 1 |
| 15 | Invalid MIME registry must fail | `test/machine/annotation/test_creation_machine.py::test_invalid_mime_map_is_rejected` | 0 → 1 |
| 16 | Filled details need a title | `test/machine/annotation/test_creation_machine.py::test_registered_capability_without_annotation_title_is_rejected` | 0 → 1 |
| 17 | Annotations must use drawing container | `test/machine/annotation/test_creation_machine.py::test_annotations_created_uses_file_container_instead_of_stale_context` | 0 → 1 |
| 18 | Live objects must be serializable | `test/machine/annotation/test_creation_machine.py::test_etl_describes_live_objects_and_replaces_atomically` | 0 → 1 |
| 19 | CSV upsert must replace | `test/unit/annotation/test_csv_repository.py::test_upsert_replaces_in_place_appends_and_empties_omitted_fields` | 0 → 1 |
| 20 | Newest CSV must be selected | `test/unit/annotation/test_csv_repository.py::test_newest_csv_receives_writes_and_older_csv_is_ignored` | 0 → 1 |
| 21 | CSV must reject unknown columns | `test/unit/annotation/test_csv_repository.py::test_invalid_row_preserves_existing_csv` | 0 → 1 |
| 22 | CSV identifier required | `test/unit/annotation/test_csv_repository.py::test_invalid_row_preserves_existing_csv` | 0 → 1 |
| 23 | Blank title disables OK | `test/unit/annotation/test_qt_contracts.py::test_ok_requires_nonblank_title` | 0 → 1 |
| 24 | Form must omit blank optionals | `test/unit/annotation/test_qt_contracts.py::test_details_trim_values_and_omit_blank_optionals` | 0 → 1 |
| 25 | Double click discards pending click | `test/unit/annotation/test_qt_contracts.py::test_immediate_pre_double_click_is_discarded_and_previous_click_retained` | 0 → 1 |
| 26 | Command must append to same CSV | `test/e2e/annotation/test_annotation_command.py::test_second_command_appends_to_same_csv` | 0 → 1 |
| 27 | State actions must follow YAML transitions | `infobim:test/unit/annotation/test_creation_machine.py::test_real_machine_executes_yaml_transition_order_and_closes_viewer` | 0 → 1 |
| 28 | Empty responsibility chains must report LookupError | `test/machine/annotation/test_creation_machine.py::test_each_empty_mime_mapping_and_chain_fails_clearly` | 0 → 1 |
| 29 | CSV replacement must finish atomically | `test/unit/annotation/test_csv_repository.py::test_quotes_newlines_unicode_and_wkt_round_trip_without_temporary_files` | 0 → 1 |
| 30 | Repository absence must precede any ETL | `test/e2e/annotation/test_annotation_command.py::test_valid_flag_orders_fail_immediately_without_repository` | 0 → 1 |
| 31 | Annotation details cancellation must close viewer | `test/unit/annotation/test_qt_contracts.py::test_annotation_details_cancel_always_closes_viewer` | 0 → 1 |
| 32 | IFC capture must continue closing its viewer | `test/unit/annotation/test_qt_contracts.py::test_point_capabilities_keep_annotation_window_but_close_ifc_window[ifc]` | 0 → 1 |
| 33 | Blank title blocks real command form | `test/e2e/annotation/test_annotation_command.py::test_blank_title_disables_ok_in_real_command_form` | 0 → 1 |
| 34 | Readers must see old CSV until atomic replacement | `test/unit/annotation/test_csv_repository.py::test_atomic_update_keeps_previous_complete_csv_visible_until_replace` | 0 → 1 |

No commit or push was requested for this test task; the files remain available
for review on the requested branch.
