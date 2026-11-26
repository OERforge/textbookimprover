"""
identifiers.py -- the identifiers a book's settings give it: a DOI, its
ISBNs, an address, and a contact; and the period a book covers.

Each is checked where it's set, so that a mistyped one is caught there
rather than in a store's or a registry's record: a DOI by its form (10.,
a registrant's code, a slash, and a suffix), given bare or as its
address and kept bare, as an EPUB's identifier typed DOI holds it; an
ISBN by its check digit, ISBN-13's (ISO 2108: weights 1 and 3, mod 10)
or ISBN-10's (weights 10 to 1, mod 11, X for 10), its hyphens and spaces
taken out and an ISBN-10 written as the ISBN-13 it's part of, since an
EPUB types it ISBN-13; an address as an http or https URL with a host,
no space or control character in it; a contact as an email address
or such an address; and a period, words or an ISO 8601 interval of two
dates (1865/1900), the second not before the first.

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


def isbn_parts(value):
    """The parts an ISBN's hyphens or spaces set apart, as written, or None
    where it's written without them."""
    text = re.sub(r"^ISBN:?\s*", "", str(value).strip(), flags=re.I)
    parts = [p for p in re.split(r"[\s-]+", text) if p]
    return parts if len(parts) > 1 else None


def isbn(value):
    """An ISBN as its 13 digits, from an ISBN-13 or an ISBN-10, or
    ValueError where it isn't one or its check digit is wrong. It may be
    written without hyphens, or with hyphens or spaces between its
    parts: an ISBN-13's five (978-0-306-40615-7, the prefix of three
    digits, the registration group, the registrant, the publication, and
    the check digit) or an ISBN-10's four; other hyphens are refused,
    since they'd be shown as given (isbn_shown)."""
    parts = isbn_parts(value)
    if parts is not None and not (
            all(re.fullmatch(r"\d+", p) for p in parts[:-1])
            and len(parts[-1]) == 1
            and (len(parts) == 5 and len(parts[0]) == 3 and 1 <= len(parts[1]) <= 5
                 or len(parts) == 4 and 1 <= len(parts[0]) <= 5)):
        raise ValueError(f"{value!r} has its hyphens elsewhere than between an ISBN's "
                         "parts: an ISBN-13's five (978-0-306-40615-7), as its agency "
                         "gives them, or an ISBN-10's four; or write it without them")
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


def isbn_shown(value):
    """An ISBN as a reader is shown it: its 13 digits, hyphenated where
    the setting hyphenates it, an ISBN-10's parts after 978 and with its
    ISBN-13's check digit; or ValueError, as isbn() gives."""
    digits = isbn(value)
    parts = isbn_parts(value)
    if parts is None:
        return digits
    if len(parts) == 4:
        parts = ["978"] + parts[:3] + [digits[-1]]
    return "-".join(parts)


def url(value):
    """An address, as given, or ValueError where it isn't an http or https
    URL with a host."""
    text = str(value).strip()
    parts = urlsplit(text)
    if URL_BAD.search(text) or parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"{value!r} isn't an address that begins http:// or https:// and "
                         "names a host")
    return text


# An email address as a person writes one: a local part and a domain with
# a dot, nothing that would end it in a record (a space, a quote, an angle
# bracket, a control character), and mailto: before it taken off.
EMAIL_RE = re.compile(r"^(?:mailto:)?([^@\s<>\"'(),;:\\\[\]\x00-\x1f\x7f]+"
                      r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+)$", re.I)


def contact(value):
    """Where to write about the book, an email address (mailto: before it
    taken off) or an http or https URL, or ValueError where it's neither."""
    text = str(value).strip()
    found = EMAIL_RE.match(text)
    if found:
        return found.group(1)
    try:
        return url(text)
    except ValueError:
        raise ValueError(f"{value!r} isn't an email address (corrections@example.edu) or an "
                         "address that begins http:// or https:// and names a host") from None


# A date as an interval's end may give it: a year, a month, or a day.
ISO_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def _date_bounds(text):
    """The first and last days a date of a year, a month, or a day spans,
    or None where it isn't one."""
    import calendar
    import datetime
    found = ISO_DATE.match(text)
    if not found:
        return None
    year = int(found.group(1))
    month = int(found.group(2)) if found.group(2) else None
    day = int(found.group(3)) if found.group(3) else None
    try:
        if month is None:
            return datetime.date(year, 1, 1), datetime.date(year, 12, 31)
        if day is None:
            last = calendar.monthrange(year, month)[1]
            return datetime.date(year, month, 1), datetime.date(year, month, last)
        when = datetime.date(year, month, day)
        return when, when
    except ValueError:
        return None


def period(value):
    """A period as a setting gives it: words (the twentieth century), kept
    as they are, or an ISO 8601 interval of two dates, each a year, a
    month, or a day (1865/1900, 1929-10/1939-09-01), checked, or
    ValueError where it reads as an interval and isn't one."""
    text = " ".join(str(value).split())
    if text.count("/") == 1:
        start, end = (part.strip() for part in text.split("/"))
        if start[:1].isdigit() or end[:1].isdigit():
            first, last = _date_bounds(start), _date_bounds(end)
            if first is None or last is None:
                raise ValueError(f"{value!r} isn't an interval of two dates, each a year, a "
                                 "month, or a day (1865/1900, 1929-10/1939-09-01); write "
                                 "a period in words without a slash")
            if last[1] < first[0]:
                raise ValueError(f"{value!r} ends before it begins")
            return f"{start}/{end}"
    return text


# A setting is kept as a reader is shown it: an ISBN hyphenated where it
# was written so, which isbn() makes 13 digits for a record.
CHECKS = {"doi": doi, "isbn": isbn_shown, "url": url, "contact": contact, "period": period}
