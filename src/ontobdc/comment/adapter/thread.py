import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from ontobdc.container.adapter.entity_listing import ContainerEntities


class CommentThread:
    """
    The thread of comments of one entity, as the social ontology of
    Brasidatacenter models it: a ``sioc:Thread`` the entity has as its
    discussion, and the comments (``social:Comment``, a ``sioc:Post``) it
    contains, each of them maybe in reply to another.

    It is kept as Turtle in the dataset of the entity, in
    ``payload/triple/comment_<global id of the entity>.ttl``. A comment is not
    an entity, whatever the files of ``payload/triple`` say: only what the
    dataset declares as its data entities is one.
    """

    SOCIAL: ClassVar[Namespace] = Namespace(
        "http://datacenter.app.br/ontology/domain/social/taxonomy/type.ttl#"
    )
    SIOC: ClassVar[Namespace] = Namespace("http://rdfs.org/sioc/ns#")
    SCHEMA: ClassVar[Namespace] = Namespace("http://schema.org/")
    DIRECTORY: ClassVar[Path] = Path("payload") / "triple"
    PREFIX: ClassVar[str] = "comment_"
    SUFFIX: ClassVar[str] = ".ttl"
    FORMAT: ClassVar[str] = "turtle"

    def __init__(self, dataset_path: Path, entity_id: str) -> None:
        self._dataset_path: Path = dataset_path.expanduser().resolve()
        self._entity_id: str = entity_id

    @property
    def path(self) -> Path:
        return self._dataset_path / self.DIRECTORY / f"{self.PREFIX}{self._entity_id}{self.SUFFIX}"

    @property
    def entity(self) -> URIRef:
        return URIRef(f"urn:ontobdc:entity:{self._entity_id}")

    @property
    def thread(self) -> URIRef:
        return URIRef(f"urn:ontobdc:thread:{self._entity_id}")

    @staticmethod
    def comment_iri(comment_id: str) -> URIRef:
        return URIRef(f"urn:ontobdc:comment:{comment_id}")

    def comments(self) -> List[Dict[str, Any]]:
        """
        The comments of the thread, the oldest first.
        """
        graph: Graph = self._read()
        comments: List[Dict[str, Any]] = []
        subject: Any
        for subject in graph.subjects(RDF.type, self.SOCIAL.Comment):
            reply_of: Optional[Any] = next(graph.objects(subject, self.SIOC.reply_of), None)
            comments.append(
                {
                    "global_id": self._text(graph, subject, DCTERMS.identifier),
                    "text": self._text(graph, subject, self.SCHEMA.text),
                    "author": self._text(graph, subject, DCTERMS.creator),
                    "created_at": self._text(graph, subject, DCTERMS.created),
                    "reply_of": self._id_of(reply_of) if reply_of is not None else "",
                }
            )

        return sorted(comments, key=lambda comment: (comment["created_at"], comment["global_id"]))

    def add(self, text: str, author: str, reply_of: Optional[str] = None) -> Dict[str, Any]:
        """
        Put a comment at the end of the thread, opening the thread when it
        has none.

        Raises:
            LookupError: ``reply_of`` is not a comment of the thread.
        """
        graph: Graph = self._read()
        if reply_of is not None and (self.comment_iri(reply_of), RDF.type, self.SOCIAL.Comment) not in graph:
            raise LookupError(f"The thread has no comment {reply_of} to reply to.")

        self._bind(graph)
        graph.add((self.entity, self.SIOC.has_discussion, self.thread))
        graph.add((self.thread, RDF.type, self.SIOC.Thread))
        comment_id: str = str(uuid.uuid4())
        subject: URIRef = self.comment_iri(comment_id)
        created_at: str = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        graph.add((subject, RDF.type, self.SOCIAL.Comment))
        graph.add((subject, DCTERMS.identifier, Literal(comment_id)))
        graph.add((subject, self.SCHEMA.text, Literal(text)))
        if author:
            graph.add((subject, DCTERMS.creator, Literal(author)))
        graph.add((subject, DCTERMS.created, Literal(created_at, datatype=XSD.dateTime)))
        graph.add((subject, self.SIOC.has_container, self.thread))
        graph.add((self.thread, self.SIOC.container_of, subject))
        if reply_of is not None:
            graph.add((subject, self.SIOC.reply_of, self.comment_iri(reply_of)))
            graph.add((self.comment_iri(reply_of), self.SIOC.has_reply, subject))

        self._write(graph)
        return {
            "global_id": comment_id,
            "text": text,
            "author": author,
            "created_at": created_at,
            "reply_of": reply_of or "",
        }

    def delete(self, comment_id: str) -> List[str]:
        """
        Remove a comment, with the comments that reply to it, and to those.
        Returns the ids removed, the comment first.

        Raises:
            LookupError: the thread has no such comment.
        """
        graph: Graph = self._read()
        if (self.comment_iri(comment_id), RDF.type, self.SOCIAL.Comment) not in graph:
            raise LookupError(f"The thread has no comment {comment_id}.")

        removed: List[URIRef] = [self.comment_iri(comment_id)]
        seen: Set[URIRef] = set(removed)
        queue: List[URIRef] = list(removed)
        while queue:
            current: URIRef = queue.pop(0)
            replies: Any
            for replies in graph.subjects(self.SIOC.reply_of, current):
                if isinstance(replies, URIRef) and replies not in seen:
                    seen.add(replies)
                    removed.append(replies)
                    queue.append(replies)

        subject: URIRef
        for subject in removed:
            graph.remove((subject, None, None))
            graph.remove((None, None, subject))

        if next(graph.subjects(RDF.type, self.SOCIAL.Comment), None) is None:
            self.path.unlink(missing_ok=True)
        else:
            self._write(graph)

        return [self._id_of(subject) for subject in removed]

    def update(self, comment_id: str, text: Optional[str] = None, author: Optional[str] = None) -> Dict[str, Any]:
        """
        Change what a comment says (``text``) and who says it (``author``); what is not given stays as
        it was. The comment keeps its place in the thread and its moment of creation, and gets the
        moment it was changed.

        Raises:
            LookupError: the thread has no such comment.
            ValueError: nothing to change was given.
        """
        if text is None and author is None:
            raise ValueError("Give the text or the author to change.")

        graph: Graph = self._read()
        subject: URIRef = self.comment_iri(comment_id)
        if (subject, RDF.type, self.SOCIAL.Comment) not in graph:
            raise LookupError(f"The thread has no comment {comment_id}.")

        self._bind(graph)
        if text is not None:
            graph.set((subject, self.SCHEMA.text, Literal(text)))
        if author is not None:
            graph.remove((subject, DCTERMS.creator, None))
            if author:
                graph.add((subject, DCTERMS.creator, Literal(author)))
        modified_at: str = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        graph.set((subject, DCTERMS.modified, Literal(modified_at, datatype=XSD.dateTime)))

        self._write(graph)
        reply_of: Optional[Any] = next(graph.objects(subject, self.SIOC.reply_of), None)
        return {
            "global_id": comment_id,
            "text": self._text(graph, subject, self.SCHEMA.text),
            "author": self._text(graph, subject, DCTERMS.creator),
            "created_at": self._text(graph, subject, DCTERMS.created),
            "reply_of": self._id_of(reply_of) if reply_of is not None else "",
        }

    def holds(self, comment_id: str) -> bool:
        return (self.comment_iri(comment_id), RDF.type, self.SOCIAL.Comment) in self._read()

    @classmethod
    def holding(cls, container_path: Path, comment_id: str) -> Optional["CommentThread"]:
        """
        The thread, among those the datasets of the container keep, that has the comment.
        """
        dataset_path: Path
        for dataset_path in ContainerEntities.distinct_datasets(container_path):
            directory: Path = dataset_path / cls.DIRECTORY
            file: Path
            for file in sorted(directory.glob(f"{cls.PREFIX}*{cls.SUFFIX}")):
                thread: CommentThread = cls(dataset_path, file.stem[len(cls.PREFIX):])
                if thread.holds(comment_id):
                    return thread

        return None

    def _read(self) -> Graph:
        graph: Graph = Graph()
        if self.path.is_file():
            graph.parse(str(self.path), format=self.FORMAT)

        return graph

    def _write(self, graph: Graph) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(graph.serialize(format=self.FORMAT), encoding="utf-8")

    def _bind(self, graph: Graph) -> None:
        graph.bind("social", self.SOCIAL)
        graph.bind("sioc", self.SIOC)
        graph.bind("schema", self.SCHEMA)
        graph.bind("dcterms", DCTERMS)

    @staticmethod
    def _text(graph: Graph, subject: Any, predicate: Any) -> str:
        value: Optional[Any] = next(graph.objects(subject, predicate), None)
        return str(value) if value is not None else ""

    @staticmethod
    def _id_of(iri: Any) -> str:
        return str(iri).rsplit(":", 1)[-1]
