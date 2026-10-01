from typing import Any, Dict

import pytest

from ontobdc.container.plugin.machine.container_refresh.state import (
    ContainerRefreshProcessState,
)


class TestContainerRefreshProcessStateEnumeration:
    """Verify enum values, names and the ``strip("_")`` YAML convention."""

    EXPECTED_VALUES: Dict[str, str] = {
        "UNDEFINED": "__undefined__",
        "CONTAINER_INVALID": "__container_invalid__",
        "CONTAINER_HEALTHY": "__container_healthy__",
        "CONTAINER_DATASETS_HEALTHY": "__container_datasets_healthy__",
        "CONTAINER_CLEANED": "__container_cleaned__",
        "CONTAINER_DATAPACKAGE_UPDATED": "__container_datapackage_updated__",
        "CONTAINER_RO_CRATE_UPDATED": "__container_ro_crate_updated__",
        "CONTAINER_UPDATED": "__container_updated__",
    }

    def test_has_exactly_eight_states(self) -> None:
        states: Dict[str, Any] = {
            name: value
            for name, value in ContainerRefreshProcessState.__dict__.items()
            if not name.startswith("_") and name.isupper()
        }
        assert len(states) == len(self.EXPECTED_VALUES)

    def test_each_state_value_follows_the_dunder_convention(self) -> None:
        state_name: str
        expected_value: str
        for state_name, expected_value in self.EXPECTED_VALUES.items():
            state: ContainerRefreshProcessState = getattr(
                ContainerRefreshProcessState, state_name,
            )
            assert state.value == expected_value
            assert state.value.strip("_") == expected_value.strip("_")

    def test_value_stripped_of_underscores_yields_the_statechart_state_name(
        self,
    ) -> None:
        pairs: Dict[str, str] = {
            "UNDEFINED": "undefined",
            "CONTAINER_INVALID": "container_invalid",
            "CONTAINER_HEALTHY": "container_healthy",
            "CONTAINER_DATASETS_HEALTHY": "container_datasets_healthy",
            "CONTAINER_CLEANED": "container_cleaned",
            "CONTAINER_DATAPACKAGE_UPDATED": "container_datapackage_updated",
            "CONTAINER_RO_CRATE_UPDATED": "container_ro_crate_updated",
            "CONTAINER_UPDATED": "container_updated",
        }
        member_name: str
        yaml_name: str
        for member_name, yaml_name in pairs.items():
            member: ContainerRefreshProcessState = getattr(
                ContainerRefreshProcessState, member_name,
            )
            assert member.value.strip("_") == yaml_name


class TestContainerRefreshProcessStateGetState:
    """Verify the case-insensitive upper-based state lookup."""

    @pytest.mark.parametrize("member_name", list(
        TestContainerRefreshProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_uppercase_members(self, member_name: str) -> None:
        result: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.get_state(member_name)
        )
        assert result is getattr(ContainerRefreshProcessState, member_name)

    @pytest.mark.parametrize("member_name", list(
        TestContainerRefreshProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_lowercase_members(self, member_name: str) -> None:
        result: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.get_state(member_name.lower())
        )
        assert result is getattr(ContainerRefreshProcessState, member_name)

    @pytest.mark.parametrize("member_name", list(
        TestContainerRefreshProcessStateEnumeration.EXPECTED_VALUES.keys(),
    ))
    def test_get_state_accepts_mixed_case_members(self, member_name: str) -> None:
        mixed: str = "".join(
            ch.lower() if idx % 2 else ch.upper()
            for idx, ch in enumerate(member_name)
        )
        result: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.get_state(mixed)
        )
        assert result is getattr(ContainerRefreshProcessState, member_name)

    def test_get_state_raises_for_unknown_names(self) -> None:
        with pytest.raises(AttributeError):
            ContainerRefreshProcessState.get_state("does_not_exist")


class TestContainerRefreshProcessStateNormalizePresentationMetadata:
    """Verify dict/str/other value normalization for labels and descriptions."""

    def test_string_value_becomes_a_single_english_entry(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_HEALTHY
        )
        state.bind_presentation_metadata(label="Saudavel")
        result: Dict[str, str] = state._normalize_presentation_metadata("Saudavel")
        assert result == {"en": "Saudavel"}

    def test_none_value_yields_an_empty_mapping(self) -> None:
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(None)
        )
        assert result == {}

    def test_integer_value_yields_an_empty_mapping(self) -> None:
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(42)
        )
        assert result == {}

    def test_list_value_yields_an_empty_mapping(self) -> None:
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata([])
        )
        assert result == {}

    def test_object_value_yields_an_empty_mapping(self) -> None:
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(object())
        )
        assert result == {}

    def test_language_keys_are_normalized(self) -> None:
        raw: Dict[str, str] = {
            "EN": "Undefined",
            " PT_BR  ": "Indefinido",
        }
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(raw)
        )
        assert result["en"] == "Undefined"
        assert result["pt-br"] == "Indefinido"

    def test_empty_language_keys_are_dropped(self) -> None:
        raw: Dict[str, str] = {
            "en": "Healthy",
            "": "ignored",
            "   ": "also_ignored",
        }
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(raw)
        )
        assert result == {"en": "Healthy"}

    def test_none_language_values_are_dropped(self) -> None:
        raw: Dict[str, Any] = {
            "en": "Ready",
            "pt-br": None,
        }
        result: Dict[str, str] = (
            ContainerRefreshProcessState._normalize_presentation_metadata(raw)
        )
        assert result == {"en": "Ready"}


class TestContainerRefreshProcessStateLabelAndDescription:
    """Verify fallback chain: requested lang → English → default."""

    def test_label_returns_requested_language_when_present(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_UPDATED
        )
        state.bind_presentation_metadata(
            label={"en": "Updated", "pt-br": "Atualizado"},
        )
        assert state.label("pt-br") == "Atualizado"

    def test_label_falls_back_to_english(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_CLEANED
        )
        state.bind_presentation_metadata(label={"en": "Cleaned"})
        assert state.label("pt-br") == "Cleaned"

    def test_label_falls_back_to_enum_value(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_INVALID
        )
        assert state.label("pt-br") == state.value

    def test_description_returns_requested_language_when_present(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED
        )
        state.bind_presentation_metadata(
            description={"en": "Synced.", "pt-br": "Sincronizado."},
        )
        assert state.description("pt-br") == "Sincronizado."

    def test_description_falls_back_to_english(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED
        )
        state.bind_presentation_metadata(description={"en": "Descriptor updated."})
        assert state.description("pt-br") == "Descriptor updated."

    def test_description_falls_back_to_empty_string(self) -> None:
        state: ContainerRefreshProcessState = (
            ContainerRefreshProcessState.CONTAINER_DATASETS_HEALTHY
        )
        assert state.description("pt-br") == ""
