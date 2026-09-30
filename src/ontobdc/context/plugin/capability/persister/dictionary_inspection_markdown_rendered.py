import importlib.resources as importlib_resources
from typing import Any, ClassVar, Dict, List
from pathlib import Path

from jinja2 import Template, Environment, StrictUndefined, FileSystemLoader

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import PersisterCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.adapter.kind_representation import KindRepresentationSummary
from ontobdc.context.adapter.dictionary_inspection_event import (
    DictionaryInspectionEtlStateAdapter,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)


class DictionaryInspectionMarkdownRenderedCapability(PersisterCapability):
    """Render dictionary inspection results from FSM-owned Jinja templates."""

    TEXT_KEY: ClassVar[str] = "text"
    NORMALIZED_TEXT_KEY: ClassVar[str] = "normalized_text"
    LANGUAGE_KEY: ClassVar[str] = "language"
    LEMMA_KEY: ClassVar[str] = "lemma"
    RESOLUTION_KEY: ClassVar[str] = "ontology_term_resolution"
    REPRESENTATIONS_KEY: ClassVar[str] = "kind_representations"
    MARKDOWN_KEY: ClassVar[str] = "result_markdown"
    MARKDOWN_PATH_KEY: ClassVar[str] = "result_markdown_path"

    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.MARKDOWN_RENDERED
    )

    TEMPLATE_PACKAGE: ClassVar[str] = (
        "ontobdc.context.plugin.machine.dictionary_inspection"
    )
    EXACT_TEMPLATE_FILENAME: ClassVar[str] = "exact_match.md.jinja"
    CANDIDATE_LIST_TEMPLATE_FILENAME: ClassVar[str] = "candidate_list.md.jinja"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.persister.target."
            "dictionary_inspection_markdown_rendered"
        ),
        version="1.4.0",
        name="Dictionary Inspection Markdown Rendered",
        description=(
            "Render exact matches or fuzzy candidates from separate FSM-owned "
            "Jinja templates and persist the Markdown ETL state."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "dictionary", "inspection", "markdown", "etl", "jinja"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                TEXT_KEY: {"type": "string", "required": True},
                NORMALIZED_TEXT_KEY: {"type": "string", "required": True},
                LANGUAGE_KEY: {"type": "string", "required": True},
                LEMMA_KEY: {"type": "string", "required": True},
                RESOLUTION_KEY: {"type": "object", "required": True},
                REPRESENTATIONS_KEY: {"type": "object", "required": True},
            },
        },
        output_schema={
            "properties": {
                MARKDOWN_KEY: {"type": "string"},
                MARKDOWN_PATH_KEY: {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "Dictionary inspection Markdown ETL state persisted."},
            "debug_entry": {"en": "Rendering dictionary inspection Markdown."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Markdown da Inspecao do Dicionario Renderizado"
        return "Dictionary Inspection Markdown Rendered"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Renderiza correspondencias exatas ou candidatos com Jinja da FSM."
        return "Render exact matches or candidates with FSM Jinja."

    def is_satisfied(self, context: CliContextPort) -> bool:
        return context.has_parameter(
            self.MARKDOWN_KEY
        ) and DictionaryInspectionEtlStateAdapter.markdown_event_is_present(
            context=context,
            state=self.STATE,
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        text: str = RequiredParameter.of(context, self.TEXT_KEY)
        normalized_text: str = RequiredParameter.of(context, self.NORMALIZED_TEXT_KEY)
        language: str = RequiredParameter.of(context, self.LANGUAGE_KEY)
        lemma: str = RequiredParameter.of(context, self.LEMMA_KEY)
        resolution: Any = context.get_parameter_value(self.RESOLUTION_KEY)
        if not isinstance(resolution, dict):
            raise ValueError(
                f"Context parameter '{self.RESOLUTION_KEY}' must be an object."
            )
        kind_representations: Any = context.get_parameter_value(
            self.REPRESENTATIONS_KEY
        )
        if not isinstance(kind_representations, dict):
            raise ValueError(
                f"Context parameter '{self.REPRESENTATIONS_KEY}' must be an object."
            )

        markdown: str = self._render(
            text=text,
            normalized_text=normalized_text,
            language=language,
            lemma=lemma,
            resolution=resolution,
            kind_representations=KindRepresentationSummary.summarize_all(
                kind_representations, language
            ),
        )
        markdown_path: Path = DictionaryInspectionEtlStateAdapter.write_markdown(
            context=context,
            state=self.STATE,
            markdown=markdown,
        )
        context.set_parameter_value(self.MARKDOWN_KEY, markdown)
        context.set_parameter_value(self.MARKDOWN_PATH_KEY, str(markdown_path))

        return {
            self.MARKDOWN_KEY: markdown,
            self.MARKDOWN_PATH_KEY: str(markdown_path),
        }

    @classmethod
    def _render(
        cls,
        *,
        text: str,
        normalized_text: str,
        language: str,
        lemma: str,
        resolution: Dict[str, Any],
        kind_representations: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        match_type_raw: Any = resolution["match_type"]
        if not isinstance(match_type_raw, str):
            raise ValueError("Dictionary inspection match_type must be a string.")

        if match_type_raw == "exact":
            return cls._render_exact(
                text=text,
                normalized_text=normalized_text,
                language=language,
                lemma=lemma,
                resolution=resolution,
                kind_representations=kind_representations,
            )
        if match_type_raw == "fuzzy-substring":
            return cls._render_candidates(
                text=text,
                normalized_text=normalized_text,
                language=language,
                lemma=lemma,
                resolution=resolution,
                kind_representations=kind_representations,
            )
        raise ValueError(
            "Dictionary inspection Markdown does not support match type "
            f"'{match_type_raw}'."
        )

    @classmethod
    def _render_exact(
        cls,
        *,
        text: str,
        normalized_text: str,
        language: str,
        lemma: str,
        resolution: Dict[str, Any],
        kind_representations: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        if "candidates" in resolution or "candidate_count" in resolution:
            raise ValueError("Exact dictionary matches must not contain candidate data.")
        exact_matches_raw: Any = resolution["exact_matches"]
        if not isinstance(exact_matches_raw, list) or not exact_matches_raw:
            raise ValueError("Exact dictionary resolution requires exact matches.")
        exact_matches: List[Dict[str, Any]] = []
        exact_match_raw: Any
        for exact_match_raw in exact_matches_raw:
            if not isinstance(exact_match_raw, dict):
                raise ValueError("Exact dictionary match must be an object.")
            exact_matches.append(exact_match_raw)

        template: Template = cls._environment().get_template(
            cls.EXACT_TEMPLATE_FILENAME
        )
        rendered: str = template.render(
            text=text,
            normalized_text=normalized_text,
            language=language,
            lemma=lemma,
            exact_matches=exact_matches,
            kind_representations=kind_representations,
        )
        return rendered.rstrip()

    @classmethod
    def _render_candidates(
        cls,
        *,
        text: str,
        normalized_text: str,
        language: str,
        lemma: str,
        resolution: Dict[str, Any],
        kind_representations: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        if "exact_matches" in resolution:
            raise ValueError("Candidate resolution must not contain exact matches.")
        candidate_count_raw: Any = resolution["candidate_count"]
        if not isinstance(candidate_count_raw, int):
            raise ValueError("Dictionary inspection candidate_count must be an integer.")
        candidates: List[Dict[str, Any]] = cls._candidates(resolution)
        if not candidates:
            raise ValueError("Dictionary candidate resolution requires candidates.")
        if candidate_count_raw != len(candidates):
            raise ValueError(
                "Dictionary inspection candidate_count does not match candidates."
            )
        template: Template = cls._environment().get_template(
            cls.CANDIDATE_LIST_TEMPLATE_FILENAME
        )
        rendered: str = template.render(
            text=text,
            normalized_text=normalized_text,
            language=language,
            lemma=lemma,
            candidate_count=candidate_count_raw,
            candidates=candidates,
            kind_representations=kind_representations,
        )
        return rendered.rstrip()

    @classmethod
    def _environment(cls) -> Environment:
        return Environment(
            loader=FileSystemLoader(cls._template_directory()),
            autoescape=False,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @classmethod
    def _template_directory(cls) -> Path:
        resource: Any = importlib_resources.files(cls.TEMPLATE_PACKAGE)
        if not isinstance(resource, Path):
            raise TypeError(
                f"Template package '{cls.TEMPLATE_PACKAGE}' is not backed by "
                "the filesystem; zipped distributions are not supported."
            )
        return resource

    @staticmethod
    def _candidates(resolution: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates_raw: Any = resolution["candidates"]
        if not isinstance(candidates_raw, list):
            raise ValueError("Dictionary inspection candidates must be a list.")
        candidates: List[Dict[str, Any]] = []
        candidate_raw: Any
        for candidate_raw in candidates_raw:
            if not isinstance(candidate_raw, dict):
                raise ValueError("Dictionary inspection candidate must be an object.")
            candidates.append(candidate_raw)
        return candidates
