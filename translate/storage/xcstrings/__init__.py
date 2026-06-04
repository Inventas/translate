"""Storage support for Apple String Catalog ``.xcstrings`` files."""

from translate.storage.xcstrings.file import XCStringsFile
from translate.storage.xcstrings.state import XCStringsState
from translate.storage.xcstrings.unit import XCStringsUnit
from translate.storage.xcstrings.variant import XCStringsVariant


def XCStrings(inputfile=None, **kwargs):
    """Helper function to create :class:`XCStringsFile` instances."""
    return XCStringsFile(inputfile, **kwargs)


__all__ = [
    "XCStrings",
    "XCStringsFile",
    "XCStringsState",
    "XCStringsUnit",
    "XCStringsVariant",
]
