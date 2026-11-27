from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.job.plugin.machine.job_create.port import JobCreateProcessStatePort
from ontobdc.shared.adapter.etl_state import EtlStateFile


class JobCreateEtlEvent:
    """
    The ETL file every state of the creation of a job leaves::

        <container>/.__ontobdc__/etl/job/<md5 of the IRI of the procedure>/<state>.json
    """

    ETL_MODULE_NAME: ClassVar[str] = "job"

    @classmethod
    def write(
        cls,
        container_path: Path,
        procedure_iri: str,
        state: JobCreateProcessStatePort,
        result: Dict[str, Any],
    ) -> Path:
        return EtlStateFile.write_by_iri(
            container_path, cls.ETL_MODULE_NAME, procedure_iri, state.value.strip("_"), result
        )
