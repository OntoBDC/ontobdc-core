"""Explicit, reversible mutation checks; never imported or run by pytest.

Run with the shared virtualenv Python from either checkout. Each selected test
must pass first, then fail with a behavioral assertion under its mutation.
Every source is restored byte-for-byte in finally, including on interruption.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT.parent
M = "test/machine/annotation/"
U = "test/unit/annotation/"
E = "test/e2e/annotation/"
CASES = [
    (
        "WKT coordinate order",
        "ontobdc",
        "annotation/domain/model/annotation.py",
        'f"{point.x:g} {point.y:g}"',
        'f"{point.y:g} {point.x:g}"',
        M + "test_annotation_model.py::test_geometry_preserves_order_and_numeric_forms",
    ),
    (
        "Required nonblank model fields",
        "ontobdc",
        "annotation/domain/model/annotation.py",
        "if not value.strip():",
        "if False:",
        M + "test_annotation_model.py::test_rejects_blank_required_fields",
    ),
    (
        "Omitted optional fields",
        "ontobdc",
        "annotation/domain/model/annotation.py",
        "if self.text is not None:",
        "if True:",
        M + "test_annotation_model.py::test_record_omits_only_missing_optional_values",
    ),
    (
        "Repository must be injected",
        "ontobdc",
        "container/plugin/machine/entity_write/machine.py",
        "if not isinstance(repository, EntityRepositoryPort):",
        "if False:",
        M + "test_entity_write.py::test_repository_is_required_at_handler_construction",
    ),
    (
        "Columns must be synchronized",
        "ontobdc",
        "container/plugin/capability/transformation/data_source_columns_synced.py",
        "repository.add_columns(dataset_path, missing)",
        "pass",
        M
        + "test_entity_write.py::test_resume_only_fills_missing_columns_rows_and_links",
    ),
    (
        "Rows must be persisted",
        "ontobdc",
        "container/plugin/capability/transformation/data_source_filled.py",
        "repository.upsert_rows(dataset_path, records)",
        "pass",
        M
        + "test_entity_write.py::test_resume_only_fills_missing_columns_rows_and_links",
    ),
    (
        "Facade row validation",
        "ontobdc",
        "container/plugin/capability/transformation/data_source_filled.py",
        "self._validate(facade, record)",
        "pass",
        M
        + "test_entity_write.py::test_invalid_row_fails_before_repository_writes_and_blocks_links",
    ),
    (
        "Content changes must trigger rewriting",
        "ontobdc",
        "container/plugin/machine/entity_write/machine.py",
        'if (stored.get(column) or "") != ("" if value is None else str(value)):',
        "if False:",
        M
        + "test_entity_write.py::test_changed_content_replaces_existing_row_and_removed_text_becomes_empty",
    ),
    (
        "Link union must preserve previous origins",
        "ontobdc",
        "container/plugin/capability/transformation/entity_documents_linked.py",
        "set(linkset.links()) | set(EntityWriteRequest.source_documents(context))",
        "set(EntityWriteRequest.source_documents(context))",
        M
        + "test_entity_write.py::test_linkset_unions_sources_and_retains_previous_document_after_replacement",
    ),
    (
        "Dataset title must be applied",
        "ontobdc",
        "container/plugin/capability/transformation/dataset_metadata_ready.py",
        "DatasetTitleRepository(Path(target_path)).write_title(dataset_title)",
        "pass",
        M
        + "test_dataset_and_document.py::test_dataset_states_typing_title_and_idempotence",
    ),
    (
        "Dataset must carry entity type",
        "ontobdc",
        "container/plugin/check/is_dataset_metadata_ready/hotfix.py",
        "dataset_graph.add((data_entity_ref, RDF.type, URIRef(entity_iri)))",
        "pass",
        M
        + "test_dataset_and_document.py::test_dataset_states_typing_title_and_idempotence",
    ),
    (
        "Document paths must be encoded",
        "ontobdc",
        "container/adapter/document_iri.py",
        "quote(relative_path, safe='/')",
        "relative_path",
        M
        + "test_dataset_and_document.py::test_document_iri_encodes_identifier_accents_spaces_but_preserves_directory_separator",
    ),
    (
        "Type event must match requested type",
        "ontobdc",
        "annotation/plugin/capability/transformation/annotation_type_identified.py",
        "return set(event_graph) == set(type_graph)",
        "return True",
        M
        + "test_creation_machine.py::test_resolves_real_published_type_and_observes_matching_event",
    ),
    (
        "Ambiguous type must be rejected",
        "ontobdc",
        "annotation/plugin/capability/transformation/annotation_type_identified.py",
        "if len(matches) > 1:",
        "if False:",
        M
        + "test_creation_machine.py::test_ambiguous_external_ontology_data_reports_all_matches",
    ),
    (
        "Invalid MIME registry must fail",
        "ontobdc",
        "shared/adapter/mime_capability.py",
        "if not isinstance(capabilities_by_mime, dict):",
        "if False:",
        M + "test_creation_machine.py::test_invalid_mime_map_is_rejected",
    ),
    (
        "Filled details need a title",
        "ontobdc",
        "annotation/plugin/capability/loader/annotation_details_filled.py",
        "if not isinstance(title, str) or not title.strip():",
        "if False:",
        M
        + "test_creation_machine.py::test_registered_capability_without_annotation_title_is_rejected",
    ),
    (
        "Annotations must use drawing container",
        "ontobdc",
        "annotation/plugin/capability/transformation/annotations_created.py",
        "ContainerDocumentIri.container_of(file_path)",
        'Path(context.get_parameter_value("container_path"))',
        M
        + "test_creation_machine.py::test_annotations_created_uses_file_container_instead_of_stale_context",
    ),
    (
        "Live objects must be serializable",
        "ontobdc",
        "annotation/plugin/machine/annotation_creation_from_point/etl.py",
        "default=cls._describe,",
        "",
        M
        + "test_creation_machine.py::test_etl_describes_live_objects_and_replaces_atomically",
    ),
    (
        "CSV upsert must replace",
        "infobim",
        "annotation/adapter/csv_repository.py",
        "existing[positions[identifier]] = written",
        "existing.append(written)",
        U
        + "test_csv_repository.py::test_upsert_replaces_in_place_appends_and_empties_omitted_fields",
    ),
    (
        "Newest CSV must be selected",
        "infobim",
        "annotation/adapter/csv_repository.py",
        "return sources[-1] if sources else None",
        "return sources[0] if sources else None",
        U
        + "test_csv_repository.py::test_newest_csv_receives_writes_and_older_csv_is_ignored",
    ),
    (
        "CSV must reject unknown columns",
        "infobim",
        "annotation/adapter/csv_repository.py",
        "if unknown:",
        "if False:",
        U + "test_csv_repository.py::test_invalid_row_preserves_existing_csv",
    ),
    (
        "CSV identifier required",
        "infobim",
        "annotation/adapter/csv_repository.py",
        "if not identifier:",
        "if False:",
        U + "test_csv_repository.py::test_invalid_row_preserves_existing_csv",
    ),
    (
        "Blank title disables OK",
        "infobim",
        "_2d/adapter/annotation_details_form.py",
        "bool(self._title.text().strip())",
        "True",
        U + "test_qt_contracts.py::test_ok_requires_nonblank_title",
    ),
    (
        "Form must omit blank optionals",
        "infobim",
        "_2d/adapter/annotation_details_form.py",
        "if text:",
        "if True:",
        U + "test_qt_contracts.py::test_details_trim_values_and_omit_blank_optionals",
    ),
    (
        "Double click discards pending click",
        "infobim",
        "_2d/adapter/qt_viewer.py",
        "self._timer.stop()\n        self._pending = None\n        self._add(qc.QPointF(point))",
        "self._commit_pending()\n        self._add(qc.QPointF(point))",
        U
        + "test_qt_contracts.py::test_immediate_pre_double_click_is_discarded_and_previous_click_retained",
    ),
    (
        "Command must append to same CSV",
        "infobim",
        "annotation/adapter/csv_repository.py",
        "existing.append(written)",
        "existing[:] = [written]",
        E + "test_annotation_command.py::test_second_command_appends_to_same_csv",
    ),
]

CASES.extend(
    [
        (
            "State actions must follow YAML transitions",
            "ontobdc",
            "annotation/plugin/machine/annotation_creation_from_point/standard_annotation_creation_from_point.yaml",
            "action: handler.perform_state_transition(to_state = AnnotationCreationFromPointProcessStatePort.POINTS_CAPTURED)",
            "action: handler.perform_state_transition(to_state = AnnotationCreationFromPointProcessStatePort.ANNOTATION_DETAILS_FILLED)",
            "infobim:"
            + U
            + "test_creation_machine.py::test_real_machine_executes_yaml_transition_order_and_closes_viewer",
        ),
        (
            "Empty responsibility chains must report LookupError",
            "ontobdc",
            "shared/adapter/mime_chain_capability.py",
            'raise LookupError(f"{failure} «{file_path}».")',
            "return {}",
            M
            + "test_creation_machine.py::test_each_empty_mime_mapping_and_chain_fails_clearly",
        ),
        (
            "CSV replacement must finish atomically",
            "infobim",
            "annotation/adapter/csv_repository.py",
            "os.replace(temporary, path)",
            "pass",
            U
            + "test_csv_repository.py::test_quotes_newlines_unicode_and_wkt_round_trip_without_temporary_files",
        ),
        (
            "Repository absence must precede any ETL",
            "ontobdc",
            "annotation/plugin/command/point.py",
            "EntityWriteRequest.repository(context)",
            "None",
            E
            + "test_annotation_command.py::test_valid_flag_orders_fail_immediately_without_repository",
        ),
        (
            "Annotation details cancellation must close viewer",
            "infobim",
            "_2d/plugin/capability/loader/annotation_details.py",
            "session.close()",
            "pass",
            U
            + "test_qt_contracts.py::test_annotation_details_cancel_always_closes_viewer",
        ),
        (
            "IFC capture must continue closing its viewer",
            "infobim",
            "_2d/plugin/capability/loader/points.py",
            "session.close()",
            "pass",
            U
            + "test_qt_contracts.py::test_point_capabilities_keep_annotation_window_but_close_ifc_window[ifc]",
        ),
    ]
)

CASES.append(
    (
        "Blank title blocks real command form",
        "infobim",
        "_2d/adapter/annotation_details_form.py",
        "bool(self._title.text().strip())",
        "True",
        E
        + "test_annotation_command.py::test_blank_title_disables_ok_in_real_command_form",
    )
)

CASES.append(
    (
        "Readers must see old CSV until atomic replacement",
        "infobim",
        "annotation/adapter/csv_repository.py",
        'temporary: Path = path.with_name(f"{path.name}.tmp")',
        "temporary: Path = path",
        U
        + "test_csv_repository.py::test_atomic_update_keeps_previous_complete_csv_visible_until_replace",
    )
)


def run(repo, selector):
    if selector.startswith("infobim:"):
        repo, selector = selector.split(":", 1)
    directory = WORKSPACE / repo
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(directory / "src"), str(directory)])
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", selector],
        cwd=directory,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    report = Path(__file__).with_name("mutation_results.json")
    results = json.loads(report.read_text())[:start] if start else []
    for name, repo, relative, before, after, selector in CASES[start:]:
        source = WORKSPACE / repo / "src" / repo / relative
        original = source.read_bytes()
        original_stat = source.stat()
        text = original.decode()
        if before not in text:
            raise RuntimeError(f"Mutation anchor missing: {name}")
        baseline = run(repo, selector)
        if baseline.returncode:
            raise RuntimeError(
                f"Baseline failed: {name}\n{baseline.stdout}\n{baseline.stderr}"
            )
        cache = Path(importlib.util.cache_from_source(str(source)))
        try:
            source.write_text(text.replace(before, after, 1))
            cache.unlink(missing_ok=True)
            mutant = run(repo, selector)
            detected = (
                mutant.returncode == 1
                and "FAILED " in mutant.stdout
                and "ERROR collecting" not in mutant.stdout
            )
        finally:
            source.write_bytes(original)
            os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            cache.unlink(missing_ok=True)
        assert source.read_bytes() == original
        result = dict(
            mutation=name,
            repository=repo,
            test=selector,
            detected=detected,
            baseline_exit=baseline.returncode,
            mutant_exit=mutant.returncode,
            source_sha256=hashlib.sha256(original).hexdigest(),
            failures=[
                line
                for line in mutant.stdout.splitlines()
                if line.startswith("FAILED ")
            ],
        )
        results.append(result)
        (Path(__file__).with_name("mutation_results.json")).write_text(
            json.dumps(results, indent=2) + "\n"
        )
        print(
            f"{len(results)}/{len(CASES)} {'DETECTED' if detected else 'SURVIVED'}: {name}",
            flush=True,
        )
        if not detected:
            raise RuntimeError(
                f"Mutation survived: {name}\n{mutant.stdout}\n{mutant.stderr}"
            )


if __name__ == "__main__":
    main()
