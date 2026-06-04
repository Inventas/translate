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

"""String Catalog translation unit."""

from __future__ import annotations

from translate.misc.multistring import multistring
from translate.storage import base
from translate.storage.xcstrings.state import XCStringsState
from translate.storage.xcstrings.variant import JsonDict, XCStringsVariant


class XCStringsUnit(base.TranslationUnit):
    """A single translation unit exposed from a String Catalog."""

    def __init__(
        self,
        source=None,
        *,
        target=None,
        key: str | None = None,
        unit_id: str | None = None,
        notes: str = "",
        should_translate: bool = True,
        source_variant: XCStringsVariant | None = None,
        target_variant: XCStringsVariant | None = None,
        plural_tags: list[str] | None = None,
        state: str | None = None,
    ) -> None:
        self.key = key or unit_id or str(source or "")
        self._id = unit_id or self.key
        self.should_translate = should_translate
        self.source_variant = source_variant
        self.target_variant = target_variant
        self.plural_tags = plural_tags or []
        self.state = state or XCStringsState.NEW
        self._target_dirty = False
        self._state_dirty = False
        self._initializing = True
        super().__init__(source)
        self.target = target
        if notes:
            self.notes = notes
        self._initializing = False
        self._target_dirty = False

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, target) -> None:
        self._rich_target = None
        if getattr(self, "_initializing", False):
            self._target = target
            return
        changed = getattr(self, "_target", None) != target
        self._target = target
        if changed and not getattr(self, "_initializing", False):
            self._target_dirty = True

    def getid(self) -> str:
        return self._id

    def setid(self, value) -> None:
        self._id = value
        self.key = value.split("|", 1)[0]

    def getlocations(self) -> list[str]:
        return [self.getid()]

    def hasplural(self) -> bool:
        return bool(self.plural_tags) or isinstance(self.source, multistring)

    def istranslatable(self) -> bool:
        return self.should_translate and super().istranslatable()

    def isfuzzy(self) -> bool:
        return self.state == XCStringsState.NEEDS_REVIEW

    def markfuzzy(self, value=True) -> None:
        self.state = XCStringsState.NEEDS_REVIEW if value else self._clean_state()
        self._state_dirty = True

    def markreviewneeded(self, needsreview=True, explanation=None) -> None:
        self.markfuzzy(needsreview)
        if explanation:
            self.addnote(explanation)

    def istranslated(self):
        return self._has_target_value() and not self.isfuzzy()

    def get_state_n(self):
        return XCStringsState.to_base(self.state, self.target)

    def set_state_n(self, value) -> None:
        self.state = XCStringsState.from_base(value, self.target)
        self._state_dirty = True

    def infer_state(self) -> None:
        self.state = self._clean_state()

    def _clean_state(self) -> str:
        return XCStringsState.TRANSLATED if self._has_target_value() else XCStringsState.NEW

    def _has_target_value(self) -> bool:
        if isinstance(self.target, multistring):
            return any(bool(string) for string in self.target.strings)
        return bool(self.target)

    def _state_for_serialization(self) -> str:
        if self.state == XCStringsState.NEEDS_REVIEW:
            return self.state
        if self._target_dirty and self.state == XCStringsState.NEW and self._has_target_value():
            return XCStringsState.TRANSLATED
        return self.state or self._clean_state()

    def needs_serialization(self) -> bool:
        return self._target_dirty or self._state_dirty

    def apply_to_localization(self, localization: JsonDict) -> None:
        if not self.should_translate or not self.needs_serialization():
            return

        variant = self.target_variant
        if variant is None:
            variant = XCStringsVariant(
                self.source_variant.path if self.source_variant else (),
                {},
                plural_tags=self.plural_tags or None,
            )
            self.target_variant = variant

        variant.write_value(
            localization,
            self.target if self.target is not None else "",
            state=self._state_for_serialization(),
            template=self.source_variant,
        )
        self._target_dirty = False
        self._state_dirty = False
