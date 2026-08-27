from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.adapter.draw import (
    DrawSourceStrategyLoader,
    VTracerSvgDrawAdapter,
)
from ontobdc.shared.domain.model.draw import DrawSource
from ontobdc.shared.domain.port.draw import (
    DrawSourceStrategyPort,
    SvgDrawPort,
)


class DrawLogoAsSvgCapability(TransactionCapability):
    """Draw a logo as SVG using a plugin that understands its source."""

    METADATA = CapabilityMetadata(
        id="org.ontobdc.shared.plugin.capability.draw.logo_as_svg",
        version="1.0.0",
        name="Draw Logo as SVG",
        description=(
            "Draw a logo as SVG after resolving its source format through "
            "a strategy plugin."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["shared", "draw", "logo", "svg"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "required": True,
                },
                "target_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "source_format": {"type": "string"},
                "source_strategy": {"type": "string"},
                "svg_path": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
        },
    )

    def __init__(
        self,
        strategy_loader: DrawSourceStrategyLoader | None = None,
        svg_drawer: SvgDrawPort | None = None,
    ) -> None:
        self._strategy_loader: DrawSourceStrategyLoader = (
            strategy_loader or DrawSourceStrategyLoader()
        )
        self._svg_drawer: SvgDrawPort = (
            svg_drawer or VTracerSvgDrawAdapter()
        )

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, str] = {
            "en": "Draw Logo as SVG",
            "pt-br": "Desenhar Logo como SVG",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, str] = {
            "en": "Draw a logo as an SVG document.",
            "pt-br": "Desenha um logo como documento SVG.",
        }
        return descriptions.get(lang, descriptions["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source_path: Path = self._source_path(context)
        target_path: Path = self._target_path(context, source_path)
        strategy: DrawSourceStrategyPort = self._strategy_loader.resolve(
            source_path
        )
        source: DrawSource = strategy.load(source_path)
        svg: str = self._svg_drawer.draw(source)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(svg, encoding="utf-8")

        return {
            "source_format": source.source_format,
            "source_strategy": strategy.__class__.__name__,
            "svg_path": str(target_path),
            "width": source.width,
            "height": source.height,
        }

    @staticmethod
    def _source_path(context: CliContextPort) -> Path:
        raw_path: str = str(
            context.get_parameter_value("source_path") or ""
        ).strip()
        source_path: Path = Path(raw_path).expanduser().resolve()
        if not source_path.is_file():
            raise ValueError(f"Logo source file does not exist: '{source_path}'.")
        return source_path

    @staticmethod
    def _target_path(context: CliContextPort, source_path: Path) -> Path:
        raw_path: str = str(
            context.get_parameter_value("target_path") or ""
        ).strip()
        target_path: Path = Path(raw_path).expanduser().resolve()
        if target_path.suffix.lower() != ".svg":
            raise ValueError("Logo target path must use the .svg extension.")
        if target_path == source_path:
            raise ValueError("Logo source and target paths must be different.")
        return target_path
