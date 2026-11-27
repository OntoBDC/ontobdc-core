import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Tuple
from urllib.parse import quote, urlparse

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.job.adapter.procedure_graph import ProcedureGraph
from ontobdc.shared.domain.vocabulary import JOB, OBDC, PKO


class JobStore:
    """
    Keeps the jobs of a container in the dataset that holds them: one Turtle file for each job, in the
    ``payload/triple`` of the dataset. The file holds the job, its run, its parameters and the procedure
    it executes, as it was when the job was created, so the job does not depend on the graph it came from.

    Every time is saved in UTC.
    """

    ENTITY_IRI: str = str(OBDC.Job)
    PAYLOAD_DIRECTORY: str = "payload"
    TRIPLE_DIRECTORY: str = "triple"
    DOCUMENT_DIRECTORY: str = "document"

    @staticmethod
    def job_node(job_id: str) -> URIRef:
        return URIRef(f"urn:uuid:{job_id}")

    @staticmethod
    def run_node(job_id: str) -> URIRef:
        return URIRef(f"urn:ontobdc:job:{job_id}:run")

    @staticmethod
    def now() -> Literal:
        """
        The moment, in UTC, as a date and time.
        """
        moment: str = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return Literal(moment, datatype=XSD.dateTime)

    @staticmethod
    def source_iri(graph_url: str) -> str:
        """
        The address of the graph as an absolute IRI: a path on this machine becomes the ``file`` URI of its
        absolute form, so that reading the job back, which resolves a relative IRI against the file of the
        job, opens the graph the job was created from. An address that already names a scheme, as an HTTP(S)
        address does, is kept as it is.
        """
        if urlparse(graph_url).scheme:
            return graph_url

        return Path(graph_url).expanduser().resolve().as_uri()

    @classmethod
    def create(
        cls,
        dataset_path: Path,
        graph_url: str,
        graph: Graph,
        procedure: URIRef,
        parameters: List[Tuple[str, str]],
    ) -> str:
        """
        Writes a job that executes the procedure, with its run waiting to start (``job:Pending``). Returns
        the id of the job.
        """
        job_id: str = str(uuid.uuid4())
        job: URIRef = cls.job_node(job_id)
        run: URIRef = cls.run_node(job_id)

        record: Graph = Graph()
        record.bind("obdc", OBDC)
        record.bind("job", JOB)
        record.bind("pko", PKO)
        record.bind("dcterms", DCTERMS)
        record.add((job, RDF.type, OBDC.Job))
        record.add((job, DCTERMS.identifier, Literal(job_id)))
        title = ProcedureGraph.label(graph, procedure)
        if title is not None:
            record.add((job, DCTERMS.title, Literal(title)))
        record.add((job, DCTERMS.source, URIRef(cls.source_iri(graph_url))))
        record.add((job, JOB.executesProcedure, procedure))
        record.add((job, JOB.creationTime, cls.now()))
        record.add((job, JOB.run, run))
        record.add((run, RDF.type, JOB.ProcedureRun))
        record.add((run, JOB.status, JOB.Pending))

        name: str
        value: str
        for name, value in parameters:
            parameter: URIRef = URIRef(f"urn:ontobdc:job:{job_id}:parameter:{quote(name, safe='')}")
            record.add((job, JOB.hasParameter, parameter))
            record.add((parameter, RDF.type, JOB.Parameter))
            record.add((parameter, JOB.parameterId, Literal(name)))
            record.add((parameter, JOB.parameterValue, Literal(value)))

        for triple in ProcedureGraph.snapshot(graph, procedure):
            record.add(triple)

        cls.write(dataset_path, job_id, record)
        return job_id

    @classmethod
    def path(cls, dataset_path: Path, job_id: str) -> Path:
        return dataset_path / cls.PAYLOAD_DIRECTORY / cls.TRIPLE_DIRECTORY / f"{job_id}.ttl"

    @classmethod
    def dataset_of(cls, container_path: Path, job_id: str) -> Path:
        """
        The dataset of the container that keeps the job.

        Raises:
            LookupError: no dataset of the container keeps it.
        """
        dataset_path: Path
        for dataset_path in EntityDatasets.of(container_path, cls.ENTITY_IRI):
            if cls.path(dataset_path, job_id).is_file():
                return dataset_path

        raise LookupError(f"No dataset of the container {container_path} keeps the job {job_id}.")

    @classmethod
    def delete(cls, dataset_path: Path, job_id: str) -> None:
        """
        Removes the job: what the run left for it in the documents of the dataset first, and its file last, so a job
        whose removal is interrupted is still a job that is listed.

        Raises:
            FileNotFoundError: the dataset does not keep the job.
        """
        path: Path = cls.path(dataset_path, job_id)
        if not path.is_file():
            raise FileNotFoundError(f"The dataset {dataset_path} does not keep the job {job_id}.")

        document: Path
        for document in sorted((dataset_path / cls.PAYLOAD_DIRECTORY / cls.DOCUMENT_DIRECTORY).glob(f"{job_id}_*.json")):
            document.unlink()
        path.unlink()

    @classmethod
    def read(cls, dataset_path: Path, job_id: str) -> Graph:
        graph: Graph = Graph()
        graph.parse(str(cls.path(dataset_path, job_id)), format="turtle")
        return graph

    @classmethod
    def write(cls, dataset_path: Path, job_id: str, graph: Graph) -> None:
        """
        Saves the job whole, or not at all: whoever reads it sees the file as it was, or as it is.
        """
        path: Path = cls.path(dataset_path, job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path = path.with_name(f"{path.name}.tmp")
        temporary.write_text(graph.serialize(format="turtle"), encoding="utf-8")
        os.replace(temporary, path)

    @classmethod
    def update(
        cls,
        dataset_path: Path,
        job_id: str,
        change: Callable[[Graph, URIRef, URIRef], None],
    ) -> None:
        """
        Changes the job: ``change`` gets its graph, its node and the node of its run.
        """
        graph: Graph = cls.read(dataset_path, job_id)
        change(graph, cls.job_node(job_id), cls.run_node(job_id))
        cls.write(dataset_path, job_id, graph)
