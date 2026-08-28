import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import List, Type

from ontobdc.shared.domain.model.draw import (
    DrawSource,
    DrawSourceKind,
)
from ontobdc.shared.domain.port.draw import (
    DrawSourceStrategyPort,
    SvgDrawPort,
)


class DrawSourceStrategyLoader:
    """Discover source strategies owned by the draw capability package."""

    _PLUGIN_PACKAGE: str = (
        "ontobdc.shared.plugin.strategy.draw"
    )

    def get_all(self) -> List[Type[DrawSourceStrategyPort]]:
        package: ModuleType = importlib.import_module(self._PLUGIN_PACKAGE)
        strategy_types: List[Type[DrawSourceStrategyPort]] = []

        module_info: pkgutil.ModuleInfo
        for module_info in pkgutil.walk_packages(
            package.__path__,
            f"{package.__name__}.",
        ):
            module: ModuleType = importlib.import_module(module_info.name)
            member: object
            for _, member in inspect.getmembers(module, inspect.isclass):
                if member is DrawSourceStrategyPort:
                    continue
                if not issubclass(member, DrawSourceStrategyPort):
                    continue
                if inspect.isabstract(member):
                    continue
                strategy_types.append(member)

        return sorted(
            set(strategy_types),
            key=lambda strategy_type: (
                -strategy_type.priority,
                strategy_type.__name__,
            ),
        )

    def resolve(self, source_path: Path) -> DrawSourceStrategyPort:
        strategy_type: Type[DrawSourceStrategyPort]
        for strategy_type in self.get_all():
            strategy: DrawSourceStrategyPort = strategy_type()
            if strategy.accepts(source_path):
                return strategy

        raise ValueError(
            f"No draw source strategy understands '{source_path}'."
        )


class VTracerSvgDrawAdapter(SvgDrawPort):
    """Draw raster sources with VTracer and preserve existing SVG sources."""

    def draw(self, source: DrawSource) -> str:
        if source.kind is DrawSourceKind.VECTOR:
            return source.content.decode("utf-8")

        # Imported lazily: only raster tracing needs it, so a runtime without
        # the (Rust-backed) ``vtracer`` wheel can still load this module and
        # pass SVG sources through unchanged.
        try:
            import vtracer
        except ImportError as error:  # pragma: no cover - depends on env
            raise RuntimeError(
                "Tracing a raster logo to SVG requires the optional 'vtracer' "
                "package. Install it (pip install 'ontobdc[logo]') or provide "
                "an SVG source instead."
            ) from error

        svg: str = vtracer.convert_raw_image_to_svg(
            source.content,
            img_format=source.content_format.lower(),
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=1,
            color_precision=8,
            layer_difference=1,
            path_precision=3,
        )
        return svg
