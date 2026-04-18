
import os
import sys
from typing import Dict, Any, List
from ontobdc.cli import get_config_dir
from ontobdc.storage.adapter.icdd import ICDDIndexAdapter
from rdflib import PROV, Graph, RDF, DCTERMS
from ontobdc.storage.adapter.storage import StorageIndexAdapter
from ontobdc.core.domain.resource.param import InputParamChecker


class InputParams(InputParamChecker):
    def __init__(self, args: List[str]):
        self._args: Dict[str, Dict[str, Any]] = self._parse_args(args)
        self._expected_params: List[Dict[str, Any]] = []

    def _get_params(self) -> Dict[str, Any]:
        """
        Get the input parameters.
        """
        params: Dict[str, Any] = {}

        for arg_id, arg_value in self._args.items():
            params[arg_id] = arg_value

        return params

    def _get_expected_params(self) -> List[Dict[str, Any]]:
        """
        Get the expected input parameters.
        """
        return self._expected_params

    @property
    def config_dir(self) -> str:
        """
        Get the configuration directory.
        """
        return get_config_dir()


def main() -> List[Dict[str, Any]]:
    # Remove the --json argument from sys.argv so it doesn't break InputParams parser
    args = [arg for arg in sys.argv[1:] if arg != "--json"]
    params = InputParams(args)

    try:
        params.check()
    except Exception as e:
        print(e)
        # print(params._get_params()) # removed to avoid double crash
        return []

    storage_rdf = os.path.join(params.config_dir, StorageIndexAdapter.INDEX_FILE)

    g = Graph()
    try:
        g.parse(storage_rdf, format="xml")

        ct = ICDDIndexAdapter.CT
        items: Dict[str, Dict[str, Any]] = {}
        containers = list(g.subjects(RDF.type, ct.ContainerDescription))
        for container in containers:
            container_data: Dict[str, Any] = {'@id': str(container), 'dataset': []}
            titles = list(g.objects(container, DCTERMS.title))
            container_data["title"] = str(titles[0])

            locations = list(g.objects(container, PROV.atLocation))
            if locations:
                container_data["location"] = str(locations[0])

            items[str(container)] = container_data

        for dataset in set(g.subjects(predicate=PROV.atLocation)):
            container_refs = list(g.objects(dataset, DCTERMS.isPartOf))
            if not container_refs:
                continue

            container_ref: str = str(container_refs[0])
            dataset_data: Dict[str, Any] = {'@id': str(dataset).split(f"{container_ref}/")[-1]}

            titles = list(g.objects(dataset, DCTERMS.title))
            dataset_data["title"] = str(titles[0])

            locations = list(g.objects(dataset, PROV.atLocation))
            if locations:
                dataset_data["location"] = f"{items[str(container_ref)]["location"]}/{str(locations[0])}"

            if str(container_ref) in items.keys():
                items[str(container_ref)]["dataset"].append(dataset_data)

    except Exception as e:
        print(e)
        return []

    return list(items.values())

if __name__ == "__main__":
    import json
    print(json.dumps(main()))

    