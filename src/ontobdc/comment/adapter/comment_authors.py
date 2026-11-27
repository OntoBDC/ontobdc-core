from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.container.adapter.entity_listing import ContainerEntities


class CommentAuthors:
    """
    Who a comment says wrote it, as a reader is shown: the name of the entity the author points to.

    An author is the IRI of an entity (``urn:ontobdc:entity:<global id>``, or the global id itself when it is already an
    IRI), a name, or nothing. When the IRI is the one of an entity of the container, the name of the entity is what is
    shown; any other author is shown as it is.
    """

    ENTITY_IRI_PREFIX: ClassVar[str] = "urn:ontobdc:entity:"

    @classmethod
    def names(cls, container_path: Path) -> Dict[str, str]:
        """The name of every entity of the container, by global id."""
        names: Dict[str, str] = {}
        dataset: Dict[str, Any]
        for dataset in ContainerEntities.of(container_path):
            entity: Dict[str, Any]
            for entity in dataset["entities"]:
                names[str(entity["global_id"])] = str(entity["name"])

        return names

    @classmethod
    def resolved(cls, comments: List[Dict[str, Any]], names: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        The comments, each author that is an entity of the container given by its name, with the IRI it pointed to kept
        in ``author_iri``.
        """
        shown: List[Dict[str, Any]] = []
        comment: Dict[str, Any]
        for comment in comments:
            author: str = str(comment["author"])
            global_id: str = author[len(cls.ENTITY_IRI_PREFIX):] if author.startswith(cls.ENTITY_IRI_PREFIX) else author
            if global_id in names:
                shown.append({**comment, "author": names[global_id], "author_iri": author})
            else:
                shown.append(comment)

        return shown
