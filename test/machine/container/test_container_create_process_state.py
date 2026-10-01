from typing import Any, Dict

import pytest

from ontobdc.container.plugin.machine.container_create.state import (
    ContainerCreateProcessState,
    DatasetCreateProcessState,
)


class TestContainerCreateProcessStateEnumeration:
    """Verify enum values, names and the ``strip("_")`` YAML convention."""

    EXPECTED_VALUES: Dict[str, str] = {
        "UNDEFINED": "__undefined__",
        "INVALID_PATH": "__invalid_path__",
        "DIRECTORY_READY": "__directory_ready__",
        "CONTAINER_METADATA_READY": "__container_metadata_ready__",
        "CONTAINER_STORAGE_INDEX_READY": "__container_storage_index_ready__",
        "CONTAINER_MANIFEST_SYNCED": "__container_manifest_synced__",
    }

    def test_has_exactly_six_states(self) -> None:
        states: Dict[str, Any] = {
            name: value
            for name, value in ContainerCreateProcessState.__dict__.items()
            if not name.startswith("_") and name.isupper()
        }
        assert len(states) == len(self.EXPECTED_VALUES)

    def test_each_state_value_follows_the_dunder_convention(self) -> None:
        state_name: str
        expected_value: str
        for state_name, expected_value in self.EXPECTED_VALUES.items():
            state: ContainerCreateProcessState = getattr(
                ContainerCreateProcessState, state_name,
            )
            assert state.value == expected_value
            assert state.value.strip("_") == expected_value.strip("_")

    def test_value_stripped_of_underscores_yields_the_statechart_state_name(
        self,
    ) -> None:
        pairs: Dict[str, str] = {
            "UNDEFINED": "undefined",
            "INVALID_PATH": "invalid_path",
            "DIRECTORY_READY": "directory_ready",
            "CONTAINER_METADATA_READY": "container_metadata_ready",
            "CONTAINER_STORAGE_INDEX_READY": "container_storage_index_ready",
            "CONTAINER_MANIFEST_SYNCED": "container_manifest_synced",
        }
        member_name: str
        yaml_name: str
        for member_name, yaml_name in pairs.items():
            member: ContainerCreateProcessState = getattr(
                ContainerCreateProcessState, member_name,
            )
            assert member.value.strip("_") == yaml_name


class TestContainerCreateProcessStateGetState:
    """Verify the case-insensitive upper-based state lookup."""

    @pytest.mark.parametrize("member_name", list(
        TestContainerCreateProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_uppercase_members(self, member_name: str) -> None:
        result: ContainerCreateProcessState = (
            ContainerCreateProcessState.get_state(member_name)
        )
        assert result is getattr(ContainerCreateProcessState, member_name)

    @pytest.mark.parametrize("member_name", list(
        TestContainerCreateProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_lowercase_members(self, member_name: str) -> None:
        result: ContainerCreateProcessState = (
            ContainerCreateProcessState.get_state(member_name.lower())
        )
        assert result is getattr(ContainerCreateProcessState, member_name)

    @pytest.mark.parametrize("member_name", list(
        TestContainerCreateProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_mixed_case_members(self, member_name: str) -> None:
        mixed: str = "".join(
            ch.lower() if idx % 2 else ch.upper()
            for idx, ch in enumerate(member_name)
        )
        result: ContainerCreateProcessState = (
            ContainerCreateProcessState.get_state(mixed)
        )
        assert result is getattr(ContainerCreateProcessState, member_name)

    def test_get_state_raises_for_unknown_names(self) -> None:
        with pytest.raises(AttributeError):
            ContainerCreateProcessState.get_state("does_not_exist")


class TestContainerCreateProcessStateNormalizePresentationMetadata:
    """Verify presentation metadata normalization rules."""

    def test_string_label_becomes_english_only(self) -> None:
        result: Dict[str, str] = (
            ContainerCreateProcessState._normalize_presentation_metadata(
                "Directory Ready",
            )
        )
        assert result == {"en": "Directory Ready"}

    def test_none_and_non_mapping_yield_empty_dictionaries(self) -> None:
        assert ContainerCreateProcessState._normalize_presentation_metadata(None) == {}
        assert ContainerCreateProcessState._normalize_presentation_metadata([]) == {}
        assert ContainerCreateProcessState._normalize_presentation_metadata(123) == {}
        assert ContainerCreateProcessState._normalize_presentation_metadata(False) == {}
        assert ContainerCreateProcessState._normalize_presentation_metadata(object()) == {}

    def test_mapping_language_keys_are_normalized(self) -> None:
        raw: Dict[Any, Any] = {
            "en": "Undefined",
            "PT_BR": "Indefinido",
            "  ": "Ignorado: idioma vazio",
            "de": None,
            "fr": "Non défini",
        }
        result: Dict[str, str] = (
            ContainerCreateProcessState._normalize_presentation_metadata(raw)
        )
        assert result["en"] == "Undefined"
        assert result["pt-br"] == "Indefinido"
        assert result["fr"] == "Non défini"
        assert "" not in result
        assert "de" not in result
        assert len(result) == 3

    def test_empty_language_key_is_dropped_even_with_value(self) -> None:
        raw: Dict[Any, Any] = {"": "Something", "en": "Real value"}
        result: Dict[str, str] = (
            ContainerCreateProcessState._normalize_presentation_metadata(raw)
        )
        assert "" not in result
        assert result == {"en": "Real value"}


class TestContainerCreateProcessStateLabelAndDescription:
    """Verify localization, fallbacks and default values for label/description."""

    def setup_method(self) -> None:
        self.state: ContainerCreateProcessState = (
            ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED
        )

    def test_label_defaults_to_the_raw_value_without_metadata(self) -> None:
        assert self.state.label() == self.state.value
        assert self.state.label(lang="pt-br") == self.state.value
        assert self.state.label(lang="de") == self.state.value

    def test_description_defaults_to_empty_string_without_metadata(self) -> None:
        assert self.state.description() == ""
        assert self.state.description(lang="pt-br") == ""
        assert self.state.description(lang="de") == ""

    def test_bind_presentation_metadata_sets_up_localized_values(self) -> None:
        self.state.bind_presentation_metadata(
            label={
                "en": "Manifest Synced",
                "PT_BR": "Manifesto Sincronizado",
            },
            description={
                "en": "Manifest has been synchronized with storage.",
                "pt-br": "Manifesto foi sincronizado com armazenamento.",
            },
        )
        assert self.state.label() == "Manifest Synced"
        assert self.state.label("en") == "Manifest Synced"
        assert self.state.label("pt-br") == "Manifesto Sincronizado"
        assert self.state.label("  PT_BR  ") == "Manifesto Sincronizado"
        assert self.state.description() == (
            "Manifest has been synchronized with storage."
        )
        assert self.state.description("pt-br") == (
            "Manifesto foi sincronizado com armazenamento."
        )

    def test_missing_language_falls_back_to_english(self) -> None:
        self.state.bind_presentation_metadata(
            label={"en": "English"},
            description={"en": "English description"},
        )
        assert self.state.label("zh-cn") == "English"
        assert self.state.description("zh-cn") == "English description"

    def test_missing_english_language_falls_back_to_defaults(self) -> None:
        self.state.bind_presentation_metadata(
            label={"pt-br": "Sem inglês"},
            description={"pt-br": "Sem inglês"},
        )
        assert self.state.label() == self.state.value
        assert self.state.label("pt-br") == "Sem inglês"
        assert self.state.description() == ""
        assert self.state.description("pt-br") == "Sem inglês"

    def test_string_argument_to_bind_presentation_metadata_sets_only_english(
        self,
    ) -> None:
        self.state.bind_presentation_metadata(
            label="One label",
            description="One description",
        )
        assert self.state.label() == "One label"
        assert self.state.label("en") == "One label"
        assert self.state.label("pt-br") == "One label"
        assert self.state.description() == "One description"
        assert self.state.description("en") == "One description"
        assert self.state.description("pt-br") == "One description"


class TestDatasetCreateProcessStateEnumeration:
    """Keep the twin enum (Dataset) exercised for the same module cohesion."""

    EXPECTED_MEMBERS: Dict[str, str] = {
        "UNDEFINED": "__undefined__",
        "INVALID_PATH": "__invalid_path__",
        "DIRECTORY_READY": "__directory_ready__",
        "DATASET_METADATA_READY": "__dataset_metadata_ready__",
        "DATASET_CONTAINER_INDEX_READY": "__dataset_container_index_ready__",
    }

    def test_has_exactly_five_members(self) -> None:
        members: Dict[str, Any] = {
            name: value
            for name, value in DatasetCreateProcessState.__dict__.items()
            if not name.startswith("_") and name.isupper()
        }
        assert len(members) == len(self.EXPECTED_MEMBERS)

    @pytest.mark.parametrize("member_name", list(EXPECTED_MEMBERS.keys()))
    def test_member_value_matches(self, member_name: str) -> None:
        member: DatasetCreateProcessState = getattr(
            DatasetCreateProcessState, member_name,
        )
        assert member.value == self.EXPECTED_MEMBERS[member_name]

    def test_get_state_looks_up_members_case_insensitively(self) -> None:
        assert DatasetCreateProcessState.get_state("dataset_metadata_ready") is (
            DatasetCreateProcessState.DATASET_METADATA_READY
        )
        assert DatasetCreateProcessState.get_state("DATASET_CONTAINER_INDEX_READY") is (
            DatasetCreateProcessState.DATASET_CONTAINER_INDEX_READY
        )

    def test_label_returns_english_entries_by_default(self) -> None:
        assert DatasetCreateProcessState.UNDEFINED.label() == "Undefined"
        assert DatasetCreateProcessState.INVALID_PATH.label() == "Invalid Path"
        assert DatasetCreateProcessState.DIRECTORY_READY.label() == "Directory Ready"
        assert DatasetCreateProcessState.DATASET_METADATA_READY.label() == (
            "Dataset Metadata Ready"
        )
        assert DatasetCreateProcessState.DATASET_CONTAINER_INDEX_READY.label() == (
            "Dataset Container Index Ready"
        )

    def test_label_translates_portuguese(self) -> None:
        assert DatasetCreateProcessState.UNDEFINED.label("pt-br") == "Indefinido"
        assert DatasetCreateProcessState.INVALID_PATH.label("pt-br") == (
            "Caminho Invalido"
        )
        assert DatasetCreateProcessState.DATASET_METADATA_READY.label("pt-br") == (
            "Metadados do Dataset Prontos"
        )

    def test_label_unknown_language_falls_back_to_english(self) -> None:
        assert DatasetCreateProcessState.DIRECTORY_READY.label("de") == (
            "Directory Ready"
        )

    def test_description_returns_non_empty_strings_for_known_states(self) -> None:
        member: DatasetCreateProcessState
        for member_name in self.EXPECTED_MEMBERS:
            member = getattr(DatasetCreateProcessState, member_name)
            english: str = member.description()
            portuguese: str = member.description("pt-br")
            assert isinstance(english, str) and english
            assert isinstance(portuguese, str) and portuguese
            assert english != portuguese or member_name == "DIRECTORY_READY"
