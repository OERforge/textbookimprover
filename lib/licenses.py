"""
licenses.py -- what a book's license and copyright line say, for the
outputs that record them.

project.license is the license's SPDX identifier where it has one and
otherwise its name; project.copyright the line as it should read, or its
parts, a holder, a year (the year of project.published where it's not
given), and words of the author's own after them, from which the line is
"Copyright 2026 Robert Szarka." and then the words. The
Creative Commons licenses and CC0, the ones open textbooks use, are known
here by name and deed; another license is given as it's written, with no
address, since an identifier that only looks like SPDX's would be given
a page at spdx.org that isn't there.

project.licenses, or a part's own, gives some of the pages a license of
their own, entry by entry (check_entry): the pages by name or pattern,
and either the work they're adapted from in its parts (its title,
author, source, and license, the TASL a reuser is asked to give, with
the changes made) or a statement in the author's own words. From the
parts a run writes one sentence in a fixed form at the end of the set's
last page, or of each page (tasl_sentence); a page's license is its
entries' and otherwise the part's (page_licenses), and the book's rights
say "except where otherwise noted" when any page's differs (exceptions).

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

import fnmatch
import re

# A Creative Commons license's SPDX identifier: its elements, its version,
# and, for 3.0 and earlier, a port's jurisdiction, which SPDX writes after.
CC = re.compile(r"^CC-(BY(?:-NC)?(?:-ND|-SA)?)-(?:(1\.0|2\.0|2\.5|3\.0)(?:-([A-Z]{2,3}))?"
                r"|(4\.0))$", re.I)
CC_NAMES = {"BY": "Attribution", "BY-SA": "Attribution-ShareAlike",
            "BY-ND": "Attribution-NoDerivatives", "BY-NC": "Attribution-NonCommercial",
            "BY-NC-SA": "Attribution-NonCommercial-ShareAlike",
            "BY-NC-ND": "Attribution-NonCommercial-NoDerivatives"}
# A control character, which no XML record may hold (XML 1.0's Char), and
# C1's, which mean nothing in a line of text.
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def one_line(text):
    """The text as one line: a control character, a line end among them,
    a space, and runs of spaces one."""
    return " ".join(CONTROL.sub(" ", str(text or "")).split())


def known(license_id):
    """(name, address, free of conditions): a Creative Commons license
    or CC0 as its deed names it, the deed's address, and whether it asks
    nothing of a reader (CC0 alone); None for any other license."""
    text = str(license_id or "").strip()
    if not text:
        return None
    if text.upper() == "CC0-1.0":
        return ("CC0 1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/", True)
    found = CC.match(text)
    if found:
        elements = found.group(1).upper()
        version, port = found.group(2) or found.group(4), found.group(3)
        # SPDX's BY-ND for 3.0 and before is the deed's by-nd; the name is
        # NoDerivs before 4.0.
        name = CC_NAMES[elements]
        if version != "4.0":
            name = name.replace("NoDerivatives", "NoDerivs")
        # 1.0's deed put NoDerivatives before NonCommercial, as SPDX's
        # own link to it does.
        path = "by-nd-nc" if elements == "BY-NC-ND" and version == "1.0" else elements.lower()
        address = f"https://creativecommons.org/licenses/{path}/{version}/"
        if port:
            address += port.lower() + "/"
        # Its scope as the deed names it: 4.0 is International, 3.0 is
        # otherwise Unported, and earlier Generic; a port is given by its
        # jurisdiction's code, which the deed spells out.
        scope = ("International" if version == "4.0" else port.upper() if port
                 else "Unported" if version == "3.0" else "Generic")
        return (f"Creative Commons {name} {version} {scope}", address, False)
    return None


# A Creative Commons deed's address, or its legal code's, within a text:
# the license's elements, version, and a port's jurisdiction, or CC0.
DEED = re.compile(r"creativecommons\.org/(?:licenses/(by(?:-nc)?(?:-nd|-sa)?|by-nd-nc)/"
                  r"(\d\.\d)(?:/([a-z]{2,3}))?(?=[/\s\"'<>),.;]|$)|(publicdomain/zero/1\.0))",
                  re.I)


def from_address(text):
    """The SPDX identifier of the first Creative Commons license or CC0
    whose deed's or legal code's address the text holds, as an unpacked
    book's metadata gives it (OpenStax's collection, an EPUB's rights), or
    None where it holds none this module knows."""
    for found in DEED.finditer(str(text or "")):
        if found.group(4):
            return "CC0-1.0"
        elements, version, port = found.group(1).upper(), found.group(2), found.group(3)
        if elements == "BY-ND-NC":
            elements = "BY-NC-ND"
        spdx = f"CC-{elements}-{version}" + (f"-{port.upper()}" if port else "")
        if known(spdx):
            return spdx
    return None


def is_open(license_id):
    """Whether the license is a Creative Commons license or CC0, which
    cost nothing to use."""
    text = str(license_id or "").strip()
    return text.upper() == "CC0-1.0" or bool(CC.match(text))


COPYRIGHT_KEYS = ("holder", "year", "text")
# A year, or a range of them, its two years a hyphen or a dash apart.
YEARS = re.compile(r"^(\d{4})(?:\s*[-\u2013]\s*(\d{4}))?$")


def check_copyright(value, where):
    """project.copyright as a setting takes it, the line whole or a
    mapping of its parts (holder, year, text), and the problems it has,
    each naming where. A holder is a person or an organization, as a
    publisher is given, or a list of them; a year is one, or a range of
    two (2024-2026), kept with a dash between."""
    import people
    if not isinstance(value, dict):
        if isinstance(value, (bool, list)):
            return None, [f"{where} is {value!r}; give the line as it should read, or a "
                          "mapping with holder, year, and text"]
        text = str(value).strip()
        if CONTROL.search(text):
            return None, [f"{where} is {text!r}, which holds a control character"]
        return text, []
    problems = []
    unknown = sorted(str(k) for k in value if k not in COPYRIGHT_KEYS)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        "holder, year, and text")
    out = {}
    holders = value.get("holder")
    if holders in (None, "", []):
        problems.append(f"{where} has no holder; give who holds the copyright, or write the "
                        "line whole")
    else:
        checked = []
        many = isinstance(holders, list)
        for index, holder in enumerate(holders if many else [holders]):
            here = people.entry(f"{where}.holder", index + 1) if many else f"{where}'s holder"
            kind = "organization" if isinstance(holder, dict) and "ror" in holder else "person"
            done, more = people.check(holder, here, kind)
            problems += more
            if done is not None:
                checked.append(done)
        out["holder"] = checked if many else (checked[0] if checked else None)
    year = value.get("year")
    if year is not None:
        found = YEARS.match(str(year).strip()) if not isinstance(year, bool) else None
        if not found or (found.group(2) and found.group(2) < found.group(1)):
            problems.append(f"{where}'s year is {year!r}; give a year (2026) or a range of "
                            "years, the earlier first (2024-2026)")
        else:
            out["year"] = found.group(1) + ("\u2013" + found.group(2) if found.group(2)
                                            else "")
    text = value.get("text")
    if text is not None:
        line = str(text).strip()
        if isinstance(text, (bool, dict, list)):
            problems.append(f"{where}'s text is {text!r}; give it as text")
        elif CONTROL.search(line):
            problems.append(f"{where}'s text is {line!r}, which holds a control character")
        elif line:
            out["text"] = line
    return out, problems


def holders(value):
    """The copyright's holders' names, in order, from its parts."""
    import people
    holder = (value or {}).get("holder") if isinstance(value, dict) else None
    return people.names(holder if isinstance(holder, list) else [holder] if holder else [])


def copyright_line(value, published=""):
    """The copyright line: the line whole as given, or, from its parts,
    "Copyright", the year (published's where the parts give none), the
    holders ("A", "A and B", "A, B, and C"), a full stop, and the text.
    "" where nothing is given."""
    if not isinstance(value, dict):
        return one_line(value)
    names = holders(value)
    if len(names) > 2:
        named = ", ".join(names[:-1]) + ", and " + names[-1]
    else:
        named = " and ".join(names)
    year = str(value.get("year") or str(published or "")[:4]).strip()
    line = " ".join(part for part in ("Copyright", year, named) if part)
    line = one_line(line if line.endswith(".") else line + ".") if named else ""
    extra = one_line(value.get("text"))
    return " ".join(part for part in (line, extra) if part)


def statement(copyright, license_id, published="", noted=False):
    """The rights as one statement, as an EPUB's dc:rights and a
    cartridge's rights description give them: the copyright line
    (copyright_line), then the license by name and address, or as given
    where it has neither, "except where otherwise noted" (noted) where
    some pages have a license of their own (exceptions)."""
    parts = []
    line = copyright_line(copyright, published)
    if line:
        parts.append(line if line.endswith(".") else line + ".")
    text = one_line(license_id)
    if text:
        found = known(text)
        if found and found[2]:
            said = f"dedicated to the public domain under {found[0]} ({found[1]})."
        elif found:
            said = f"licensed under {found[0]} ({found[1]})."
        else:
            said = f"license: {text}."
        parts.append("Except where otherwise noted, " + said if noted
                     else said[0].upper() + said[1:])
    return " ".join(parts)


def short_name(license_id):
    """The license's short name as its deed writes it: a Creative Commons
    license's "CC BY-NC-SA 4.0" (a port's "CC BY 3.0 US"), "CC0 1.0", and
    any other license as it's given. SPDX's identifier puts a hyphen
    after CC where Creative Commons writes a space."""
    text = one_line(license_id)
    if text.upper() == "CC0-1.0":
        return "CC0 1.0"
    found = CC.match(text)
    if not found:
        return text
    version, port = found.group(2) or found.group(4), found.group(3)
    return " ".join(part for part in ("CC", found.group(1).upper(), version,
                                      (port or "").upper()) if part)


ENTRY_KEYS = ("pages", "title", "author", "source", "license", "changes", "statement",
              "each_page")
# The parts of the work a statement names, which a statement in the
# author's own words takes the place of.
TASL_KEYS = ("title", "author", "source", "changes")


def _text(value, where, key, problems):
    """A text setting of an entry, one line, or None with a problem."""
    if isinstance(value, (bool, dict, list)):
        problems.append(f"{where}'s {key} is {value!r}; give it as text")
        return None
    text = str(value).strip()
    if CONTROL.search(text):
        problems.append(f"{where}'s {key} is {text!r}, which holds a control character")
        return None
    return text or None


def check_entry(value, where):
    """An entry of project.licenses, or a part's, as a setting takes it,
    and the problems it has, each naming where: pages, a page's name or a
    pattern (ch03-*), or a list of them; then either title, author (a
    name or a list), source (an address, checked), license, and changes,
    or statement, the author's own words, with a license or not; and
    each_page, true for the sentence at the end of every page it names
    and not only the last."""
    import identifiers
    if not isinstance(value, dict):
        return None, [f"{where} is {value!r}; give a mapping with pages and either title "
                      "and license or a statement"]
    problems = []
    unknown = sorted(str(k) for k in value if k not in ENTRY_KEYS)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        + ", ".join(ENTRY_KEYS))
    out = {}
    pages = value.get("pages")
    pages = pages if isinstance(pages, list) else [] if pages in (None, "") else [pages]
    names = []
    for page in pages:
        name = _text(page, where, "pages", problems)
        if name and "/" in name:
            problems.append(f"{where}'s pages names {name!r}; a page is named as the run "
                            "names it, without a folder")
        elif name:
            names.append(name)
    if not names:
        problems.append(f"{where} has no pages; name the pages it covers, or a pattern "
                        "such as ch03-*")
    out["pages"] = names
    for key in ("title", "source", "license", "changes", "statement"):
        if value.get(key) is not None:
            text = _text(value[key], where, key, problems)
            if text and key == "source":
                try:
                    text = identifiers.url(text)
                except ValueError as exc:
                    problems.append(f"{where}'s source: {exc}")
                    text = None
            if text:
                out[key] = text
    author = value.get("author")
    if author is not None:
        authors = author if isinstance(author, list) else [author]
        checked = [a for a in (_text(a, where, "author", problems) for a in authors) if a]
        if checked:
            out["author"] = checked
    each = value.get("each_page")
    if each is not None:
        if not isinstance(each, bool):
            problems.append(f"{where}'s each_page is {each!r}; give true or false")
        elif each:
            out["each_page"] = True
    if "statement" in out:
        given = [k for k in TASL_KEYS if k in out]
        if given:
            problems.append(f"{where} has a statement and {', '.join(given)}; give the "
                            "statement in your own words, or the parts it's made from, "
                            "not both")
    else:
        if "title" not in out:
            problems.append(f"{where} has no title; give the title of the work it's "
                            "adapted from, or a statement in your own words")
        if "license" not in out:
            problems.append(f"{where} has no license; give the work's license, its SPDX "
                            "identifier (CC-BY-4.0) or its name")
    return out, problems


def check_entries(value, where):
    """project.licenses, or a part's, as a list of entries (check_entry),
    and the problems they have."""
    import people
    entries = value if isinstance(value, list) else [] if value in (None, "") else [value]
    out, problems = [], []
    for index, entry in enumerate(entries, 1):
        checked, more = check_entry(entry, people.entry(where, index))
        problems += more
        if checked is not None and not more:
            out.append(checked)
    return out, problems


def covers(entry, stem):
    """Whether the entry names the page, by its name or a pattern."""
    return any(fnmatch.fnmatchcase(stem, pattern) for pattern in entry.get("pages") or [])


def page_licenses(entries, stems, default):
    """{page: [its licenses]}: each license the entries naming it give,
    in order, and the part's (default) where none does; a page with none
    at all is left out."""
    out = {}
    for stem in stems:
        own = []
        for entry in entries or []:
            license_id = entry.get("license")
            if license_id and covers(entry, stem) and license_id not in own:
                own.append(license_id)
        if own or one_line(default):
            out[stem] = own or [one_line(default)]
    return out


def exceptions(entries, default):
    """Whether an entry gives some pages a license other than the part's,
    so that the book's rights hold "except where otherwise noted"."""
    base = one_line(default).upper()
    return any(entry.get("license") and one_line(entry["license"]).upper() != base
               for entry in entries or [])


def unmatched(entries, stems):
    """The entries that name no page among stems, each by its place (1 is
    the first)."""
    return [index for index, entry in enumerate(entries or [], 1)
            if not any(covers(entry, stem) for stem in stems)]


def statement_pages(entries, ordered):
    """{page: [the entries whose sentence goes at its end]}: an entry's
    last page in the book's order, or each of its pages with each_page."""
    out = {}
    for entry in entries or []:
        pages = [stem for stem in ordered if covers(entry, stem)]
        for stem in (pages if entry.get("each_page") else pages[-1:]):
            out.setdefault(stem, []).append(entry)
    return out


def names_joined(names):
    """"A", "A and B", or "A, B, and C"."""
    names = [one_line(n) for n in names or [] if one_line(n)]
    if len(names) > 2:
        return ", ".join(names[:-1]) + ", and " + names[-1]
    return " and ".join(names)


def tasl_parts(entry):
    """The sentence an entry gives at the end of its page, as runs of
    (text, kind, address): kind "" for plain text, "title" for the work's
    title (linked to its source where it has one), and "license" for the
    license's short name (linked to its deed where it's known). An entry
    with a statement gives it whole. The fixed form is English:
    "Adapted from Title by Author, licensed under CC BY 4.0. Changes: …"."""
    if entry.get("statement"):
        return [(one_line(entry["statement"]), "", "")]
    runs = [("Adapted from ", "", ""), (one_line(entry.get("title")), "title",
                                         entry.get("source") or "")]
    if entry.get("author"):
        runs.append((" by " + names_joined(entry["author"]), "", ""))
    found = known(entry.get("license"))
    runs += [(", licensed under ", "", ""),
             (short_name(entry.get("license")), "license", found[1] if found else ""),
             (".", "", "")]
    if entry.get("changes"):
        changes = one_line(entry["changes"])
        runs.append((" Changes: " + changes + ("" if changes[-1:] in ".!?" else "."), "", ""))
    return runs


def tasl_sentence(entry):
    """The entry's sentence as plain text (tasl_parts)."""
    return "".join(text for text, _, _ in tasl_parts(entry))


def restricted(project):
    """What isn't openly licensed (is_open), for packing to leave out of
    an archive made to share unless asked: [(where, license)], where a
    part's name ("parts.book"), the project ("project"), or an entry's
    pages ("parts.book's licenses' first entry"). A license left unset
    isn't open either, since nothing says it may be shared."""
    import people
    out = []
    parts = project.get("parts") if isinstance(project.get("parts"), dict) else {}
    blocks = [(f"parts.{name}", block) for name, block in parts.items()
              if isinstance(block, dict)] or [("project", project)]
    for where, block in blocks:
        license_id = one_line(block.get("license") or project.get("license"))
        if not is_open(license_id):
            out.append((where, license_id))
        entries = block.get("licenses") if where != "project" else project.get("licenses")
        if where != "project" and entries is None:
            entries = project.get("licenses")
        for index, entry in enumerate(entries or [], 1):
            if isinstance(entry, dict) and entry.get("license") \
                    and not is_open(entry["license"]):
                label = "licenses" if where == "project" else f"{where}'s licenses"
                out.append((people.entry(label, index), one_line(entry["license"])))
    return out
