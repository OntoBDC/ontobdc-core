from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ontobdc.job.adapter.job_listing import ContainerJobs
from ontobdc.job.adapter.job_store import JobStore
from ontobdc.shared.domain.vocabulary import JOB


class JobCleaner:
    """
    Deletes the jobs of a container that are done with: the ones that completed with no error (``clear``), or
    every one that is not executing (``purge``). A job that is executing is never deleted.
    """

    COMPLETED: str = str(JOB.Completed).rsplit("#", 1)[-1]
    EXECUTING: str = str(JOB.Executing).rsplit("#", 1)[-1]

    @classmethod
    def clear(cls, container_path: Path, container_id: str) -> List[Dict[str, Any]]:
        """Deletes the jobs whose run completed, and gives them as they were listed."""
        return cls._delete(container_path, container_id, lambda status: status == cls.COMPLETED)

    @classmethod
    def purge(cls, container_path: Path, container_id: str) -> List[Dict[str, Any]]:
        """Deletes every job but the ones that are executing, and gives them as they were listed."""
        return cls._delete(container_path, container_id, lambda status: status != cls.EXECUTING)

    @classmethod
    def _delete(
        cls,
        container_path: Path,
        container_id: str,
        doomed: Callable[[Optional[str]], bool],
    ) -> List[Dict[str, Any]]:
        deleted: List[Dict[str, Any]] = []
        job: Dict[str, Any]
        for job in ContainerJobs.of(container_path, container_id, None):
            if not doomed(job["status"]):
                continue

            JobStore.delete(JobStore.dataset_of(container_path, job["id"]), job["id"])
            deleted.append(job)

        return deleted
