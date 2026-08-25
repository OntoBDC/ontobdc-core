from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import set_state_marker
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.surface_common import state_reached


_PRODUCT = {
    "ontobdc": {
        "page": "https://ontobdc.org/",
        "hidden_dir": ".__ontobdc__",
        "asset_dir": "asset",
        "brand": "OntoBDCBrand.svg",
        "logotype": "OntoBDCLogotype.svg",
    },
    "infobim": {
        "page": "https://infobim.org/",
        "hidden_dir": ".__infobim__",
        "asset_dir": "assets",
        "brand": "InfoBIMBrand.svg",
        "logotype": "InfoBIMLogotype.svg",
    },
}


class _SvgLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name not in {"src", "href"} or not value:
                continue
            if urlparse(value).path.lower().endswith(".svg"):
                self.links.append(value)


class SurfaceBrandedCapability(TransformationCapability):
    """Resolve Surface SVG branding with container/workspace/web precedence."""

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_branded",
        version="1.0.0",
        name="Surface Branded",
        description=(
            "Resolve Surface SVG branding from the container, then the workspace, "
            "falling back to the official product page."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "branding", "svg", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "Surface SVG branding resources were resolved.",
            },
            "debug_entry": {
                "en": (
                    "Resolving Surface SVG branding from container, workspace, "
                    "or official product page."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_BRANDED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_BRANDED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        try:
            document = self._surface.read(context)
        except (OSError, ValueError):
            return False
        return state_reached(document, SurfaceGenerationProcessState.SURFACE_BRANDED)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_root = self._container_root(context)
        workspace_root = Path(context.root_path).expanduser().resolve()
        product = self._product(container_root, workspace_root)
        spec = _PRODUCT[product]

        resolved: Dict[str, Dict[str, str]] = {}
        for role in ("brand", "logotype"):
            filename = str(spec[role])
            relative_path = Path(str(spec["hidden_dir"])) / str(spec["asset_dir"]) / filename
            path, source = self._resolve_svg(
                container_root=container_root,
                workspace_root=workspace_root,
                relative_path=relative_path,
                page_url=str(spec["page"]),
                filename=filename,
            )
            resolved[role] = {
                "path": str(path),
                "source": source,
            }

        document = set_state_marker(self._surface.read(context), "surface_branded")
        surface_path = self._surface.write(context, document)
        if not self.check(context):
            raise RuntimeError("Surface branding transformation did not reach surface_branded")

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_BRANDED,
            "surface_path": str(surface_path),
            "product": product,
            "branding": resolved,
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    @staticmethod
    def _container_root(context: CliContextPort) -> Path:
        if not context.has_parameter("container_path"):
            raise ValueError("container_path is required to resolve Surface branding")
        value = context.get_parameter_value("container_path")
        if not value:
            raise ValueError("container_path is required to resolve Surface branding")
        return Path(str(value)).expanduser().resolve()

    @staticmethod
    def _product(container_root: Path, workspace_root: Path) -> str:
        if (
            (container_root / ".__infobim__").exists()
            or (workspace_root / ".__infobim__").exists()
        ):
            return "infobim"
        return "ontobdc"

    @classmethod
    def _resolve_svg(
        cls,
        *,
        container_root: Path,
        workspace_root: Path,
        relative_path: Path,
        page_url: str,
        filename: str,
    ) -> Tuple[Path, str]:
        container_candidate = container_root / relative_path
        if container_candidate.is_file():
            cls._require_svg(container_candidate.read_bytes(), container_candidate)
            return container_candidate, "container"

        workspace_candidate = workspace_root / relative_path
        if workspace_candidate.is_file():
            cls._require_svg(workspace_candidate.read_bytes(), workspace_candidate)
            return workspace_candidate, "workspace"

        payload, source_url = cls._download_svg_from_page(page_url, filename)
        cls._require_svg(payload, source_url)
        container_candidate.parent.mkdir(parents=True, exist_ok=True)
        container_candidate.write_bytes(payload)
        return container_candidate, source_url

    @classmethod
    def _download_svg_from_page(cls, page_url: str, filename: str) -> Tuple[bytes, str]:
        page = cls._download(page_url).decode("utf-8", errors="replace")
        parser = _SvgLinkParser()
        parser.feed(page)

        links = cls._ordered_svg_links(parser.links, filename)
        for link in links:
            absolute_url = urljoin(page_url, link)
            try:
                payload = cls._download(absolute_url)
                cls._require_svg(payload, absolute_url)
            except (OSError, ValueError):
                continue
            return payload, absolute_url

        raise FileNotFoundError(
            f"SVG branding asset {filename!r} was not found in container, workspace, "
            f"or official page {page_url}"
        )

    @staticmethod
    def _ordered_svg_links(links: Iterable[str], filename: str) -> List[str]:
        unique = list(dict.fromkeys(links))
        expected = filename.lower()
        exact = [link for link in unique if Path(urlparse(link).path).name.lower() == expected]
        others = [link for link in unique if link not in exact]
        return exact + others

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "OntoBDC/SurfaceBranded"})
        with urlopen(request, timeout=15) as response:
            return response.read()

    @staticmethod
    def _require_svg(payload: bytes, source: object) -> None:
        text = payload.lstrip()[:512].lower()
        if b"<svg" not in text:
            raise ValueError(f"Branding asset is not SVG: {source}")
