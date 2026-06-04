import json
from pathlib import Path

from translate.misc.multistring import multistring
from translate.storage import factory, xcstrings


FIXTURE_DIR = Path(__file__).with_name("xcstrings")


def fixture(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def test_factory_registers_xcstrings_extension() -> None:
    assert factory.getclass("Localizable.xcstrings") is xcstrings.XCStringsFile


def test_list_languages_returns_source_and_localization_languages() -> None:
    languages = xcstrings.XCStringsFile.list_languages(fixture("variants.xcstrings"))

    assert languages == ["en", "fr"]


def test_parse_simple_catalog_with_language_code() -> None:
    store = xcstrings.XCStringsFile(fixture("simple.xcstrings"), language_code="fr")

    assert store.getsourcelanguage() == "en"
    assert store.gettargetlanguage() == "fr"
    assert [unit.getid() for unit in store.units] == ["brand", "hello", "missing"]

    hello = store.findid("hello")
    assert hello.source == "Hello"
    assert hello.target == "Bonjour"
    assert hello.getnotes() == "Greeting shown on the home screen"
    assert hello.isfuzzy()


def test_missing_target_value_is_exposed_without_creating_it_on_roundtrip() -> None:
    store = xcstrings.XCStringsFile(fixture("simple.xcstrings"), language_code="fr")
    missing = store.findid("missing")

    assert missing.source == "Missing"
    assert missing.target == ""

    roundtripped = json.loads(bytes(store))
    assert "fr" not in roundtripped["strings"]["missing"]["localizations"]


def test_setting_missing_target_creates_target_localization() -> None:
    store = xcstrings.XCStringsFile(fixture("simple.xcstrings"), language_code="fr")
    store.findid("missing").target = "Absent"

    assert bytes(store).decode() == fixture(
        "simple_missing_translated.expected.xcstrings"
    ).decode()


def test_should_translate_false_is_non_translatable_and_not_written() -> None:
    store = xcstrings.XCStringsFile(fixture("simple.xcstrings"), language_code="fr")
    brand = store.findid("brand")

    assert not brand.istranslatable()
    brand.target = "Changed"

    serialized = json.loads(bytes(store))
    assert (
        serialized["strings"]["brand"]["localizations"]["fr"]["stringUnit"]["value"]
        == "OneSec"
    )


def test_plural_variations_are_exposed_as_multistring() -> None:
    store = xcstrings.XCStringsFile(fixture("variants.xcstrings"), language_code="fr")
    unit = store.findid("apples")

    assert unit.hasplural()
    assert isinstance(unit.source, multistring)
    assert unit.source.strings == ["%lld apple", "%lld apples"]
    assert unit.target.strings == ["%lld pomme", "%lld pommes"]


def test_device_variants_are_exposed_as_separate_units() -> None:
    store = xcstrings.XCStringsFile(fixture("variants.xcstrings"), language_code="fr")

    mac = store.findid("ordered|device.mac")
    other = store.findid("ordered|device.other")

    assert mac.source == "Products ordered on Mac"
    assert mac.target == "Produits commandes sur Mac"
    assert other.source == "Products ordered"
    assert other.target == "Produits commandes"


def test_substitution_plural_variants_are_exposed() -> None:
    store = xcstrings.XCStringsFile(fixture("variants.xcstrings"), language_code="fr")
    unit = store.findid("birdSightingAlert|substitution.BIRDS")

    assert unit.source.strings == ["no birds", "a bird", "several birds"]
    assert unit.target.strings == ["aucun oiseau", "un oiseau", "plusieurs oiseaux"]


def test_unknown_fields_survive_roundtrip_serialization() -> None:
    store = xcstrings.XCStringsFile(
        fixture("unknown_fields.xcstrings"), language_code="fr"
    )

    serialized = json.loads(bytes(store))

    assert serialized["x-top"] == {"kept": True}
    entry = serialized["strings"]["unknown"]
    assert entry["x-entry"] == {"kept": True}
    assert entry["localizations"]["fr"]["x-localization"] == "target metadata"
    assert entry["localizations"]["fr"]["stringUnit"]["x-string-unit"] == {
        "kept": True
    }


def test_add_language_adds_empty_localizations() -> None:
    store = xcstrings.XCStringsFile(fixture("simple.xcstrings"), language_code="de")

    store.add_language("de")

    serialized = json.loads(bytes(store))
    assert serialized["strings"]["hello"]["localizations"]["de"] == {
        "stringUnit": {"state": "new", "value": ""}
    }
    assert serialized["strings"]["missing"]["localizations"]["de"] == {
        "stringUnit": {"state": "new", "value": ""}
    }
