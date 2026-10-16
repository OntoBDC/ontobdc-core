"""Real disk/context setup and a test-owned implementation of the repository port."""

from pathlib import Path
from ontobdc.cli.adapter.context import IsolatedCliContextAdapter
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from test.e2e.container_workspace import ContainerE2eWorkspace


class MemoryRepository(EntityRepositoryPort):
    def __init__(self):
        self.sources = {}
        self.writes = 0

    def data_source_exists(self, dataset_path):
        return Path(dataset_path) in self.sources

    def create_data_source(self, dataset_path):
        self.sources[Path(dataset_path)] = (["global_id"], {})
        path = self.data_source_path(dataset_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("global_id\n")
        return path

    def data_source_path(self, dataset_path):
        return Path(dataset_path) / "payload/document/annotations.csv"

    def columns(self, dataset_path):
        return list(self.sources[Path(dataset_path)][0])

    def add_columns(self, dataset_path, columns):
        existing = self.sources[Path(dataset_path)][0]
        existing.extend(column for column in columns if column not in existing)

    def rows(self, dataset_path):
        return {
            key: dict(value)
            for key, value in self.sources[Path(dataset_path)][1].items()
        }

    def upsert_rows(self, dataset_path, records):
        columns, rows = self.sources[Path(dataset_path)]
        for record in records:
            rows[str(record["global_id"])] = {
                column: "" if record.get(column) is None else str(record[column])
                for column in columns
            }
        self.writes += 1

    def delete_rows(self, dataset_path, global_ids):
        _, rows = self.sources[Path(dataset_path)]
        for global_id in global_ids:
            rows.pop(str(global_id), None)


def workspace(tmp_path):
    from ontobdc.container.adapter.document_iri import ContainerDocumentIri
    from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
        main as metadata,
    )
    from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
        main as index,
    )
    from ontobdc.container.plugin.check.is_container_datapackage_updated.hotfix import (
        main as datapackage,
    )
    from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
        main as manifest,
    )

    root = tmp_path.resolve()
    configuration = root / ".__ontobdc__"
    configuration.mkdir()
    (configuration / "config.yaml").write_text("context: {}\n")
    container = root / "container-under-test"
    container.mkdir()
    for prepare in [metadata, index, datapackage, manifest]:
        assert prepare(container_path=str(container), root_path=str(root)) == 0
    disk = ContainerE2eWorkspace(
        root, container, ContainerDocumentIri.container_id(container)
    )
    context = IsolatedCliContextAdapter([], root_dir=str(root))
    return disk, context


def put(context, **values):
    for key, value in values.items():
        context.set_parameter_value(key, value)
    return context
