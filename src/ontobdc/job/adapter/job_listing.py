from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from brasidatacenter.resources import iter_ontology_files
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF

from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.shared.domain.vocabulary import JOB, OBDC


class ContainerJobs:
    """
    Lists the jobs a container holds, by whether they have finished.

    A job points to its run, and the run to its status. The jobs are read from what the Turtle data
    sources of the container's datasets say. A job is active when the status of its run is one the job
    ontology puts in ``job:ActiveStatus``, and finished when it is in ``job:FinishedStatus``. A job that
    has no run, or whose run has no status, is in neither: nothing says whether it finished, and it is
    listed only when every job is.
    """

    ACTIVE: str = "active"
    FINISHED: str = "finished"
    ALL: str = "all"

    ONTOLOGY_FILE: str = "job.ttl"
    ONTOLOGY_IRI: URIRef = URIRef("http://datacenter.app.br/ontology/tool/ontobdc/core/job.ttl")

    @classmethod
    def status_of(cls, kind: str) -> Optional[Set[URIRef]]:
        """
        The status the job ontology that BrasidataCenter publishes lists for the kind of job: the active
        ones, or the finished ones. None for every job, which is not limited to a status.

        Raises:
            ValueError: the kind is not one of the three, the ontology is not part of BrasidataCenter, or
                it lists no status for the kind.
        """
        if kind == cls.ALL:
            return None
        lists: Dict[str, URIRef] = {cls.ACTIVE: JOB.ActiveStatus, cls.FINISHED: JOB.FinishedStatus}
        if kind not in lists:
            raise ValueError(f"A kind of job is active, finished or all, not {kind}.")

        for ontology_file in iter_ontology_files():
            if ontology_file.name != cls.ONTOLOGY_FILE:
                continue

            ontology: Graph = Graph()
            ontology.parse(data=ontology_file.read_text(encoding="utf-8"), format="turtle")
            if (cls.ONTOLOGY_IRI, RDF.type, OWL.Ontology) not in ontology:
                continue

            listed: Set[URIRef] = {
                status
                for status in ontology.objects(lists[kind], JOB.includesStatus)
                if isinstance(status, URIRef)
            }
            if not listed:
                raise ValueError(f"The job ontology lists no {kind} status.")

            return listed

        raise ValueError("The job ontology is not part of BrasidataCenter.")

    @classmethod
    def of(cls, container_path: Path, container_id: str, status: Optional[Set[URIRef]]) -> List[Dict[str, Any]]:
        """
        The jobs of the container whose status is among the ones given, or every job when none is given.
        """
        return cls.in_graph(ContainerEntities.triples(container_path), container_id, status)

    @classmethod
    def in_graph(cls, graph: Graph, container_id: str, status: Optional[Set[URIRef]]) -> List[Dict[str, Any]]:
        """
        The jobs the graph describes whose status is among the ones given (every job when none is given),
        each with the container it was found in, ordered by identifier.
        """
        jobs: List[Dict[str, Any]] = []
        job: Any
        for job in sorted(set(graph.subjects(RDF.type, OBDC.Job)), key=str):
            run: Any = graph.value(job, JOB.run)
            current: Any = graph.value(run, JOB.status) if run is not None else None
            if status is not None and current not in status:
                continue

            summary: Any = graph.value(run, JOB.errorSummary) if run is not None else None
            jobs.append(
                {
                    "id": cls._text(graph, job, DCTERMS.identifier) or str(job),
                    "container": container_id,
                    "title": cls._text(graph, job, DCTERMS.title),
                    "status": None if current is None else str(current).rsplit("#", 1)[-1],
                    "procedure": cls._text(graph, job, JOB.executesProcedure),
                    "creation_time": cls._text(graph, job, JOB.creationTime),
                    "start_time": cls._text(graph, job, JOB.startTime),
                    "end_time": cls._text(graph, job, JOB.endTime),
                    "error": None if summary is None else cls._text(graph, summary, JOB.message),
                }
            )

        return jobs

    @staticmethod
    def _text(graph: Graph, subject: Any, predicate: URIRef) -> Optional[str]:
        value: Any = graph.value(subject, predicate)
        return None if value is None else str(value)
