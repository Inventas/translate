#
# Copyright 2026 Translate Toolkit contributors
#
# This file is part of the Translate Toolkit.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Apple String Catalog file storage."""

from __future__ import annotations

import json
import os
from typing import Any, BinaryIO, TextIO, cast

from translate.lang import data as lang_data
from translate.misc.multistring import multistring
from translate.storage import base
from translate.storage.xcstrings.state import XCStringsState
from translate.storage.xcstrings.unit import XCStringsUnit
from translate.storage.xcstrings.variant import JsonDict, VariantPath, XCStringsVariant


class XCStringsFile(base.TranslationStore[XCStringsUnit]):
    """Apple String Catalog file."""

    UnitClass = XCStringsUnit
    Name = "Apple String Catalog"
    Mimetypes = ["application/x-xcstrings", "application/json"]
    Extensions = ["xcstrings"]

    _ORDER = {
        "sourceLanguage": 0,
        "strings": 1,
        "version": 2,
        "comment": 10,
        "extractionState": 11,
        "shouldTranslate": 12,
        "localizations": 13,
        "stringUnit": 20,
        "variations": 21,
        "substitutions": 22,
        "formatSpecifier": 23,
        "state": 30,
        "value": 31,
        "zero": 40,
        "one": 41,
        "two": 42,
        "few": 43,
        "many": 44,
        "other": 45,
    }

    def __init__(
        self,
        inputfile=None,
        *,
        language_code: str | None = None,
        sourcelanguage: str | None = None,
        targetlanguage: str | None = None,
        unitclass=None,
        encoding=None,
        **kwargs,
    ) -> None:
        super().__init__(unitclass=unitclass, encoding=encoding)
        self.filename = ""
        self._file: JsonDict = {"sourceLanguage": "en", "strings": {}, "version": "1.0"}
        if sourcelanguage is not None:
            self.setsourcelanguage(sourcelanguage)
        if targetlanguage is not None:
            self.settargetlanguage(targetlanguage)
        elif language_code is not None:
            self.settargetlanguage(language_code)
        if inputfile is not None:
            self.parse(inputfile)

    @classmethod
    def list_languages(cls, data: str | bytes | TextIO | BinaryIO) -> list[str]:
        """Return all localization language codes present in a catalog."""
        parsed = cls._load_json(data)
        languages: set[str] = set()

        source_language = parsed.get("sourceLanguage")
        if isinstance(source_language, str):
            languages.add(source_language)

        strings = parsed.get("strings", {})
        if not isinstance(strings, dict):
            return sorted(languages)

        for entry in strings.values():
            if not isinstance(entry, dict):
                continue
            localizations = entry.get("localizations", {})
            if isinstance(localizations, dict):
                languages.update(str(language) for language in localizations)

        return sorted(languages)

    def parse(self, data: str | bytes | TextIO | BinaryIO) -> None:
        """Parse a String Catalog JSON file."""
        if hasattr(data, "name"):
            self.filename = cast("Any", data).name
        elif isinstance(data, (str, os.PathLike)):
            filename = os.fspath(data)
            if isinstance(filename, bytes):
                filename = filename.decode("utf-8-sig")
            if not self._looks_like_inline_json(filename):
                self.filename = filename
        self.units = []
        self.locationindex = {}
        self.sourceindex = {}
        self.id_index = {}

        parsed = self._load_json(data)
        strings = parsed.setdefault("strings", {})
        if not isinstance(strings, dict):
            raise base.ParseError(ValueError(".xcstrings 'strings' must be an object."))

        self._file = parsed
        source_language = parsed.get("sourceLanguage")
        if isinstance(source_language, str):
            self.setsourcelanguage(source_language)
        elif self.getsourcelanguage() is None:
            self.setsourcelanguage("en")

        if self.gettargetlanguage() is None:
            self.settargetlanguage(self.getsourcelanguage())

        self._extract_units()

    def serialize(self, out) -> None:
        target_language = self.gettargetlanguage() or self.getsourcelanguage() or "en"
        strings = self._file.setdefault("strings", {})
        if not isinstance(strings, dict):
            strings = {}
            self._file["strings"] = strings

        if self.getsourcelanguage():
            self._file["sourceLanguage"] = self.getsourcelanguage()
        self._file.setdefault("version", "1.0")

        for unit in self.units:
            if not unit.should_translate or not unit.needs_serialization():
                continue
            entry = strings.setdefault(unit.key, {})
            if not isinstance(entry, dict):
                entry = {}
                strings[unit.key] = entry
            localizations = entry.setdefault("localizations", {})
            if not isinstance(localizations, dict):
                localizations = {}
                entry["localizations"] = localizations
            localization = localizations.setdefault(target_language, {})
            if not isinstance(localization, dict):
                localization = {}
                localizations[target_language] = localization
            unit.apply_to_localization(localization)

        normalized = self._ordered(self._file)
        out.write(
            json.dumps(normalized, ensure_ascii=False, indent=2).encode(self.encoding)
        )
        out.write(b"\n")

    def add_language(self, language_code: str) -> None:
        """Add an empty localization entry for every catalog string."""
        source_language = self.getsourcelanguage() or self._file.get("sourceLanguage")
        if not isinstance(source_language, str):
            source_language = "en"

        strings = self._file.setdefault("strings", {})
        if not isinstance(strings, dict):
            strings = {}
            self._file["strings"] = strings

        for entry in strings.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("shouldTranslate") is False:
                continue
            localizations = entry.setdefault("localizations", {})
            if not isinstance(localizations, dict):
                localizations = {}
                entry["localizations"] = localizations
            if language_code in localizations:
                continue
            source_localization = localizations.get(source_language, {})
            localizations[language_code] = self._empty_localization_from_source(
                source_localization if isinstance(source_localization, dict) else {}
            )

    @classmethod
    def _empty_localization_from_source(cls, source_localization: JsonDict) -> JsonDict:
        source_variants = cls._collect_variants(source_localization)
        if not source_variants:
            return {"stringUnit": {"state": XCStringsState.NEW, "value": ""}}

        localization: JsonDict = {}
        for path, source_variant in sorted(
            source_variants.items(), key=lambda item: cls._path_sort_key(item[0])
        ):
            empty_variant = XCStringsVariant(
                path,
                {},
                plural_tags=(
                    source_variant.plural_tags if source_variant.is_plural else None
                ),
            )
            if source_variant.is_plural:
                empty_variant.write_value(
                    localization,
                    multistring([""] * len(source_variant.plural_tags or [])),
                    state=XCStringsState.NEW,
                    template=source_variant,
                )
            else:
                empty_variant.write_value(
                    localization, "", state=XCStringsState.NEW, template=source_variant
                )
        return localization

    @classmethod
    def _load_json(cls, data: str | bytes | TextIO | BinaryIO) -> JsonDict:
        text: str | bytes
        if hasattr(data, "read"):
            text = cast("BinaryIO", data).read()
        elif isinstance(data, os.PathLike):
            with open(os.fspath(data), "rb") as handle:
                text = handle.read()
        else:
            text = data

        if isinstance(text, str) and not cls._looks_like_inline_json(text):
            with open(text, "rb") as handle:
                text = handle.read()

        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise base.ParseError(error) from error

        try:
            parsed = json.loads(text)
        except ValueError as error:
            raise base.ParseError(error) from error

        if not isinstance(parsed, dict):
            raise base.ParseError(ValueError(".xcstrings root must be a JSON object."))
        return parsed

    @staticmethod
    def _looks_like_inline_json(text: str) -> bool:
        return text.lstrip("\ufeff \t\r\n").startswith("{")

    def _extract_units(self) -> None:
        source_language = self.getsourcelanguage() or "en"
        target_language = self.gettargetlanguage() or source_language
        strings = self._file.get("strings", {})
        if not isinstance(strings, dict):
            return

        for key in sorted(strings):
            entry = strings[key]
            if not isinstance(entry, dict):
                continue
            localizations = entry.get("localizations", {})
            if not isinstance(localizations, dict):
                localizations = {}

            source_localization = localizations.get(source_language)
            if not isinstance(source_localization, dict):
                source_localization = {}
            target_localization = localizations.get(target_language)
            if not isinstance(target_localization, dict):
                target_localization = {}

            source_variants = self._collect_variants(source_localization)
            target_variants = self._collect_variants(target_localization)
            paths = sorted(
                set(source_variants) | set(target_variants),
                key=self._path_sort_key,
            )
            if not paths:
                paths = [()]

            for path in paths:
                source_variant = source_variants.get(path)
                target_variant = target_variants.get(path)
                is_plural = self._path_is_plural(path, source_variant, target_variant)
                plural_tags = self._plural_tags(source_variant, target_variant)

                source = self._source_value(key, source_variant, is_plural, plural_tags)
                target = self._target_value(target_variant, is_plural, plural_tags)
                unit = self.UnitClass(
                    source,
                    target=target,
                    key=key,
                    unit_id=self._unit_id(key, path),
                    notes=self._notes(entry),
                    should_translate=entry.get("shouldTranslate", True) is not False,
                    source_variant=source_variant,
                    target_variant=target_variant,
                    plural_tags=plural_tags if is_plural else None,
                    state=target_variant.state
                    if target_variant is not None
                    else XCStringsState.NEW,
                )
                self.addunit(unit)

    @classmethod
    def _collect_variants(
        cls,
        container: JsonDict,
        path: VariantPath = (),
        root_container: JsonDict | None = None,
    ) -> dict[VariantPath, XCStringsVariant]:
        if root_container is None:
            root_container = container
        variants: dict[VariantPath, XCStringsVariant] = {}

        if isinstance(container.get("stringUnit"), dict):
            variants[path] = XCStringsVariant(
                path, container, root_container=root_container
            )

        substitutions = container.get("substitutions", {})
        if isinstance(substitutions, dict):
            for name, substitution in substitutions.items():
                if isinstance(substitution, dict):
                    variants.update(
                        cls._collect_variants(
                            substitution,
                            (*path, ("substitution", str(name))),
                            root_container,
                        )
                    )

        variation_groups = container.get("variations", {})
        if not isinstance(variation_groups, dict):
            return variants

        for variation_type, cases in variation_groups.items():
            if not isinstance(cases, dict):
                continue
            variation_type = str(variation_type)
            if variation_type == "plural":
                plural_path = (*path, ("plural",))
                plural_tags = cls._sorted_plural_tags(cases.keys())
                variants[plural_path] = XCStringsVariant(
                    plural_path,
                    cases,
                    plural_tags=plural_tags,
                    root_container=root_container,
                )
                continue
            for case, case_container in cases.items():
                if isinstance(case_container, dict):
                    variants.update(
                        cls._collect_variants(
                            case_container,
                            (*path, ("variation", variation_type, str(case))),
                            root_container,
                        )
                    )
        return variants

    @classmethod
    def _sorted_plural_tags(cls, tags) -> list[str]:
        tag_strings = [str(tag) for tag in tags]
        known = [tag for tag in lang_data.cldr_plural_categories if tag in tag_strings]
        unknown = sorted(tag for tag in tag_strings if tag not in known)
        return [*known, *unknown]

    @staticmethod
    def _path_is_plural(
        path: VariantPath,
        source_variant: XCStringsVariant | None,
        target_variant: XCStringsVariant | None,
    ) -> bool:
        return (
            any(segment[0] == "plural" for segment in path)
            or bool(source_variant and source_variant.is_plural)
            or bool(target_variant and target_variant.is_plural)
        )

    @classmethod
    def _plural_tags(
        cls,
        source_variant: XCStringsVariant | None,
        target_variant: XCStringsVariant | None,
    ) -> list[str]:
        tags: list[str] = []
        for variant in (source_variant, target_variant):
            if variant is None or not variant.plural_tags:
                continue
            for tag in variant.plural_tags:
                if tag not in tags:
                    tags.append(tag)
        return cls._sorted_plural_tags(tags)

    @staticmethod
    def _source_value(
        key: str,
        source_variant: XCStringsVariant | None,
        is_plural: bool,
        plural_tags: list[str],
    ) -> str | multistring:
        if source_variant is not None:
            return source_variant.get_value()
        if is_plural:
            return multistring([""] * len(plural_tags))
        return key

    @staticmethod
    def _target_value(
        target_variant: XCStringsVariant | None,
        is_plural: bool,
        plural_tags: list[str],
    ) -> str | multistring:
        if target_variant is not None:
            return target_variant.get_value()
        if is_plural:
            return multistring([""] * len(plural_tags))
        return ""

    @staticmethod
    def _notes(entry: JsonDict) -> str:
        comment = entry.get("comment")
        return comment if isinstance(comment, str) else ""

    @classmethod
    def _unit_id(cls, key: str, path: VariantPath) -> str:
        if not path or path == (("plural",),):
            return key

        parts = []
        for segment in path:
            kind = segment[0]
            if kind == "substitution":
                parts.append(f"substitution.{segment[1]}")
            elif kind == "variation":
                parts.append(f"{segment[1]}.{segment[2]}")
            elif kind == "plural":
                continue
        return f"{key}|{'|'.join(parts)}" if parts else key

    @classmethod
    def _path_sort_key(cls, path: VariantPath):
        return cls._unit_id("", path)

    @classmethod
    def _ordered(cls, value):
        if isinstance(value, dict):
            return {
                key: cls._ordered(value[key])
                for key in sorted(
                    value,
                    key=lambda key: (cls._ORDER.get(str(key), 1000), str(key)),
                )
            }
        if isinstance(value, list):
            return [cls._ordered(item) for item in value]
        return value
