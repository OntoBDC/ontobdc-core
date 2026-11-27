from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.job.adapter.job_cleaner import JobCleaner
from ontobdc.job.adapter.job_delete_command import JobDeleteCommand


class JobPurgeCommand(JobDeleteCommand):
    """
    Delete every job that is not executing, in every container or in one.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="job_purge",
        logical_component="job",
        description="Delete every job that is not executing, in every container or in one.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the only container whose jobs are deleted, by storage identifier or filesystem path. "
                    "When omitted, the jobs of every registered container are."
                ),
                "type": "str",
            },
            {
                "accepts": ["--purge"],
                "description": "Delete every job, finished or not, but the ones that are executing.",
                "usage": "ontobdc job --purge [--container <id-or-path>]",
            },
        ],
    )

    FLAG: ClassVar[str] = "--purge"
    TITLE: ClassVar[str] = "Purge"
    DONE: ClassVar[str] = "Purged"

    @staticmethod
    def delete(container_path: Path, container_id: str) -> List[Dict[str, Any]]:
        return JobCleaner.purge(container_path, container_id)
