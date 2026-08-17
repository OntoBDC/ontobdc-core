
from __future__ import annotations

from pathlib import Path
from rdflib import Literal
from rdflib.graph import Graph
from rdflib.namespace import Namespace
from typing import Any, Dict, List, Optional, Tuple

from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.domain.port.ontology import OntologyConfigPort

_SUPPORTED_EXTENSIONS: Tuple[str, ...] = (
    ".ttl",
    ".rdf",
    ".jsonld",
    ".json-ld",
    ".owl",
    ".xml",
    ".nt",
    ".n3",
)

_PREFIX_TO_RESOURCE_PARTS: Dict[str, Tuple[str, ...]] = {
    "obdc": ("ontobdc", "domain"),
    "obdc_code": ("ontobdc", "domain"),
    "obdc_test": ("ontobdc", "domain"),
    "obdc_view": ("ontobdc", "domain"),
    "obdc_abox_surface_layouts": ("ontobdc", "abox"),
    "pe_entity": ("productivity", "entity"),
    "pe_entity_document": ("productivity", "entity", "document"),
    "pe_entity_work_stream": ("productivity", "entity", "work_stream"),
    "pe_entity_enrichment_annotation": ("productivity", "entity", "enrichment_annotation"),
    "pe_entity_visual_representation_type": (
        "productivity",
        "entity",
        "visual_representation_type",
    ),
    "social_ns": ("social", "entity"),
    "social_entity_contact_point": ("social", "entity", "contact_point"),
    "social_entity_person": ("social", "entity", "person"),
    "social_entity_weblink": ("social", "entity", "weblink"),
    "social_entity_document": ("social", "entity", "document"),
    "bsi_element_ifc_work_schedule": ("bsi", "element", "ifc_work_schedule"),
    "sales_entity_sales_funnel": ("sales", "entity", "sales_funnel"),
    "sales_entity_sales_opportunity": ("sales", "entity", "sales_opportunity"),
}

_INFOBIM_PREFIX_TO_RESOURCE_SUBPATH: Dict[str, Tuple[str, ...]] = {
    "ibim": ("ns",),
    "ibim_view": ("view",),
}


def _resource_path_from_package(
    package_name: str,
    path_parts: Tuple[str, ...],
    type_name: str,
) -> Optional[Path]:
    """Generic package-resources resolver.

    Uses ``importlib.resources.files(package_name)`` to resolve a file inside a
    Python package. Works both for editable installs of the package (repo
    source tree) and for installed wheels in production.
    """
    try:
        from importlib.resources import files  # noqa: WPS433 — inside helper
    except Exception:
        return None
    try:
        package_root = files(package_name)
    except Exception:
        return None
    candidate = package_root.joinpath(*path_parts, f"{type_name}.ttl")
    if not candidate.is_file():
        return None
    return Path(str(candidate))


def _brasidatacenter_resource_path(prefix: str, type_name: str) -> Optional[Path]:
    """Resolve an ontology file through the BrasidataCenter package when it is
    installed as a pip dependency.

    Delegates directly to :func:`brasidatacenter.resources.ontology_path`
    because that helper already handles both install modes correctly:

    * **installed wheel** — the ontology tree lives under the package
      ``brasidatacenter/ontology`` (populated via hatch force-include).
    * **editable repo install** — it falls back to the repository-local
      ``ontology/`` directory next to the package source tree.

    Returns the filesystem path as a :class:`Path` if BrasidataCenter is
    importable, the prefix is in the official map, and the resolved file
    actually exists. Returns ``None`` otherwise so callers can fall through
    the remaining resolution tiers (InfoBIM package resolver, user config
    absolute paths, legacy workspace ontology cache).
    """
    try:
        from brasidatacenter.resources import ontology_path  # noqa: WPS433 — soft import
    except Exception:
        return None

    path_parts: Optional[Tuple[str, ...]] = _PREFIX_TO_RESOURCE_PARTS.get(prefix)
    if path_parts is None:
        return None
    candidate = ontology_path(*path_parts, f"{type_name}.ttl")
    if not candidate.is_file():
        return None
    return Path(str(candidate))


def _infobim_resource_path(prefix: str, type_name: str) -> Optional[Path]:
    """Tier 1.5 — resolve InfoBIM-specific ontologies directly from the
    installed ``infobim`` package tree.

    Some InfoBIM-only TBox files (``ibim`` core namespace and
    ``ibim_view``) are still packaged inside the InfoBIM distribution rather
    than mirrored into BrasidataCenter; the resolver therefore prefers the
    InfoBIM package directly instead of forcing a wrong location. When those
    TBox files are eventually upstreamed into BrasidataCenter their prefix
    entry should be moved from here to :data:`_PREFIX_TO_RESOURCE_PARTS` and
    the brasidatacenter tier will pick them up automatically.
    """
    subpath: Optional[Tuple[str, ...]] = _INFOBIM_PREFIX_TO_RESOURCE_SUBPATH.get(prefix)
    if subpath is None:
        return None
    expected_stem: str = subpath[-1]
    return _resource_path_from_package(
        "infobim",
        ("context", "ontology"),
        expected_stem,
    )


def _resolve_file_with_extensions(
    directory: Path,
    type_name: str,
) -> Optional[Path]:
    """Look for ``<type_name>.<extension>`` with a canonical ordered list of
    RDF file extensions, returning the first hit or ``None``."""
    for extension in _SUPPORTED_EXTENSIONS:
        candidate: Path = directory / f"{type_name}{extension}"
        if candidate.is_file():
            return candidate
    return None


class OntologyConfigAdapter(OntologyConfigPort):
    """
    Central adapter for all ontology access in OntoBDC.

    Resolution order for :meth:`get_ontology_path` is intentionally strict and
    mirrors rule #15 of the project (prefer central adapters over local
    workarounds, hardcoded absolute paths or parallel lookups):

    1. **BrasidataCenter packaged ontology tree** — preferred source whenever
       the BrasidataCenter Python distribution is importable, because that is
       the single canonical copy declared in ``brasidatacenter/ontology/`` and
       shipped inside every published BrasidataCenter wheel. This resolver
       works identically in editable installs (development repos) and in
       production wheels (no hardcoded paths, no monorepo assumptions).

       A small in-process prefix map (:data:`_PREFIX_TO_RESOURCE_PARTS`)
       translates short OntoBDC prefix strings (``obdc``, ``obdc_view``,
       ``obdc_abox_surface_layouts``, ``social_ns``, ``pe_entity``, …) to the
       correct path tuple inside ``brasidatacenter.ontology`` — for example
       ``obdc`` maps to ``("ontobdc","domain")`` then the caller's
       ``type="ns"`` becomes ``ontobdc/domain/ns.ttl``, mirroring the exact
       filesystem layout you see in the repository.

    1.5. **InfoBIM packaged ontology tree** — InfoBIM-specific prefixes that
         are still packaged inside the ``infobim`` distribution itself (and
         not yet upstreamed into BrasidataCenter) are resolved directly from
         the installed ``infobim`` package. This tier is explicitly temporary:
         as soon as those vocabularies are mirrored into BrasidataCenter
         their mapping moves to tier 1 and the brasidatacenter resolver
         picks them up automatically (see :data:`_INFOBIM_PREFIX_TO_RESOURCE_
         SUBPATH` for the 2 prefixes currently living here: ``ibim``,
         ``ibim_view``).

    2. **User/project ConfigDataAdapter absolute paths** — explicit
       ``directory.ontology.<prefix>.absolute_path`` or
       ``directory.ontology.<prefix>.<type>.absolute_path`` configuration
       entries. This branch exists so advanced deployments can override a
       specific ontology (hot-fix patch, private forked copy, custom TBox)
       *without* replacing the BrasidataCenter package. Tries both the
       configured path as a file itself and ``<config-dir>/<type><ext>`` when
       the configured path points to a directory.

    3. **Workspace ontology cache** — legacy fallback. When the other two
       layers cannot find a file the adapter keeps the old behavior of
       searching ``ConfigDataPort.ontology_cache`` for ``<prefix>`` and
       ``<prefix>.<ext>``, so old environments that still drop ontology files
       directly in the workspace cache keep working without changes.

    If none of the three layers succeeds, :exc:`FileNotFoundError` is raised
    with a descriptive error listing the prefix, the requested type, and the
    three candidate roots that were actually probed — making debugging of
    missing or miss-spelled prefixes substantially easier than the old single
    ``not found in <dir>`` message.

    :meth:`get_ontology_namespace_by_prefix` remains a lightweight in-memory
    lookup; every stable W3C / ISO / industry prefix map is cached here so
    callers never have to touch the filesystem just to build a
    :class:`rdflib.namespace.Namespace`. New project prefixes MUST be added
    to this dictionary before they are used anywhere in the codebase to keep
    prefix→IRI binding consistent between import-time module constants and
    runtime callers.
    """

    def __init__(self, config_adapter: ConfigDataPort) -> None:
        self._config_adapter: ConfigDataPort = config_adapter

    def get_ontology_namespace_by_prefix(self, prefix: str) -> Optional[Namespace]:
        """
        Return the in-memory cached :class:`Namespace` for a stable prefix.

        Never touches the filesystem; never raises (returns ``None`` for
        unknown prefixes, matching :class:`OntologyConfigPort` contract).
        """
        ontology_list: Dict[str, Namespace] = {
            "cv": Namespace("http://rdfs.org/resume-rdf/cv.rdfs#"),
            "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
            "peo": Namespace("http://w3id.org/peo#"),
            "sh": Namespace("http://www.w3.org/ns/shacl#"),
            "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
            "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
            "obdc": Namespace("http://ontobdc.org/ontology/domain/ns.ttl#"),
            "obdc_code": Namespace("http://ontobdc.org/ontology/domain/code.ttl#"),
            "obdc_test": Namespace("http://ontobdc.org/ontology/domain/test.ttl#"),
            "obdc_view": Namespace("http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#"),
            "obdc_tile": Namespace("http://datacenter.app.br/ontology/ontobdc/domain/tile.ttl#"),
            "obdc_file": Namespace("http://datacenter.app.br/ontology/ontobdc/domain/file.ttl#"),
            "obdc_abox_surface_layouts": Namespace(
                "http://datacenter.app.br/ontology/ontobdc/abox/default_surface_layouts.ttl#"
            ),
            "ibim": Namespace("https://infobim.org/ontology/ns#"),
            "ibim_view": Namespace("http://datacenter.app.br/ontology/infobim/domain/view.ttl#"),
            "ibim_presentation": Namespace(
                "http://datacenter.app.br/ontology/infobim/domain/presentation.ttl#"
            ),
            "ibim_tile": Namespace("http://datacenter.app.br/ontology/infobim/domain/tile.ttl#"),
            "olia": Namespace("http://purl.org/olia/olia.owl#"),
            "ct": Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#"),
            "fnct": Namespace("http://w3id.org/function/ontology#"),
            "dcat": Namespace("http://www.w3.org/ns/dcat#"),
            "void": Namespace("http://rdfs.org/ns/void#"),
            "schema": Namespace("https://schema.org/"),
            "prov": Namespace("http://www.w3.org/ns/prov#"),
            "ontouml": Namespace("https://w3id.org/ontouml#"),
            "sdo": Namespace("https://w3id.org/okn/o/sd#"),
            "owl": Namespace("http://www.w3.org/2002/07/owl#"),
            "dcterms": Namespace("http://purl.org/dc/terms/"),
            "social_ns": Namespace(
                "http://datacenter.app.br/ontology/social/entity/ns.ttl#"
            ),
            "pe_entity": Namespace(
                "http://datacenter.app.br/ontology/productivity/entity/ns.ttl#"
            ),
            "pe_entity_work_stream": Namespace(
                "http://datacenter.app.br/ontology/productivity/entity/work_stream/ns.ttl#"
            ),
            "bsi_element_ifc_work_schedule": Namespace(
                "http://datacenter.app.br/ontology/bsi/element/ifc_work_schedule/type.ttl#"
            ),
            "sales_entity_sales_funnel": Namespace(
                "http://datacenter.app.br/ontology/sales/entity/sales_funnel/type.ttl#"
            ),
            "sales_entity_sales_opportunity": Namespace(
                "http://datacenter.app.br/ontology/sales/entity/sales_opportunity/type.ttl#"
            ),
            "social_entity_person": Namespace(
                "http://datacenter.app.br/ontology/social/entity/person/type.ttl#"
            ),
            "social_entity_contact_point": Namespace(
                "http://datacenter.app.br/ontology/social/entity/contact_point/type.ttl#"
            ),
            "social_entity_weblink": Namespace(
                "http://datacenter.app.br/ontology/social/entity/weblink/type.ttl#"
            ),
            "social_entity_document": Namespace(
                "http://datacenter.app.br/ontology/social/entity/document/type.ttl#"
            ),
            "pe_entity_document": Namespace(
                "http://datacenter.app.br/ontology/productivity/entity/document/type.ttl#"
            ),
            "pe_entity_enrichment_annotation": Namespace(
                "http://datacenter.app.br/ontology/productivity/entity/enrichment_annotation/type.ttl#"
            ),
            "pe_entity_visual_representation_type": Namespace(
                "http://datacenter.app.br/ontology/productivity/entity/visual_representation_type/type.ttl#"
            ),
            "ifco": Namespace("https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/OWL#"),
        }
        return ontology_list.get(prefix, None)

    # ------------------------------------------------------------------ path

    def _probe_configured_absolute_path(
        self,
        prefix: str,
        type_name: str,
    ) -> Optional[Path]:
        """Look up the two supported absolute_path keys from config and return
        the first matching file, preserving the two-level search semantics the
        old adapter had."""
        ontology_config: Dict[str, Any] = (
            self._config_adapter.all.get("directory", {})
            .get("ontology", {})
            .get(prefix, {})
        )

        absolute_path: Optional[str] = ontology_config.get("absolute_path")
        if absolute_path:
            configured_path: Path = Path(absolute_path)
            if configured_path.is_file():
                return configured_path
            if configured_path.is_dir():
                found = _resolve_file_with_extensions(configured_path, type_name)
                if found is not None:
                    return found

        ontology_type_config: Dict[str, Any] = ontology_config.get(type_name, {})
        absolute_path = ontology_type_config.get("absolute_path")
        if absolute_path:
            configured_path = Path(absolute_path)
            if configured_path.is_file():
                return configured_path
            if configured_path.is_dir():
                found = _resolve_file_with_extensions(configured_path, type_name)
                if found is not None:
                    return found
        return None

    def _probe_ontology_cache(
        self,
        prefix: str,
        type_name: str,
    ) -> Optional[Path]:
        """Legacy workspace-cache fallback kept for backwards compatibility."""
        ontology_root: Path = self._config_adapter.ontology_cache
        candidate: Path = ontology_root / prefix
        if candidate.is_file():
            return candidate

        base_dir: Path = candidate.parent
        base_name: str = candidate.name
        for extension in _SUPPORTED_EXTENSIONS:
            ontology_file: Path = base_dir / f"{base_name}{extension}"
            if ontology_file.is_file():
                return ontology_file

        if ontology_root.is_dir():
            found = _resolve_file_with_extensions(ontology_root, type_name)
            if found is not None:
                return found
        return None

    def get_ontology_path(self, prefix: str, type: str = "ns") -> str:
        """
        Resolve an ontology file following the three-tier lookup strategy.

        Parameters
        ----------
        prefix:
            Short ontology identifier (``obdc``, ``obdc_view``, ``ibim``, …).
        type:
            File stem inside the prefix's directory — defaults to ``"ns"``
            which matches the canonical naming convention used in the
            BrasidataCenter tree (``ontobdc/domain/ns.ttl``,
            ``infobim/domain/ns.ttl``, …). Callers that need a different
            domain file pass explicit types such as ``"view"``, ``"code"``,
            ``"file"`` or ``"default_surface_layouts"`` for ABoxes.
        """
        type_name: str = type

        hit = _brasidatacenter_resource_path(prefix, type_name)
        if hit is not None:
            return str(hit)

        ibim_hit = _infobim_resource_path(prefix, type_name)
        if ibim_hit is not None:
            return str(ibim_hit)

        configured = self._probe_configured_absolute_path(prefix, type_name)
        if configured is not None:
            return str(configured)

        cache_hit = self._probe_ontology_cache(prefix, type_name)
        if cache_hit is not None:
            return str(cache_hit)

        unmapped = _PREFIX_TO_RESOURCE_PARTS.get(
            prefix,
            None,
        )
        unmapped_ibim = _INFOBIM_PREFIX_TO_RESOURCE_SUBPATH.get(prefix, None)
        if unmapped is not None:
            mapper_msg = f"brasidatacenter parts={unmapped}"
        elif unmapped_ibim is not None:
            mapper_msg = f"infobim context/ontology/{unmapped_ibim[-1]}.ttl"
        else:
            mapper_msg = "(unmapped prefix — not in BrasidataCenter or InfoBIM package maps)"
        probed_roots: List[str] = [
            f"brasidatacenter.resources prefix={prefix} {mapper_msg} type={type_name}.ttl",
            "infobim.resources infobim/context/ontology via _INFOBIM_PREFIX_TO_RESOURCE_SUBPATH",
            (
                f"ConfigDataAdapter directory.ontology.{prefix}."
                + f"{{,{type_name}.}}absolute_path"
            ),
            f"ontology_cache={getattr(self._config_adapter, 'ontology_cache', 'N/A')}",
        ]
        raise FileNotFoundError(
            f"Ontology prefix={prefix!r} type={type_name!r} not found. "
            f"Probed resolution roots: {'; '.join(probed_roots)}"
        )

    # ----------------------------------------------------------------- graph

    def get_ontology_content(self, prefix: str, type: str = "ns") -> Graph:
        """
        Load and parse the ontology file into an :class:`rdflib.graph.Graph`.

        Currently all bundled files use Turtle (``.ttl``); format is fixed to
        ``"turtle"`` because :meth:`get_ontology_path` guarantees the returned
        file is one of the canonical RDF suffixes listed in
        :data:`_SUPPORTED_EXTENSIONS` and the project ship only Turtle
        ontologies today.
        """
        ontology_graph: Graph = Graph()
        ontology_graph.parse(self.get_ontology_path(prefix, type), format="turtle")
        return ontology_graph

    # ---------------------------------------------------------------- literal

    def as_literal(self, value: str) -> Optional[Literal]:
        """
        Safely convert a string to an :class:`rdflib.Literal`.

        Returns ``None`` for empty strings (matching the previous
        implementation) instead of creating an empty ``xsd:string`` literal,
        so callers that treat an optional absence identically to an empty
        value can keep their current ``if not literal:`` checks.
        """
        if value:
            return Literal(value)
        return None
