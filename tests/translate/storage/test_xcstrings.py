import json
from pathlib import Path

from translate.misc.multistring import multistring
from translate.storage import factory, xcstrings
from translate.storage.workflow import StateEnum as states


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
    assert missing.state == xcstrings.XCStringsState.NEW
    assert missing.get_state_n() == states.EMPTY
    assert not missing.istranslated()

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
    assert "de" not in serialized["strings"]["brand"]["localizations"]


def test_add_language_mirrors_variant_localizations() -> None:
    store = xcstrings.XCStringsFile(fixture("variants.xcstrings"), language_code="de")

    store.add_language("de")

    serialized = json.loads(bytes(store))
    german_apples = serialized["strings"]["apples"]["localizations"]["de"]
    assert "stringUnit" not in german_apples
    assert german_apples["variations"]["plural"] == {
        "one": {"stringUnit": {"state": "new", "value": ""}},
        "other": {"stringUnit": {"state": "new", "value": ""}},
    }

    german_birds = serialized["strings"]["birdSightingAlert"]["localizations"]["de"]
    assert german_birds["stringUnit"] == {"state": "new", "value": ""}
    assert german_birds["substitutions"]["BIRDS"]["formatSpecifier"] == "BIRDS"
    assert german_birds["substitutions"]["BIRDS"]["variations"]["plural"] == {
        "zero": {"stringUnit": {"state": "new", "value": ""}},
        "one": {"stringUnit": {"state": "new", "value": ""}},
        "other": {"stringUnit": {"state": "new", "value": ""}},
    }

    german_ordered = serialized["strings"]["ordered"]["localizations"]["de"]
    assert "stringUnit" not in german_ordered
    assert german_ordered["variations"]["device"] == {
        "mac": {"stringUnit": {"state": "new", "value": ""}},
        "other": {"stringUnit": {"state": "new", "value": ""}},
    }

    reparsed = xcstrings.XCStringsFile(bytes(store), language_code="de")
    assert [unit.getid() for unit in reparsed.units] == [
        "apples",
        "birdSightingAlert",
        "birdSightingAlert|substitution.BIRDS",
        "ordered|device.mac",
        "ordered|device.other",
    ]


def test_real_world_variations_fixture_exposes_device_and_plural_units() -> None:
    store = xcstrings.XCStringsFile(
        fixture("real_liamnichols_variations.xcstrings"), language_code="en"
    )

    assert xcstrings.XCStringsFile.list_languages(
        fixture("real_liamnichols_variations.xcstrings")
    ) == ["en"]
    assert [unit.getid() for unit in store.units] == [
        "String.Device|device.mac",
        "String.Device|device.other",
        "String.Plural",
    ]

    mac = store.findid("String.Device|device.mac")
    other = store.findid("String.Device|device.other")
    plural = store.findid("String.Plural")

    assert mac.source == "Click to open"
    assert other.source == "Tap to open"
    assert "macOS variation" in mac.getnotes()
    assert plural.source.strings == [
        "I have no strings",
        "I have %lld string",
        "I have %lld strings",
    ]
    assert plural.target.strings == plural.source.strings


def test_real_world_substitution_fixture_exposes_review_needed_plurals() -> None:
    store = xcstrings.XCStringsFile(
        fixture("real_liamnichols_substitution.xcstrings"), language_code="en"
    )

    assert [unit.getid() for unit in store.units] == [
        "substitutions_example.string",
        "substitutions_example.string|substitution.remaining.strings",
        "substitutions_example.string|substitution.total.strings",
    ]

    total = store.findid("substitutions_example.string|substitution.total.strings")
    remaining = store.findid(
        "substitutions_example.string|substitution.remaining.strings"
    )

    assert total.source.strings == ["is %arg string", "are %arg strings"]
    assert remaining.source.strings == ["%arg"]
    assert total.isfuzzy()
    assert remaining.isfuzzy()
    assert total.get_state_n() == states.NEEDS_REVIEW


def test_real_world_dogtracker_fixture_mutates_only_target_language() -> None:
    store = xcstrings.XCStringsFile(
        fixture("real_liamnichols_dogtracker_localizable.xcstrings"),
        language_code="fr",
    )

    assert xcstrings.XCStringsFile.list_languages(
        fixture("real_liamnichols_dogtracker_localizable.xcstrings")
    ) == ["en", "fr"]

    summary = store.findid("listSummary|substitution.dogCount")
    assert summary.source.strings == ["%arg dog", "%arg dogs"]
    assert summary.target.strings == ["%arg chien", "%arg chiens"]

    store.findid("addTitle").target = "Ajouter un chien"
    serialized = json.loads(bytes(store))
    localizations = serialized["strings"]["addTitle"]["localizations"]

    assert localizations["en"]["stringUnit"]["value"] == "New Dog"
    assert localizations["fr"]["stringUnit"]["value"] == "Ajouter un chien"


def test_real_world_three_language_fixture_preserves_comments_and_readonly() -> None:
    content = fixture("real_mshibanami_manual_comment_3langs.xcstrings")

    assert xcstrings.XCStringsFile.list_languages(content) == ["en", "ja", "zh-Hans"]

    japanese = xcstrings.XCStringsFile(content, language_code="ja")
    chinese = xcstrings.XCStringsFile(content, language_code="zh-Hans")

    ja_close = japanese.findid("closeAction")
    zh_close = chinese.findid("closeAction")
    read_only = japanese.findid("nonTranslatableString")

    assert ja_close.source == "Close"
    assert ja_close.target == "閉じる"
    assert zh_close.target == "关闭"
    assert ja_close.getnotes() == "Button title of closing a dialog, etc."
    assert not read_only.istranslatable()
    assert read_only.source == "nonTranslatableString"


def test_real_world_netnewswire_fixture_supports_version_1_1_device_cases() -> None:
    store = xcstrings.XCStringsFile(
        fixture("real_netnewswire_default_account_names.xcstrings"),
        language_code="en",
    )

    assert xcstrings.XCStringsFile.list_languages(
        fixture("real_netnewswire_default_account_names.xcstrings")
    ) == ["en"]
    assert [unit.getid() for unit in store.units] == [
        "account.name.on-my-device|device.appletv",
        "account.name.on-my-device|device.applevision",
        "account.name.on-my-device|device.applewatch",
        "account.name.on-my-device|device.ipad",
        "account.name.on-my-device|device.iphone",
        "account.name.on-my-device|device.ipod",
        "account.name.on-my-device|device.mac",
        "account.name.on-my-device|device.other",
    ]

    iphone = store.findid("account.name.on-my-device|device.iphone")
    vision = store.findid("account.name.on-my-device|device.applevision")

    assert iphone.source == "On My iPhone"
    assert vision.source == "On My Apple Vision"
    assert (
        iphone.getnotes()
        == "Device specific default account name, e.g: On my iPhone"
    )
    assert json.loads(bytes(store))["version"] == "1.1"


def test_real_world_coteditor_fixture_merges_plural_categories_and_states() -> None:
    content = fixture("real_coteditor_commandbar.xcstrings")

    assert xcstrings.XCStringsFile.list_languages(content) == [
        "bg",
        "cs",
        "de",
        "en",
        "en-GB",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "nl",
        "pl",
        "pt",
        "ru",
        "tr",
        "zh-HK",
        "zh-Hans",
        "zh-Hant",
    ]

    french = xcstrings.XCStringsFile(content, language_code="fr")
    czech = xcstrings.XCStringsFile(content, language_code="cs")

    fr_plural = french.findid("%lld commands found")
    cs_plural = czech.findid("%lld commands found")

    assert fr_plural.source.strings == [
        "No commands found",
        "%lld command found",
        "%lld commands found",
    ]
    assert fr_plural.target.strings == [
        "Aucune commande trouvée",
        "%lld commande trouvée",
        "%lld commandes trouvées",
    ]
    assert fr_plural.isfuzzy()
    assert fr_plural.get_state_n() == states.NEEDS_REVIEW
    assert "incrementally updating" in fr_plural.getnotes()
    assert cs_plural.target.strings == [
        "Nebyly nalezeny žádné příkazy",
        "Nalezen %lld příkaz",
        "Nalezeny %lld příkazy",
        "Nalezeno %lld příkazu",
        "Nalezeno %lld příkazů",
    ]


def test_missing_target_substitution_plural_serializes_clean_template() -> None:
    store = xcstrings.XCStringsFile(
        fixture("real_liamnichols_dogtracker_localizable.xcstrings"),
        language_code="de",
    )
    unit = store.findid("listSummary|substitution.dogCount")

    unit.target = multistring(["%arg Hund", "%arg Hunde"])

    serialized = json.loads(bytes(store))
    substitution = serialized["strings"]["listSummary"]["localizations"]["de"][
        "substitutions"
    ]["dogCount"]

    assert substitution["argNum"] == 1
    assert substitution["formatSpecifier"] == "lld"
    assert "one" not in substitution
    assert "other" not in substitution
    assert substitution["variations"]["plural"]["one"]["stringUnit"] == {
        "state": "translated",
        "value": "%arg Hund",
    }
    assert substitution["variations"]["plural"]["other"]["stringUnit"] == {
        "state": "translated",
        "value": "%arg Hunde",
    }
