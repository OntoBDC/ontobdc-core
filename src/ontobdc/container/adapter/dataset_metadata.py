from pathlib import Path

from rdflib import Graph


class DatasetMetadataFile:
    """
    How the metadata of a dataset (``.__ontobdc__/dataset.ttl``) is written. The ontology of the file is
    the file itself: written as ``<>`` it is read as wherever the file is, so the dataset can be moved
    with its container and no absolute location is left in the file.
    """

    @staticmethod
    def serialize(graph: Graph, metadata_path: Path) -> bytes:
        return graph.serialize(format="turtle", encoding="utf-8").replace(
            f"<{metadata_path.resolve().as_uri()}>".encode("utf-8"),
            b"<>",
        )
