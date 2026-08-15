"""i18n locale catalog tests for the annotation UI's translated labels."""

from __future__ import annotations

from ontobdc.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, catalog_for_namespace, full_catalog


def test_supported_locales():
    assert set(SUPPORTED_LOCALES) == {"en", "pt-BR", "pt-PT", "es"}
    assert DEFAULT_LOCALE == "en"


def test_full_catalog_has_every_locale():
    catalog = full_catalog()
    assert set(catalog.keys()) == set(SUPPORTED_LOCALES)


def test_every_locale_has_the_same_keys_in_annotation_namespace():
    catalog = full_catalog()
    base_keys = set(catalog[DEFAULT_LOCALE]["annotation"].keys())
    for locale in SUPPORTED_LOCALES:
        keys = set(catalog[locale]["annotation"].keys())
        assert keys == base_keys, f"locale '{locale}' keys {keys} != {base_keys}"


def test_category_labels_and_tool_labels_are_nested_dicts_per_locale():
    annotation = catalog_for_namespace("annotation")
    for locale in SUPPORTED_LOCALES:
        assert set(annotation[locale]["categoryLabels"].keys()) == {
            "NoteAnnotation", "IssueAnnotation", "ClassificationAnnotation",
            "LocationAnnotation", "RecordAnnotation",
        }
        assert set(annotation[locale]["toolLabels"].keys()) == {
            "select", "point", "multiple-points", "bounding-box", "clear",
        }


def test_pt_br_and_pt_pt_are_distinct():
    annotation = catalog_for_namespace("annotation")
    assert annotation["pt-BR"]["timeline"] == "Linha do tempo"
    assert annotation["pt-PT"]["timeline"] == "Linha temporal"
    assert annotation["pt-BR"]["timeline"] != annotation["pt-PT"]["timeline"]
