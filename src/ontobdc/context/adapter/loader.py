
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
from frictionless import Package
from frictionless.system import system
from typing import Dict, Any, Optional
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.context.domain.port.remote import RemoteResourceLoaderPort
from ontobdc.storage.domain.port.dataset import RemoteDatasetRepositoryPort

SCHEMA = get_ontology_by_prefix("schema")
PROV = get_ontology_by_prefix("prov")
CT = get_ontology_by_prefix("ct")

system.trusted = True


class RemoteResourceLoader:
    @classmethod
    def make(cls, schema_resource: Dict[str, Any]) -> RemoteResourceLoaderPort:
        format_type: str = schema_resource.get("format", "").lower()
        if format_type in ("csv", "text/csv"):
            raise NotImplementedError("CSV format is not supported yet.")
            # return CsvRemoteResourceLoader(schema_resource)

        elif format_type in ("ttl", "text/turtle"):
            return TtlRemoteResourceLoader(schema_resource)

        raise NotImplementedError(f"Unsupported resource format: {format_type}")


# class CsvRemoteResourceLoader(RemoteResourceLoaderPort):
#     def __init__(self, schema_resource: Dict[str, Any]):
#         self._schema_resource: Dict[str, Any] = schema_resource
#         self._fields: List[Dict[str, Any]] = self._schema_resource.get("schema", {}).get("fields", [])

#     def get_entity_instances(self, repo: RemoteDatasetRepositoryPort, entity_class: URIRef) -> Dict[str, Dict[str, Any]]:
#         datapackage_url: str = repo.linkset_datapackage.url
#         resource_name: Optional[str] = self._schema_resource.get("name")
#         if not resource_name:
#             raise ValueError("Schema resource does not specify a name")

#         from frictionless.system import system
#         system.trusted = True

#         # Load package from URL and extract resource using frictionless
#         package = Package(datapackage_url)
#         resource = package.get_resource(resource_name)
        
#         data: Dict[str, Dict[str, Any]] = {}
#         for row_idx, row in enumerate(resource.read_rows()):
#             row_dict = dict(row)
#             identifier_value: Optional[str] = None
            
#             entity_fields: List[Dict[str, Any]] = []
            
#             for field in self._fields:
#                 csv_col = field.get("name")
#                 value = row_dict.get(csv_col)
                
#                 if value is not None and str(value).strip():
#                     rdf_type = field.get("rdfType")
                    
#                     # Create a copy of the field definition and add the value
#                     field_with_value = field.copy()
#                     field_with_value["value"] = str(value).strip()
#                     entity_fields.append(field_with_value)
                    
#                     # Capture identifier for key
#                     if rdf_type and rdf_type.endswith("/identifier"):
#                         identifier_value = str(value).strip()
            
#             # Determine the primary key
#             key: str
#             if identifier_value:
#                 key = identifier_value
#             else:
#                 key = str(row_idx)
                
#             data[key] = {"fields": entity_fields}
                
#         return data


class TtlRemoteResourceLoader(RemoteResourceLoaderPort):
    def __init__(self, schema_resource: Dict[str, Any]):
        self._schema_resource: Dict[str, Any] = schema_resource
        self._data_package_cache: Dict[str, Dict[str, Any]] = {}
        self._derived_from_resource_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get_entity_instances(self, repo: RemoteDatasetRepositoryPort, entity_class: URIRef) -> Dict[str, Dict[str, Any]]:
        """
        Load and process entity instances from a TTL resource.

        Args:
            repo (RemoteDatasetRepositoryPort): The repository port to access the TTL resource.
            entity_class (URIRef): The RDF class URI to filter instances.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary mapping entity URIs to their fields.
        """
        graph: Graph = self._load_ttl_resource(repo)
        data: Dict[str, Dict[str, Any]] = {}

        for subject in graph.subjects(RDF.type, entity_class):
            data[str(subject)] = self._process_entity_instance(repo, graph, subject)

        return data

    def _load_ttl_resource(self, repo: RemoteDatasetRepositoryPort) -> Graph:
        datapackage_url: str = repo.linkset_datapackage.url

        resource_name: Optional[str] = self._schema_resource.get("name")
        if not resource_name:
            raise ValueError("Schema resource does not specify a name")

        # Load package from URL and extract resource using frictionless
        package = Package(datapackage_url)
        resource = package.get_resource(resource_name)

        graph: Graph = Graph()

        # Parse the remote resource using rdflib's Graph
        graph.parse(resource.normpath, format="turtle")

        return graph

    def _process_entity_instance(self, repo: RemoteDatasetRepositoryPort, graph: Graph, subject: URIRef) -> Dict[str, Any]:
        data = {
            "uri": str(subject),
            "identifier": graph.value(subject, SCHEMA.identifier).value,
            "fields": {}
        }

        for derived_from_uri in graph.objects(subject, PROV.wasDerivedFrom):
            if not str(derived_from_uri) in self._derived_from_resource_cache.keys():
                self._derived_from_resource_cache[str(derived_from_uri)] = self._process_data_source(repo, derived_from_uri)
                self._derived_from_resource_cache[str(derived_from_uri)]["values"] = {}
                primary_key: str = self._derived_from_resource_cache[str(derived_from_uri)]["primary_key"]
                for row in self._derived_from_resource_cache[str(derived_from_uri)]["content"].read_rows():
                    self._derived_from_resource_cache[str(derived_from_uri)]["values"][row[primary_key]] = dict(row)

        for data_source in self._derived_from_resource_cache.values():
            data["fields"] = {**data_source["fields"], **data["fields"]}
            item: Dict[str, Any] = data_source["values"][subject.fragment]
            for field_key in data_source["fields"].keys():
                data["fields"][field_key] = data["fields"][field_key].copy()
                data["fields"][field_key]["value"] = item[field_key]

        return data

    def _is_part_of_facade(self, repo: RemoteDatasetRepositoryPort, uri: URIRef) -> bool:
        return (uri, None, None) in repo.facade.graph

    def _get_data_package_resource(self, repo: RemoteDatasetRepositoryPort, resource_name: str):
        if resource_name not in self._data_package_cache:
            self._data_package_cache[resource_name] = repo.linkset_datapackage.get_resource_by_name(resource_name)

        return self._data_package_cache[resource_name]

    def _process_data_source(self, repo: RemoteDatasetRepositoryPort, uri: URIRef) -> Dict[str, Any]:
        data = {
            "uri": str(uri),
            "name": None,
            "fields": {},
        }

        if self._is_part_of_facade(repo, uri):
            data["name"] = repo.facade.graph.value(uri, CT.name, None).value

            if not (uri, RDF.type, CT.InternalDocument) in repo.facade.graph:
                raise ValueError(f"URI {uri} is not defined as an internal document in the facade.")
        else:
            raise NotImplementedError(f"Non-facade resources are not supported yet in {self.__class__.__name__}.")

        data_resource: Dict[str, Any] = self._get_data_package_resource(repo, data["name"])
        data["content"] = data_resource.get("content", None)

        data["primary_key"] = data_resource.get("schema", {}).get("primaryKey", None)
        if not data["primary_key"]:
            raise ValueError(f"URI {uri} does not define a primary key in the schema.")

        for field in data_resource.get("schema", {}).get("fields", []):
            if field.get("name") and field["name"] not in data["fields"]:
                data["fields"][field["name"]] = field

        return data

        # raise NotImplementedError(data)

            #         if derived_from["name"] not in derived_from_cache:
            #             derived_from_cache[derived_from["name"]] = repo.linkset_datapackage.get_resource_by_name(derived_from["name"])
            #         if derived_from["name"] not in resource_data_cache:
            #             inner_resource = package.get_resource(derived_from["name"])
            #             resource_dict = {}
            #             for row in inner_resource.read_rows():
            #                 # derived_from["debug"] = dict(row)
            #                 derived_from["debug"] = len(row)
            #                     #         row_dict = dict(row)
            #                     #         if "Code" in row_dict:
            #                     #             resource_dict[row_dict["Code"]] = row_dict
            #             resource_data_cache[derived_from["name"]] = resource_dict

            #         if 'schema' in derived_from_cache[derived_from["name"]]:
            #             derived_from["path"] = derived_from_cache[derived_from["name"]].get("path", None)
            #             if derived_from["path"]:
            #                 derived_from_schema = derived_from_cache[derived_from["name"]].get("schema", {})
            #                 if 'fields' in derived_from_schema:
            #                     pass
            #                     # for field in derived_from_schema["fields"]:
            #                     #     if not field["name"] in data[str(subject)].get("fields", {}):
            #                     #         data[str(subject)]["fields"][field["name"]] = field
            #                     #         derived_from["fields"].append(field["name"])
            #                     #         derived_from["debug2"] = data[str(subject)]["identifier"]
            #                     #         data[str(subject)]["fields"][field["name"]]["value"] = resource_data_cache[derived_from["name"]][data[str(subject)]["identifier"]].get(field["name"], None)

            #     if derived_from["path"]:
            #         data[str(subject)]["derivedFrom"].append(derived_from)
