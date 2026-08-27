from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Same shipped defaults as ontobdc_view.component.adapter.source._BRAND --
# kept as a local, self-contained copy (this module has no dependency on
# ontobdc_view) so a freshly-seeded config.yaml always starts from a real,
# renderable brand instead of a placeholder that would need replacing
# before anything shows up.
_DEFAULT_BRAND: Dict[str, str] = {
    "name": "OntoBDC",
    "mark_svg": (
        '<svg viewBox="0 0 64 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="25" fill="none" stroke="currentColor" stroke-width="8"/>'
        '<circle cx="32" cy="32" r="7" fill="currentColor"/></svg>'
    ),
    "logotype_svg": (
        '<svg viewBox="0 0 260 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="23" fill="none" stroke="var(--onto-theme-accent, currentColor)" stroke-width="7"/>'
        '<circle cx="32" cy="32" r="6" fill="var(--onto-theme-accent, currentColor)"/>'
        '<text x="68" y="42" fill="currentColor" font-family="system-ui, sans-serif" '
        'font-size="31" font-weight="700">OntoBDC</text></svg>'
    ),
    "slogan": "Data with Brains",
}

# Mirror of the product-asset layout already declared in
# ontobdc.view.plugin.capability.transformation.surface_branded and in the
# ontobdc_view brand resolver -- zero-coupling approach (A): we do not
# import either module; instead we simply read whichever SVGs that
# capability has already downloaded into the project's hidden directories
# when `brand_ready` runs *after* a surface has been generated.
_PRODUCT_ASSET_LAYOUTS = (
    (
        ".__infobim__",
        "assets",
        "InfoBIMBrand.svg",
        "InfoBIMLogotype.svg",
        "InfoBIM",
        "",
    ),
    (
        ".__ontobdc__",
        "asset",
        "OntoBDCBrand.svg",
        "OntoBDCLogotype.svg",
        "OntoBDC",
        "Data with Brains",
    ),
)


def _read_text_if_svg(path: Path) -> Optional[str]:
    """Return ``path`` decoded content if it exists and looks like an SVG."""
    try:
        if not path.is_file():
            return None
        raw = path.read_bytes()
    except (OSError, ValueError):
        return None
    probe = raw.lstrip()[:512].lower()
    if b"<svg" not in probe:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None


def _candidate_brand_roots(resolved_root_path: Optional[Path]) -> List[Path]:
    """Filesystem starting points where a product marker may be found.

    Same three-tier strategy used in ``ontobdc_view.component.adapter.source``
    for symmetry -- see there for the detailed rationale:
        1. Explicit project path passed in (and its parent, for file hints).
        2. Current working directory (shell convenience).
        3. Installed-package ``__file__`` dirs (ontobdc / ontobdc_view /
           infobim) -- these are static for a given environment so are
           immune to cwd-chdir behaviour in build tools and daemons.
    """
    candidates: List[Path] = []

    if isinstance(resolved_root_path, Path):
        try:
            explicit = resolved_root_path.expanduser().resolve()
        except (OSError, ValueError):
            explicit = None
        if explicit is not None:
            candidates.append(explicit)
            try:
                parent = explicit.parent
                if parent != explicit:
                    candidates.append(parent)
            except (OSError, ValueError):
                pass

    try:
        candidates.append(Path.cwd().resolve())
    except (OSError, ValueError):
        pass

    for module_name in ("ontobdc", "ontobdc_view", "infobim"):
        try:
            module = __import__(module_name)
            candidate_roots: List[Path] = []
            module_file = getattr(module, "__file__", None)
            if isinstance(module_file, str) and module_file:
                candidate_roots.append(Path(module_file).expanduser().resolve().parent)
            module_path_list = getattr(module, "__path__", None)
            if isinstance(module_path_list, (list, tuple)):
                for item in module_path_list:
                    if isinstance(item, str) and item:
                        candidate_roots.append(Path(item).expanduser().resolve())
            if not candidate_roots:
                continue
            for pkg_root in candidate_roots:
                for _ in range(10):
                    try:
                        candidates.append(pkg_root.resolve())
                    except (OSError, ValueError):
                        pass
                    try:
                        up = pkg_root.parent
                        if up == pkg_root:
                            break
                        pkg_root = up
                    except (OSError, ValueError):
                        break
        except Exception:
            continue

    seen: set = set()
    ordered: List[Path] = []
    for path in candidates:
        try:
            key = str(path)
        except (OSError, ValueError):
            continue
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def _discover_brand_from_assets(root_path: Path) -> Optional[Dict[str, str]]:
    """Resolve brand from on-disk assets if ``surface_branded`` already ran.

    Walks upward from every starting point returned by
    ``_candidate_brand_roots(root_path)`` (capped at 32 parent levels each
    for safety) looking for the canonical hidden product markers
    (``.__infobim__`` first, then ``.__ontobdc__``) carrying the two
    required SVG assets.  Mirrors ``ontobdc_view.component.adapter.source``
    exactly so the CLI hotfix and the rendered Surface always agree on
    the effective brand, regardless of where the user launched the CLI
    from.
    """
    starting_points = _candidate_brand_roots(root_path)
    for start in starting_points:
        search_bases: List[Path] = []
        candidate = start
        for _ in range(32):
            search_bases.append(candidate)
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent

        for base in search_bases:
            for hidden, asset_dir, brand_file, logotype_file, name, slogan in _PRODUCT_ASSET_LAYOUTS:
                marker = base / hidden
                if not marker.is_dir():
                    continue
                assets = marker / asset_dir
                brand_svg = _read_text_if_svg(assets / brand_file)
                logotype_svg = _read_text_if_svg(assets / logotype_file)
                if brand_svg is None or logotype_svg is None:
                    continue
                return {
                    "name": name,
                    "mark_svg": brand_svg.strip(),
                    "logotype_svg": logotype_svg.strip(),
                    "slogan": slogan,
                }
    return None


def _seed_default_brand(resolved_root_path: Path) -> Dict[str, str]:
    """Return the best starting brand for this project root.

    Precedence (same 3 tiers used in ``ontobdc_view``'s brand resolver for
    symmetry):
        1. Hard-coded ``_DEFAULT_BRAND`` (always there).
        2. Product branding discovered from hidden asset dirs on disk.
    ``config.yaml`` overrides are applied *on top* of this seed by the
    caller (``main()`` below), just like the view layer applies
    ``ConfigDataAdapter`` overrides last.

    ``slogan`` is allowed to be written as an empty string on purpose --
    discovered product tiers for InfoBIM ship no slogan and we do not
    want the seeded yaml to inherit "Data with Brains" in that case.
    """
    base = dict(_DEFAULT_BRAND)
    discovered = _discover_brand_from_assets(resolved_root_path)
    if isinstance(discovered, dict):
        for key, value in discovered.items():
            if not isinstance(value, str):
                continue
            if key == "slogan":
                base[key] = value
            elif value.strip():
                base[key] = value
    return base


def _get_config_file(root_path: Optional[str] = None) -> Path:
    resolved_root_path: Path
    if isinstance(root_path, str) and root_path.strip():
        resolved_root_path = Path(root_path).expanduser().resolve()
    else:
        resolved_root_path = Path.cwd().resolve()

    return resolved_root_path / ".__ontobdc__" / "config.yaml"


def main(root_path: Optional[str] = None) -> int:
    try:
        config_file: Path = _get_config_file(root_path=root_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        resolved_root_path = (
            Path(str(root_path)).expanduser().resolve()
            if isinstance(root_path, str) and root_path.strip()
            else Path.cwd().resolve()
        )

        current_config: Dict[str, Any] = {}
        if config_file.is_file():
            with open(config_file, "r", encoding="utf-8") as file_handle:
                loaded_config: Any = yaml.safe_load(file_handle) or {}

            if isinstance(loaded_config, dict):
                current_config = loaded_config

        brand: object = current_config.get("brand")
        if not isinstance(brand, dict):
            brand = {}

        seed_brand = _seed_default_brand(resolved_root_path)
        for key, default_value in seed_brand.items():
            value: object = brand.get(key)
            # Auto-generated stale override detection: if the yaml carries
            # a value byte-for-byte identical to the OLD shipped
            # ``_DEFAULT_BRAND`` for that key, it was written by the
            # previous hotfix version and the user has never manually
            # edited it -- so treat it as missing and let the freshly
            # discovered (seeded) value win.  Real user overrides are,
            # by definition, different from the shipped default, so this
            # rule never hides a real operator override.
            shipped_default = _DEFAULT_BRAND.get(key)
            is_auto_generated_stale = (
                isinstance(shipped_default, str)
                and isinstance(value, str)
                and shipped_default == value
            )
            if key == "slogan":
                # Allow explicitly blank slogans coming from the existing
                # yaml (the user may have intentionally written
                # `brand:\n  slogan: ""`) -- otherwise use discovered
                # default, OR the freshly discovered value when the
                # current yaml value is an auto-generated stale default.
                if not isinstance(value, str) or is_auto_generated_stale:
                    brand[key] = default_value
            elif (
                not isinstance(value, str)
                or not value.strip()
                or is_auto_generated_stale
            ):
                brand[key] = default_value

        current_config["brand"] = brand

        with open(config_file, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(current_config, file_handle, default_flow_style=False, sort_keys=False)

        return 0
    except Exception:
        return 1
