import sys
from pathlib import Path
from typing import List

from ontobdc.job.adapter.job_executor import JobExecutor


def main(arguments: List[str]) -> None:
    """
    The worker of a job: ``python -m ontobdc.job.adapter.job_worker <container path> <job id>``.
    """
    if len(arguments) != 2:
        raise SystemExit("usage: job_worker <container path> <job id>")

    JobExecutor.run(Path(arguments[0]), arguments[1])


if __name__ == "__main__":
    main(sys.argv[1:])
