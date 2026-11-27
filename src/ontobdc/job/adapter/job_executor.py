import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.job.adapter.job_store import JobStore
from ontobdc.job.adapter.job_target import JobTarget
from ontobdc.shared.adapter.addon_package import AddonPackage
from ontobdc.shared.adapter.etl_state import EtlStateFile
from ontobdc.shared.domain.vocabulary import JOB, PKO


class JobExecutor:
    """
    Executes a job that was created, without making whoever asked wait.

    ``start`` hands the job to a worker process of its own, which outlives the command that started it.
    The worker runs ``run``: it marks the run as executing, runs what the procedure of the job targets
    through the command line of OntoBDC, and keeps in the job how it ended, in the run, never in the
    process that asked.
    """

    WORKER_MODULE: str = "ontobdc.job.adapter.job_worker"
    CLI_ENTRY: str = "import sys; from ontobdc.cli import main; sys.argv = ['ontobdc'] + sys.argv[1:]; main()"
    OUTPUT_ID: str = "output"
    MESSAGE_LIMIT: int = 200
    DETAIL_LIMIT: int = 10000
    ETL_MODULE_NAME: ClassVar[str] = "job"

    @classmethod
    def start(cls, container_path: Path, job_id: str) -> int:
        """
        Starts the worker of the job, apart from this process. Returns the id of the process.
        """
        worker: subprocess.Popen = subprocess.Popen(
            [sys.executable, "-m", cls.WORKER_MODULE, str(container_path), job_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=os.environ.copy(),
        )
        return worker.pid

    @staticmethod
    def _environment(target: JobTarget) -> Dict[str, str]:
        """The environment the process of the job starts with: the one of this process, and the addon of the target if it has one."""
        environment: Dict[str, str] = os.environ.copy()
        if target.addon is not None:
            environment[AddonPackage.ENVIRONMENT_KEY] = target.addon

        return environment

    @classmethod
    def run(cls, container_path: Path, job_id: str) -> None:
        """
        Runs the job to its end. What goes wrong with the target is the way the run ends (``job:Error``);
        a job that cannot even be read is an error of the caller.
        """
        container: Path = container_path.expanduser().resolve()
        dataset_path: Path = JobStore.dataset_of(container, job_id)
        graph: Graph = JobStore.read(dataset_path, job_id)
        job: URIRef = JobStore.job_node(job_id)
        procedure: Any = graph.value(job, JOB.executesProcedure)
        target_id: Any = graph.value(procedure, PKO.hasProcedureTarget) if procedure is not None else None
        procedure_iri: str = str(procedure)
        parameters: List[Tuple[str, str]] = cls._parameters(graph, job)

        JobStore.update(dataset_path, job_id, cls._start)
        if target_id is None:
            cls._fail(container, dataset_path, job_id, procedure_iri, "The procedure of the job has no target.", "")
            return

        arguments: List[str] = []
        try:
            target: JobTarget = JobTarget.locate(str(target_id))
            # A machine that works on the procedure leaves its ETL under the md5 of the IRI of the procedure: the job
            # tells it which one it is.
            arguments = target.arguments(
                str(container),
                [*parameters, ("procedure_iri", procedure_iri)] if target.kind == "fsm" else parameters,
            )
            cls._etl(
                container,
                procedure_iri,
                "executing",
                {
                    "job_id": job_id,
                    "target": target.id,
                    "kind": target.kind,
                    "arguments": arguments,
                    "parameters": dict(parameters),
                    "started_at": str(JobStore.now()),
                },
            )
            completed: subprocess.CompletedProcess = subprocess.run(
                [sys.executable, "-c", cls.CLI_ENTRY, *arguments, "--json"],
                capture_output=True,
                text=True,
                check=False,
                env=cls._environment(target),
            )
        except Exception as error:
            cls._fail(container, dataset_path, job_id, procedure_iri, str(error), repr(error))
            return

        failure: Optional[str] = cls._failure(completed)
        if failure is not None:
            cls._fail(
                container,
                dataset_path,
                job_id,
                procedure_iri,
                failure,
                (completed.stderr or completed.stdout).strip(),
                completed.returncode,
            )
            return

        cls._complete(container, dataset_path, job_id, procedure_iri, completed.stdout, completed.returncode)

    @classmethod
    def _etl(cls, container: Path, procedure_iri: str, state: str, result: Dict[str, Any]) -> None:
        """
        Leaves the ETL file of a state of the run of the job: ``etl/job/<md5 of the IRI of the procedure>/<state>.json``.
        """
        EtlStateFile.write_by_iri(container, cls.ETL_MODULE_NAME, procedure_iri, state, result)

    @staticmethod
    def _parameters(graph: Graph, job: URIRef) -> List[Tuple[str, str]]:
        return sorted(
            (str(graph.value(parameter, JOB.parameterId)), str(graph.value(parameter, JOB.parameterValue)))
            for parameter in graph.objects(job, JOB.hasParameter)
        )

    @staticmethod
    def _failure(completed: subprocess.CompletedProcess) -> Optional[str]:
        """
        Why the command did not succeed, or None when it did: an exit code that is not zero, an answer that
        is not JSON, or an answer whose content is an error.
        """
        if completed.returncode != 0:
            reported: Optional[str] = JobExecutor._reported(completed)
            if reported is None:
                return f"The command ended with the exit code {completed.returncode}."
            return f"{reported} (exit code {completed.returncode})"
        try:
            answer: Any = json.loads(completed.stdout)
        except ValueError:
            return "The command did not answer JSON."
        content: Any = answer.get("content") if isinstance(answer, dict) else None
        if isinstance(content, dict) and "error" in content:
            return str(content["error"])

        return None

    @staticmethod
    def _reported(completed: subprocess.CompletedProcess) -> Optional[str]:
        """
        What the command that failed says went wrong: the error of its JSON answer, else the last line it wrote on
        its error output; None when it said nothing of the sort.
        """
        try:
            answer: Any = json.loads(completed.stdout)
        except ValueError:
            answer = None
        content: Any = answer.get("content") if isinstance(answer, dict) else None
        if isinstance(content, dict) and content.get("error"):
            return str(content["error"])

        lines: List[str] = [line.strip() for line in (completed.stderr or "").splitlines() if line.strip()]
        return lines[-1] if lines else None

    @classmethod
    def _start(cls, graph: Graph, job: URIRef, run: URIRef) -> None:
        graph.set((run, JOB.status, JOB.Executing))
        graph.set((job, JOB.startTime, JobStore.now()))

    @classmethod
    def _fail(
        cls,
        container: Path,
        dataset_path: Path,
        job_id: str,
        procedure_iri: str,
        message: str,
        detail: str,
        exit_code: Optional[int] = None,
    ) -> None:
        def change(graph: Graph, job: URIRef, run: URIRef) -> None:
            summary: URIRef = URIRef(f"urn:ontobdc:job:{job_id}:error")
            graph.set((run, JOB.status, JOB.Error))
            graph.set((job, JOB.endTime, JobStore.now()))
            graph.add((summary, JOB.message, Literal(message[: cls.MESSAGE_LIMIT])))
            graph.add((summary, JOB.errorType, JOB.Fatal))
            graph.add((summary, JOB.hasDetail, Literal(bool(detail), datatype=XSD.boolean)))
            graph.set((run, JOB.errorSummary, summary))
            if detail:
                graph.set((run, JOB.errorDetail, Literal(detail)))

        JobStore.update(dataset_path, job_id, change)
        cls._etl(
            container,
            procedure_iri,
            "error",
            {
                "job_id": job_id,
                "message": message,
                "detail": detail[: cls.DETAIL_LIMIT],
                "exit_code": exit_code,
                "ended_at": str(JobStore.now()),
            },
        )

    @classmethod
    def _complete(
        cls,
        container: Path,
        dataset_path: Path,
        job_id: str,
        procedure_iri: str,
        output: str,
        exit_code: int,
    ) -> None:
        output_file: Path = (
            dataset_path / JobStore.PAYLOAD_DIRECTORY / JobStore.DOCUMENT_DIRECTORY / f"{job_id}_{cls.OUTPUT_ID}.json"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output, encoding="utf-8")
        reference: URIRef = URIRef(f"urn:ontobdc:job:{job_id}:result:{cls.OUTPUT_ID}")
        href: str = str(ContainerDocumentIri.of(container, output_file))

        def change(graph: Graph, job: URIRef, run: URIRef) -> None:
            graph.set((run, JOB.status, JOB.Completed))
            graph.set((job, JOB.endTime, JobStore.now()))
            graph.add((job, JOB.hasResult, reference))
            graph.add((reference, JOB.resultId, Literal(cls.OUTPUT_ID)))
            graph.add((reference, JOB.href, Literal(href, datatype=XSD.anyURI)))

        JobStore.update(dataset_path, job_id, change)
        cls._etl(
            container,
            procedure_iri,
            "completed",
            {
                "job_id": job_id,
                "exit_code": exit_code,
                "output": href,
                "ended_at": str(JobStore.now()),
            },
        )
