"""
identifiers.py -- the identifiers a book's settings give it: a DOI, its
ISBNs, and an address.

Each is checked where it's set, so that a mistyped one is caught there
rather than in a store's or a registry's record: a DOI by its form (10.,
a registrant's code, a slash, and a suffix), given bare or as its
address and kept bare, as an EPUB's identifier typed DOI holds it; an
ISBN by its check digit, ISBN-13's (ISO 2108: weights 1 and 3, mod 10)
or ISBN-10's (weights 10 to 1, mod 11, X for 10), its hyphens and spaces
taken out and an ISBN-10 written as the ISBN-13 it's part of, since an
EPUB types it ISBN-13; and an address as an http or https URL with a
host, no space or control character in it.

Copyright 2026 Robert Szarka

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import re
from urllib.parse import urlsplit

DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.I)
URL_BAD = re.compile(r"[\s\x00-\x1f\x7f-\x9f]")


def doi(value):
    """A DOI bare (10.5281/zenodo.1234567), from it, its address, or
    doi:, or ValueError where it isn't one."""
    found = DOI_RE.match(str(value).strip())
    if not found:
        raise ValueError(f"{value!r} isn't a DOI, which is 10., the registrant's digits, a "
                         "slash, and the rest (10.5281/zenodo.1234567)")
    return found.group(1)


def isbn(value):
    """An ISBN as its 13 digits, from an ISBN-13 or an ISBN-10, hyphens and
    spaces allowed, or ValueError where it isn't one or its check digit is
    wrong."""
    text = re.sub(r"[\s-]", "", str(value).strip()).upper()
    if text.startswith("ISBN"):
        text = text[4:].lstrip(":")
    if re.fullmatch(r"\d{9}[\dX]", text):
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(text))
        if total % 11:
            raise ValueError(f"{value!r} isn't an ISBN: its check digit doesn't match the "
                             "others, so a digit is likely mistyped")
        text = "978" + text[:9]
        text += str((10 - sum((1, 3)[i % 2] * int(c) for i, c in enumerate(text)) % 10) % 10)
        return text
    if not re.fullmatch(r"97[89]\d{10}", text):
        raise ValueError(f"{value!r} isn't an ISBN, which is 13 digits beginning 978 or 979 "
                         "(978-1-234567-89-7), or an older one of 10")
    if sum((1, 3)[i % 2] * int(c) for i, c in enumerate(text)) % 10:
        raise ValueError(f"{value!r} isn't an ISBN: its check digit doesn't match the "
                         "others, so a digit is likely mistyped")
    return text


def url(value):
    """An address, as given, or ValueError where it isn't an http or https
    URL with a host."""
    text = str(value).strip()
    parts = urlsplit(text)
    if URL_BAD.search(text) or parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"{value!r} isn't an address that begins http:// or https:// and "
                         "names a host")
    return text


CHECKS = {"doi": doi, "isbn": isbn, "url": url}
