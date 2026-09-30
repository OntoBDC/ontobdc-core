import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.storage.adapter.bootstrap import StorageLayoutConstants


ETL_MODULE_NAME: str = "context"
ETL_PHASE_NAME: str = "suggestion"
ETL_ENTITY_NAME: str = "file"
CATEGORY_EVENT_FILE: str = "__category_candidates_found__.json"
MARKER_DIRECTORY: str = StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME

KIND_ROOT: str = "root"
KIND_CATEGORY: str = "section"
KIND_FILE: str = "file"


@dataclass(frozen=True)
class SuggestionFileEntry:
    file_path: str
    display_name: str
    best_score: float


@dataclass(frozen=True)
class SuggestionCategoryEntry:
    category_iri: str
    header: str
    label: str
    prefix: str
    term_type: str
    files: Tuple[SuggestionFileEntry, ...]


@dataclass(frozen=True)
class SuggestionStructuredData:
    categories: Tuple[SuggestionCategoryEntry, ...]
    unmatched_files: Tuple[SuggestionFileEntry, ...]


class SuggestionScoreColor:
    """Translate a suggestion match score into a painted label fragment.

    Rules (user-specified):
    * Score == 1.00               -> green + bold
    * Score in [0.80, 1.00)       -> blue  + bold
    * Score in [0.50, 0.80)       -> plain white
    * Score <  0.50 (incl. 0.00)  -> grey (BRIGHT_BLACK)
    """

    @classmethod
    def label(cls, *, score: float) -> str:
        formatted: str = f"{float(score):.2f}"
        color_prefix: str
        if score >= 1.0 - 1e-9:
            color_prefix = TerminalColor.GREEN + TerminalColor.BOLD
        elif score >= 0.80:
            color_prefix = TerminalColor.BLUE + TerminalColor.BOLD
        elif score >= 0.50:
            color_prefix = TerminalColor.WHITE
        else:
            color_prefix = TerminalColor.GRAY
        return (
            f"{color_prefix}(score {formatted}){TerminalColor.RESET}"
        )


class SuggestionTreeBuilder:
    """Build the Context/Contexto reverse tree presented after the
    suggestion pipeline runs.

    The on-disk event is grouped FILE -> CATEGORY -> CHUNK. For a reader
    that is browsing which ontology terms were found, the inverse view is
    more useful:

    * Root: Context (Contexto in pt-br)
    * Child: one entry per ONTOLOGY CATEGORY / TERM (best label, prefix,
      term type). Sorted by number of files descending, then label.
    * Leaf under each category: the FILES where that category matched,
      each annotated with its best score for that category, painted via
      :class:`SuggestionScoreColor`.
    """

    UNMATCHED_CATEGORY_IRI: ClassVar[str] = "__unmatched__"

    @classmethod
    def of(cls, *, container_path: Path) -> Dict[str, Any]:
        event_path: Path = (
            container_path
            / MARKER_DIRECTORY
            / EtlDirectoryContract.DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / CATEGORY_EVENT_FILE
        )
        if not event_path.is_file():
            return {
                "name": "Context",
                "kind": KIND_ROOT,
                "children": [],
            }
        payload: Dict[str, Any] = json.loads(
            event_path.read_text(encoding="utf-8")
        )
        return cls._build(payload)

    @classmethod
    def export_structured(
        cls,
        *,
        container_path: Path,
    ) -> SuggestionStructuredData:
        event_path: Path = (
            container_path
            / MARKER_DIRECTORY
            / EtlDirectoryContract.DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / CATEGORY_EVENT_FILE
        )
        if not event_path.is_file():
            return SuggestionStructuredData(categories=(), unmatched_files=())
        payload: Dict[str, Any] = json.loads(
            event_path.read_text(encoding="utf-8")
        )
        return cls._build_structured(payload)

    @classmethod
    def _build(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        files_entries: List[Dict[str, Any]]
        raw: Any = payload.get("files")
        if isinstance(raw, list):
            files_entries = raw
        else:
            files_entries = []

        category_aggregate: Dict[
            str,
            Dict[str, Any],
        ] = {}

        file_entry: Dict[str, Any]
        for file_entry in files_entries:
            file_path: Any = file_entry.get("file_path")
            file_name: Any = file_entry.get("file_name")
            if not isinstance(file_path, str) or not file_path.strip():
                continue
            display_file: str
            if isinstance(file_name, str) and file_name.strip():
                display_file = file_name.strip()
            else:
                display_file = file_path.strip()
            categories_raw: Any = file_entry.get("categories")
            if not isinstance(categories_raw, list):
                continue
            category_entry: Any
            for category_entry in categories_raw:
                if not isinstance(category_entry, dict):
                    continue
                iri_raw: Any = category_entry.get("category_iri")
                if not isinstance(iri_raw, str) or not iri_raw.strip():
                    continue
                iri: str = iri_raw.strip()
                label_raw: Any = category_entry.get("category_label")
                prefix_raw: Any = category_entry.get("ontology_prefix")
                ttype_raw: Any = category_entry.get("term_type")
                chunks_raw: Any = category_entry.get("chunks")
                if not isinstance(chunks_raw, list) or not chunks_raw:
                    continue
                best_score: float = cls._best_score(chunks_raw)
                bucket: Dict[str, Any]
                if iri not in category_aggregate:
                    readable_label: str
                    if isinstance(label_raw, str) and label_raw.strip():
                        readable_label = label_raw.strip()
                    else:
                        readable_label = iri.split("#")[-1] if "#" in iri else iri.split("/")[-1]
                    header_parts: List[str] = [readable_label]
                    if isinstance(prefix_raw, str) and prefix_raw.strip():
                        header_parts.append(prefix_raw.strip())
                    if isinstance(ttype_raw, str) and ttype_raw.strip():
                        short: str = ttype_raw.split("#")[-1] if "#" in ttype_raw else ttype_raw.split("/")[-1]
                        header_parts.append(short)
                    bucket = {
                        "iri": iri,
                        "label": readable_label,
                        "prefix": (
                            prefix_raw.strip()
                            if isinstance(prefix_raw, str)
                            and prefix_raw.strip()
                            else ""
                        ),
                        "term_type": (
                            ttype_raw.strip()
                            if isinstance(ttype_raw, str)
                            and ttype_raw.strip()
                            else ""
                        ),
                        "header": " · ".join(header_parts),
                        "files": {},
                    }
                    category_aggregate[iri] = bucket
                else:
                    bucket = category_aggregate[iri]
                files_by_path: Dict[str, Any] = bucket["files"]
                if file_path in files_by_path:
                    current: float = float(files_by_path[file_path]["score"])
                    if best_score > current:
                        files_by_path[file_path] = {
                            "display": display_file,
                            "score": best_score,
                        }
                else:
                    files_by_path[file_path] = {
                        "display": display_file,
                        "score": best_score,
                    }

        bucket_list: List[Dict[str, Any]] = list(category_aggregate.values())
        bucket_list.sort(
            key=lambda b: (
                -(len(b["files"]) if isinstance(b["files"], dict) else 0),
                1 if b.get("iri") == cls.UNMATCHED_CATEGORY_IRI else 0,
                str(b.get("header", "")),
            )
        )

        real_categories: List[Dict[str, Any]] = []
        unmatched_bucket: Optional[Dict[str, Any]] = None
        for b in bucket_list:
            if b.get("iri") == cls.UNMATCHED_CATEGORY_IRI:
                unmatched_file_items: Dict[str, Any] = (
                    b["files"] if isinstance(b["files"], dict) else {}
                )
                file_entries: List[Dict[str, Any]] = []
                for (_fp, info) in sorted(
                    unmatched_file_items.items(),
                    key=lambda kv: str(kv[1].get("display", kv[0])),
                ):
                    display_file = info.get("display")
                    display_str: str
                    if isinstance(display_file, str) and display_file.strip():
                        display_str = display_file.strip()
                    else:
                        display_str = str(_fp)
                    file_entries.append(
                        {
                            "name": display_str,
                            "kind": KIND_FILE,
                            "children": [],
                        }
                    )
                unmatched_count: int = len(file_entries)
                header_str: str = str(b.get("header", "")) or "Unmatched chunks"
                unmatched_bucket = {
                    "name": (
                        header_str
                        + f" ({unmatched_count} arquivo{'s' if unmatched_count != 1 else ''})"
                    ),
                    "kind": KIND_CATEGORY,
                    "children": file_entries,
                }
            else:
                file_items: Dict[str, Any] = (
                    b["files"] if isinstance(b["files"], dict) else {}
                )
                file_sorted_new: List[Tuple[str, Dict[str, Any]]] = sorted(
                    file_items.items(),
                    key=lambda kv: (
                        -float(kv[1].get("score", 0.0)),
                        str(kv[1].get("display", kv[0])),
                    ),
                )
                file_children_new: List[Dict[str, Any]] = []
                for (_fp, info) in file_sorted_new:
                    display_file = info.get("display")
                    score_value = float(info.get("score", 0.0))
                    if isinstance(display_file, str) and display_file.strip():
                        display_str_inner: str = display_file.strip()
                    else:
                        display_str_inner = str(_fp)
                    node_name: str = (
                        f"{display_str_inner}  "
                        f"{SuggestionScoreColor.label(score=score_value)}"
                    )
                    file_children_new.append(
                        {"name": node_name, "kind": KIND_FILE, "children": []}
                    )
                file_count_value: int = len(file_sorted_new)
                header_new: str = str(b.get("header", b.get("iri", "")))
                suffix_new: str = (
                    f" ({file_count_value} arquivo{'s' if file_count_value != 1 else ''})"
                )
                real_categories.append(
                    {
                        "name": header_new + suffix_new,
                        "kind": KIND_CATEGORY,
                        "children": file_children_new,
                    }
                )
        root_name_raw: Any = payload.get("__root_name__")
        if isinstance(root_name_raw, str) and root_name_raw.strip():
            root_name_value: str = root_name_raw.strip()
        else:
            root_name_value = "Contexto / Context"
        root_children: List[Dict[str, Any]] = []
        if real_categories:
            match_section_name: str = (
                "Categorias identificadas / Identified categories"
                f" ({len(real_categories)} termo{'s' if len(real_categories) != 1 else ''})"
            )
            root_children.append(
                {
                    "name": match_section_name,
                    "kind": "section",
                    "children": real_categories,
                }
            )
        if unmatched_bucket is not None:
            unmatched_section_name: str = (
                "Arquivos sem categoria definida / Unmatched files"
            )
            root_children.append(
                {
                    "name": unmatched_section_name,
                    "kind": "section",
                    "children": [unmatched_bucket],
                }
            )
        return {
            "name": root_name_value,
            "kind": KIND_ROOT,
            "children": root_children,
        }

    @staticmethod
    def _best_score(chunks_raw: List[Dict[str, Any]]) -> float:
        best: float = 0.0
        chunk: Dict[str, Any]
        for chunk in chunks_raw:
            s: Any = chunk.get("score")
            if isinstance(s, (int, float)) and not isinstance(s, bool):
                value: float = float(s)
                if value > best:
                    best = value
        return best

    @classmethod
    def _build_structured(
        cls,
        payload: Dict[str, Any],
    ) -> SuggestionStructuredData:
        files_entries: List[Dict[str, Any]]
        raw: Any = payload.get("files")
        if isinstance(raw, list):
            files_entries = raw
        else:
            files_entries = []

        category_aggregate: Dict[
            str,
            Dict[str, Any],
        ] = {}

        file_entry: Dict[str, Any]
        for file_entry in files_entries:
            file_path_any: Any = file_entry.get("file_path")
            file_name_any: Any = file_entry.get("file_name")
            if not isinstance(file_path_any, str) or not file_path_any.strip():
                continue
            file_path: str = file_path_any.strip()
            display_file: str
            if isinstance(file_name_any, str) and file_name_any.strip():
                display_file = file_name_any.strip()
            else:
                display_file = file_path
            categories_raw: Any = file_entry.get("categories")
            if not isinstance(categories_raw, list):
                continue
            category_entry: Any
            for category_entry in categories_raw:
                if not isinstance(category_entry, dict):
                    continue
                iri_raw: Any = category_entry.get("category_iri")
                if not isinstance(iri_raw, str) or not iri_raw.strip():
                    continue
                iri: str = iri_raw.strip()
                label_raw: Any = category_entry.get("category_label")
                prefix_raw: Any = category_entry.get("ontology_prefix")
                ttype_raw: Any = category_entry.get("term_type")
                chunks_raw: Any = category_entry.get("chunks")
                if not isinstance(chunks_raw, list) or not chunks_raw:
                    continue
                best_score: float = cls._best_score(chunks_raw)
                bucket: Dict[str, Any]
                if iri not in category_aggregate:
                    readable_label: str
                    if isinstance(label_raw, str) and label_raw.strip():
                        readable_label = label_raw.strip()
                    else:
                        readable_label = (
                            iri.split("#")[-1]
                            if "#" in iri
                            else iri.split("/")[-1]
                        )
                    header_parts: List[str] = [readable_label]
                    if isinstance(prefix_raw, str) and prefix_raw.strip():
                        header_parts.append(prefix_raw.strip())
                    if isinstance(ttype_raw, str) and ttype_raw.strip():
                        short: str = (
                            ttype_raw.split("#")[-1]
                            if "#" in ttype_raw
                            else ttype_raw.split("/")[-1]
                        )
                        header_parts.append(short)
                    bucket = {
                        "iri": iri,
                        "label": readable_label,
                        "prefix": (
                            prefix_raw.strip()
                            if isinstance(prefix_raw, str)
                            and prefix_raw.strip()
                            else ""
                        ),
                        "term_type": (
                            ttype_raw.strip()
                            if isinstance(ttype_raw, str)
                            and ttype_raw.strip()
                            else ""
                        ),
                        "header": " · ".join(header_parts),
                        "files": {},
                    }
                    category_aggregate[iri] = bucket
                else:
                    bucket = category_aggregate[iri]
                files_by_path: Dict[str, Any] = bucket["files"]
                if file_path in files_by_path:
                    current_score: float = float(
                        files_by_path[file_path]["best_score"]
                    )
                    if best_score > current_score:
                        files_by_path[file_path] = {
                            "display": display_file,
                            "best_score": best_score,
                        }
                else:
                    files_by_path[file_path] = {
                        "display": display_file,
                        "best_score": best_score,
                    }

        bucket_list: List[Dict[str, Any]] = list(category_aggregate.values())
        bucket_list.sort(
            key=lambda b: (
                1 if b.get("iri") == cls.UNMATCHED_CATEGORY_IRI else 0,
                -(len(b["files"]) if isinstance(b["files"], dict) else 0),
                str(b.get("header", "")),
            )
        )

        real_categories: List[SuggestionCategoryEntry] = []
        unmatched_files_acc: List[SuggestionFileEntry] = []
        bucket: Dict[str, Any]
        for bucket in bucket_list:
            file_items: Dict[str, Any] = (
                bucket["files"] if isinstance(bucket["files"], dict) else {}
            )
            file_sorted: List[Tuple[str, Dict[str, Any]]] = sorted(
                file_items.items(),
                key=lambda kv: (
                    -float(kv[1].get("best_score", 0.0)),
                    str(kv[1].get("display", kv[0])),
                ),
            )
            file_entries_result: List[SuggestionFileEntry] = [
                SuggestionFileEntry(
                    file_path=fp,
                    display_name=str(
                        info.get("display", fp)
                    ),
                    best_score=float(
                        info.get("best_score", 0.0)
                    ),
                )
                for (fp, info) in file_sorted
            ]
            if bucket.get("iri") == cls.UNMATCHED_CATEGORY_IRI:
                unmatched_files_acc.extend(file_entries_result)
            else:
                real_categories.append(
                    SuggestionCategoryEntry(
                        category_iri=str(bucket.get("iri", "")),
                        header=str(bucket.get("header", "")),
                        label=str(bucket.get("label", "")),
                        prefix=str(bucket.get("prefix", "")),
                        term_type=str(bucket.get("term_type", "")),
                        files=tuple(file_entries_result),
                    )
                )
        return SuggestionStructuredData(
            categories=tuple(real_categories),
            unmatched_files=tuple(unmatched_files_acc),
        )
