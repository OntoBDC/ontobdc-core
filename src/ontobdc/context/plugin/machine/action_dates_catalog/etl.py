from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.context.plugin.machine.action_dates_catalog.port import ActionDatesCatalogProcessStatePort
from ontobdc.shared.adapter.etl_state import EtlStateFile


class ActionDatesCatalogEtlEvent:
    """
    The ETL file every state of the cataloging of the dates of the actions leaves::

        <container>/.__ontobdc__/etl/context/<md5 of the IRI of the procedure>/<state>.json
    """

    ETL_MODULE_NAME: ClassVar[str] = "context"

    @classmethod
    def write(
        cls,
        container_path: Path,
        procedure_iri: str,
        state: ActionDatesCatalogProcessStatePort,
        result: Dict[str, Any],
    ) -> Path:
        return EtlStateFile.write_by_iri(
            container_path, cls.ETL_MODULE_NAME, procedure_iri, state.value.strip("_"), result
        )
