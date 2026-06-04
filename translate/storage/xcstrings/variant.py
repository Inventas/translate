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

"""String Catalog variant leaf handling."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from translate.misc.multistring import multistring
from translate.storage import base
from translate.storage.xcstrings.state import XCStringsState


JsonDict = dict[str, Any]
PathSegment = tuple[str, ...]
VariantPath = tuple[PathSegment, ...]


class XCStringsVariant:
    """A translatable String Catalog leaf or plural variation group."""

    def __init__(
        self,
        path: VariantPath,
        container: JsonDict,
        *,
        plural_tags: list[str] | None = None,
        root_container: JsonDict | None = None,
    ) -> None:
        self.path = path
        self.container = container
        self.plural_tags = plural_tags
        self._root_container = root_container or container

    @property
    def is_plural(self) -> bool:
        return self.plural_tags is not None

    @property
    def state(self) -> str:
        if self.is_plural:
            return self._plural_state()
        return XCStringsState.from_string_unit(self._string_unit(self.container))

    def get_value(self) -> str | multistring:
        if self.is_plural:
            values = [
                self._string_value(self.container.get(tag, {}))
                for tag in self.plural_tags or []
            ]
            return multistring(values)
        return self._string_value(self.container)

    def write_value(
        self,
        localization: JsonDict,
        value: str | multistring,
        *,
        state: str,
        template: XCStringsVariant | None = None,
    ) -> None:
        if self.is_plural:
            self._write_plural(localization, value, state=state, template=template)
        else:
            container = self._ensure_container(localization, template=template)
            self._write_string_unit(container, str(value or ""), state)

    @staticmethod
    def _string_unit(container: JsonDict) -> JsonDict | None:
        string_unit = container.get("stringUnit")
        return string_unit if isinstance(string_unit, dict) else None

    @classmethod
    def _string_value(cls, container: object) -> str:
        if not isinstance(container, dict):
            return ""
        string_unit = cls._string_unit(container)
        if not isinstance(string_unit, dict):
            return ""
        value = string_unit.get("value")
        return value if isinstance(value, str) else ""

    def _plural_state(self) -> str:
        for tag in self.plural_tags or []:
            variant = self.container.get(tag)
            if not isinstance(variant, dict):
                continue
            state = XCStringsState.from_string_unit(self._string_unit(variant))
            if state == XCStringsState.NEEDS_REVIEW:
                return state
            if state == XCStringsState.TRANSLATED:
                return state
        return XCStringsState.NEW

    def _ensure_container(
        self,
        localization: JsonDict,
        *,
        template: XCStringsVariant | None = None,
    ) -> JsonDict:
        current = localization
        template_current = template.root_container if template is not None else None

        for segment in self.path:
            kind = segment[0]
            if kind == "substitution":
                name = segment[1]
                substitutions = current.setdefault("substitutions", {})
                if not isinstance(substitutions, dict):
                    substitutions = {}
                    current["substitutions"] = substitutions
                substitution_template = self._template_child(
                    template_current, "substitutions", name
                )
                if name not in substitutions or not isinstance(substitutions[name], dict):
                    substitutions[name] = self._substitution_template(
                        name, substitution_template
                    )
                current = substitutions[name]
                template_current = substitution_template
            elif kind == "variation":
                variation_type, case = segment[1], segment[2]
                variations = current.setdefault("variations", {})
                if not isinstance(variations, dict):
                    variations = {}
                    current["variations"] = variations
                cases = variations.setdefault(variation_type, {})
                if not isinstance(cases, dict):
                    cases = {}
                    variations[variation_type] = cases
                if case not in cases or not isinstance(cases[case], dict):
                    cases[case] = {}
                current = cases[case]
                template_current = self._template_child(
                    template_current, "variations", variation_type, case
                )
            elif kind == "plural":
                break
            else:
                raise ValueError(f"Unsupported .xcstrings variant path: {segment}")
        return current

    @property
    def root_container(self) -> JsonDict:
        return self._root_container

    @staticmethod
    def _template_child(
        template: JsonDict | None,
        first_key: str,
        second_key: str,
        third_key: str | None = None,
    ) -> JsonDict | None:
        if not isinstance(template, dict):
            return None
        node = template.get(first_key)
        if not isinstance(node, dict):
            return None
        node = node.get(second_key)
        if not isinstance(node, dict):
            return None
        if third_key is None:
            return node
        node = node.get(third_key)
        return node if isinstance(node, dict) else None

    @staticmethod
    def _substitution_template(name: str, template: JsonDict | None) -> JsonDict:
        if not isinstance(template, dict):
            return {"formatSpecifier": name}
        copied = deepcopy(template)
        copied.pop("stringUnit", None)
        copied.pop("variations", None)
        copied.pop("substitutions", None)
        copied.setdefault("formatSpecifier", name)
        return copied

    def _write_plural(
        self,
        localization: JsonDict,
        value: str | multistring,
        *,
        state: str,
        template: XCStringsVariant | None = None,
    ) -> None:
        parent = self._ensure_container(localization, template=template)
        variations = parent.setdefault("variations", {})
        if not isinstance(variations, dict):
            variations = {}
            parent["variations"] = variations
        plural = variations.setdefault("plural", {})
        if not isinstance(plural, dict):
            plural = {}
            variations["plural"] = plural

        strings = base.TranslationUnit.get_plural_strings(value)
        for index, tag in enumerate(self.plural_tags or []):
            text = strings[index] if index < len(strings) else ""
            case = plural.setdefault(tag, {})
            if not isinstance(case, dict):
                case = {}
                plural[tag] = case
            self._write_string_unit(case, text, state)

    @staticmethod
    def _write_string_unit(container: JsonDict, value: str, state: str) -> None:
        string_unit = container.setdefault("stringUnit", {})
        if not isinstance(string_unit, dict):
            string_unit = {}
            container["stringUnit"] = string_unit
        string_unit["state"] = state
        string_unit["value"] = value
