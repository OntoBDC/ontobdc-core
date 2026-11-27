from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.job.adapter.job_cleaner import JobCleaner
from ontobdc.job.adapter.job_delete_command import JobDeleteCommand


class JobClearCommand(JobDeleteCommand):
    """
    Delete the jobs that completed with no error, in every container or in one.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="job_clear",
        logical_component="job",
        description="Delete the jobs that completed with no error, in every container or in one.",
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
                "accepts": ["--clear"],
                "description": "Delete the jobs whose run completed with no error.",
                "usage": "ontobdc job --clear [--container <id-or-path>]",
            },
        ],
    )

    FLAG: ClassVar[str] = "--clear"
    TITLE: ClassVar[str] = "Clear"
    DONE: ClassVar[str] = "Cleared"

    @staticmethod
    def delete(container_path: Path, container_id: str) -> List[Dict[str, Any]]:
        return JobCleaner.clear(container_path, container_id)
