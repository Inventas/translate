.. _xcstrings:

Apple String Catalog files
**************************

Apple String Catalog (``.xcstrings``) files are JSON-based localization files
used by Xcode for strings, plurals, device variations, and substitutions.

The Translate Toolkit supports ``.xcstrings`` files via
``translate.storage.xcstrings``.  The storage exposes translation units for one
target language at a time, selected with the existing target language setting or
the ``language_code`` argument when a caller provides it.

The implementation preserves unknown JSON fields and writes deterministic JSON
output.  It supports simple string units, comments, ``shouldTranslate`` entries
as non-translatable units, plural variations, device variations, and plural
substitution variants.

``XCStringsFile.list_languages()`` can be used to inspect the source language
and all localization language codes in a catalog without constructing
translation units for a specific target language.

.. seealso::

   :doc:`strings`
      Apple's legacy key-value strings format.

   :doc:`stringsdict`
      Apple's plist-based plural format.

.. _xcstrings#references:

References
==========

* `Localizing and varying text with a string catalog
  <https://developer.apple.com/documentation/xcode/localizing-and-varying-text-with-a-string-catalog>`_
