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

"""Xcode String Catalog state mapping."""

from __future__ import annotations

from typing import Any

from translate.storage.workflow import StateEnum as states


class XCStringsState:
    """Xcode string-unit state mapping."""

    NEW = "new"
    TRANSLATED = "translated"
    NEEDS_REVIEW = "needs_review"

    TO_BASE = {
        NEW: states.EMPTY,
        TRANSLATED: states.FINAL,
        NEEDS_REVIEW: states.NEEDS_REVIEW,
    }
    FROM_BASE = {
        states.EMPTY: NEW,
        states.NEEDS_WORK: NEEDS_REVIEW,
        states.REJECTED: NEEDS_REVIEW,
        states.NEEDS_REVIEW: NEEDS_REVIEW,
        states.UNREVIEWED: TRANSLATED,
        states.FINAL: TRANSLATED,
    }

    @classmethod
    def from_string_unit(cls, string_unit: dict[str, Any] | None) -> str:
        if not isinstance(string_unit, dict):
            return cls.NEW
        state = string_unit.get("state")
        if isinstance(state, str):
            return state
        return cls.NEW

    @classmethod
    def to_base(cls, state: str | None, value: object = None) -> states:
        if state in cls.TO_BASE:
            return cls.TO_BASE[state]
        return states.UNREVIEWED if value else states.EMPTY

    @classmethod
    def from_base(cls, state_value: states, value: object = None) -> str:
        if not value and state_value <= states.EMPTY:
            return cls.NEW
        return cls.FROM_BASE.get(state_value, cls.TRANSLATED if value else cls.NEW)
