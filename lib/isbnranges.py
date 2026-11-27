"""
isbnranges.py -- where an ISBN's hyphens go, by the International ISBN
Agency's range message, and the check of the hyphens a setting gives.

An ISBN's parts are of no fixed length: the registration group's and
the registrant's lengths depend on the digits, by ranges the agency
assigns and publishes as a range message (an XML file). The agency
doesn't allow its pages to be republished without its written
permission, and allows the message to be fetched by an HTTP GET, so the
message isn't kept in the repository: it's fetched, by
util/fetch-isbn-ranges.py or by a run that needs it, into
~/.cache/textbookimprover/isbn/RangeMessage.xml (under XDG_CACHE_HOME
where that's set).

A run needs it where a setting writes an ISBN with hyphens or spaces
(identifiers.isbn_parts). With none there, it's fetched; with one there
that doesn't define a range one of the ISBNs is in, it's fetched again
where it's more than a day old, since the agency adds ranges as it
assigns them. A fetch that fails leaves the copy there as it was.
TEXTBOOKIMPROVER_ISBN_RANGES set to a file's path makes that file the
message, and nothing is fetched; set to off, nothing is checked or
fetched.

A fetch is of the agency's own address alone, over https, refusing a
redirect away from https, no more than 16 MB, waiting no more than 20
seconds for each answer and two minutes in all, and kept only when it
reads as a range message. The message is read with no entity declared in it: the
agency's declares its elements alone, and one declaring an entity is
refused, as one that could make the reading take the memory.

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

import http.client
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from xml.parsers import expat

import identifiers

URL = "https://www.isbn-international.org/export_rangemessage.xml"
VARIABLE = "TEXTBOOKIMPROVER_ISBN_RANGES"
LIMIT = 16 * 1024 * 1024
TIMEOUT = 20
# All told, a fetch takes no more than this.
DEADLINE = 120
# A copy older than this is fetched again when it doesn't define a range
# an ISBN is in.
STALE = 24 * 60 * 60
# What a fetch can fail with, as lib/cnx/exercises.py says.
FETCH_ERRORS = (urllib.error.URLError, OSError, ValueError, http.client.HTTPException)
RANGE_RE = re.compile(r"^(\d{7})-(\d{7})$")
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _plain(text, most=120):
    """Text from the message or the network as a line may say it: no
    control character, and no longer than most."""
    text = CONTROL.sub("?", str(text))
    return text if len(text) <= most else text[:most] + "…"


def default_path():
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache")
    return os.path.join(cache, "textbookimprover", "isbn", "RangeMessage.xml")


class Ranges:
    """A range message read: the registration groups' lengths under each
    prefix (978, 979), and the registrants' under each group (978-0), each
    a list of (first, last, length), its first and last seven digits."""

    def __init__(self, groups, registrants, date, serial):
        self.groups = groups
        self.registrants = registrants
        self.date = date
        self.serial = serial

    @staticmethod
    def _length(rules, digits):
        key = int(digits[:7].ljust(7, "0"))
        for first, last, length in rules or ():
            if first <= key <= last:
                return length
        return 0

    def split(self, digits):
        """An ISBN's 13 digits as its five parts (prefix, registration
        group, registrant, publication, check digit), or None where the
        message doesn't define a range they're in."""
        prefix, rest = digits[:3], digits[3:12]
        length = self._length(self.groups.get(prefix), rest)
        if not length or length >= len(rest):
            return None
        group, rest = rest[:length], rest[length:]
        length = self._length(self.registrants.get(f"{prefix}-{group}"), rest)
        if not length or length >= len(rest):
            return None
        return [prefix, group, rest[:length], rest[length:], digits[12]]


def _refuse(*args):
    raise ValueError("it declares an entity, which a range message doesn't")


def _tree(data):
    """The XML's root element, read by expat with no entity declared, or
    ValueError."""
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate()
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.EntityDeclHandler = _refuse
    parser.UnparsedEntityDeclHandler = _refuse
    parser.ExternalEntityRefHandler = _refuse
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise ValueError(f"it isn't XML ({exc})") from None
    return builder.close()


def _rules(element, where):
    rules = []
    for rule in element.findall("./Rules/Rule"):
        found = RANGE_RE.match((rule.findtext("Range") or "").strip())
        length = (rule.findtext("Length") or "").strip()
        if not found or not re.fullmatch(r"[0-7]", length):
            raise ValueError(f"a rule of {_plain(where, 40)} isn't a range of seven digits and "
                             "a length")
        rules.append((int(found.group(1)), int(found.group(2)), int(length)))
    return rules


def parse(data):
    """The range message's bytes as Ranges, or ValueError where they
    aren't one."""
    if len(data) > LIMIT:
        raise ValueError(f"it's over {LIMIT // (1024 * 1024)} MB")
    root = _tree(data)
    if root.tag != "ISBNRangeMessage":
        raise ValueError(f"its root is {_plain(root.tag, 40)}, not ISBNRangeMessage")
    groups, registrants = {}, {}
    for element in root.findall("./EAN.UCCPrefixes/EAN.UCC"):
        prefix = (element.findtext("Prefix") or "").strip()
        if not re.fullmatch(r"97[89]", prefix):
            raise ValueError(f"a prefix is {_plain(prefix, 40)!r}, not 978 or 979")
        groups[prefix] = _rules(element, prefix)
    for element in root.findall("./RegistrationGroups/Group"):
        prefix = (element.findtext("Prefix") or "").strip()
        if not re.fullmatch(r"97[89]-\d{1,5}", prefix):
            raise ValueError(f"a group's prefix is {_plain(prefix, 40)!r}")
        registrants[prefix] = _rules(element, prefix)
    if not groups or not registrants:
        raise ValueError("it has no prefixes or no registration groups")
    return Ranges(groups, registrants,
                  _plain((root.findtext("MessageDate") or "").strip(), 60),
                  _plain((root.findtext("MessageSerialNumber") or "").strip(), 60))


def load(path):
    """The range message in a file, or ValueError or OSError."""
    with open(path, "rb") as handle:
        data = handle.read(LIMIT + 1)
    return parse(data)


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(req.full_url).scheme == "https" and urlsplit(newurl).scheme != "https":
            raise ValueError(f"the agency's address redirects to {_plain(newurl)}, which "
                             "isn't https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(path, url=URL, timeout=TIMEOUT):
    """Fetch the range message into path, replacing what's there only when
    it reads as one, and return it as Ranges; or one of FETCH_ERRORS."""
    opener = urllib.request.build_opener(_HttpsOnly)
    request = urllib.request.Request(url, headers={
        "User-Agent": "TextbookImprover (https://github.com/OERforge/textbookimprover)",
        "Accept": "application/xml, text/xml"})
    began, chunks, size = time.monotonic(), [], 0
    with opener.open(request, timeout=timeout) as reply:
        while size <= LIMIT:
            chunk = reply.read(64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if time.monotonic() - began > DEADLINE:
                raise ValueError(f"it took more than {DEADLINE} seconds")
    data = b"".join(chunks)
    ranges = parse(data)
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    # Beside it, a name of this process's alone, made new, not through a
    # link; then moved into its place.
    tmp = os.path.join(folder, f".{os.path.basename(path)}.{os.getpid()}.part")
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return ranges


def reason(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return _plain(f"the agency answered {exc.code} {exc.reason}")
    if isinstance(exc, urllib.error.URLError):
        return _plain(f"it couldn't be reached: {exc.reason}")
    if isinstance(exc, OSError) and exc.strerror:
        return _plain(exc.strerror)
    return _plain(str(exc) or type(exc).__name__)


def hyphenated(settings):
    """[(setting, value, its 13 digits, its parts as an ISBN-13's first
    four)] for each setting that writes an ISBN with hyphens or spaces and
    passes identifiers.isbn(); a value that doesn't is the settings
    check's to report."""
    found = []
    for name, value in settings:
        if not isinstance(value, str):
            continue
        parts = identifiers.isbn_parts(value)
        if parts is None:
            continue
        try:
            digits = identifiers.isbn(value)
        except ValueError:
            continue
        written = ["978"] + parts[:3] if len(parts) == 4 else parts[:4]
        found.append((name, value, digits, written))
    return found


def check(settings, variable=None, path=None, fetcher=fetch, now=time.time):
    """The settings' hyphens against the range message, as
    (errors, warnings): an error for an ISBN whose hyphens aren't where
    the message puts them, saying where they go; a warning for one in a
    range the message doesn't define, and for a message that couldn't be
    had. settings is [(setting's name, its value as written)]."""
    found = hyphenated(settings)
    variable = os.environ.get(VARIABLE, "") if variable is None else variable
    if not found or variable.strip().lower() == "off":
        return [], []
    errors, warnings = [], []
    names = ", ".join(name for name, *_ in found)
    if variable.strip():
        try:
            ranges = load(variable)
        except (OSError, ValueError) as exc:
            return [], [f"{VARIABLE} names {variable}, which can't be read as the "
                        f"International ISBN Agency's range message ({reason(exc)}), so the "
                        f"hyphens of {names} weren't checked."]
    else:
        path = path or default_path()
        ranges = None
        if os.path.isfile(path):
            try:
                ranges = load(path)
            except (OSError, ValueError):
                ranges = None
        stale = ranges is not None and any(ranges.split(d) is None for _, _, d, _ in found) \
            and now() - os.path.getmtime(path) > STALE
        if ranges is None or stale:
            try:
                ranges = fetcher(path)
            except FETCH_ERRORS as exc:
                if ranges is None:
                    return [], [f"the hyphens of {names} weren't checked: the International "
                                f"ISBN Agency's range message couldn't be fetched from {URL} "
                                f"({reason(exc)}). util/fetch-isbn-ranges.py fetches it, and "
                                f"{VARIABLE} can name a copy of it."]
    when = f" of {ranges.date}" if ranges.date else ""
    for name, value, digits, written in found:
        parts = ranges.split(digits)
        if parts is None:
            warnings.append(f"{name} is {value!r}, which isn't in a range the International "
                            f"ISBN Agency's range message{when} defines, so its hyphens "
                            "weren't checked: a digit may be mistyped, or the range may be "
                            "newer than the message.")
        elif parts[:4] != written:
            given = identifiers.isbn_parts(value)
            right = "-".join(parts[1:4] + [given[-1].upper()] if len(given) == 4 else parts)
            errors.append(f"{name} is {value!r}, whose hyphens aren't where the International "
                          f"ISBN Agency's ranges{when} put them: {right}. Write it so, or "
                          "without hyphens.")
    return errors, warnings
