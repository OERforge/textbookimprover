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


def statement(copyright, license_id, published=""):
    """The rights as one statement, as an EPUB's dc:rights and a
    cartridge's rights description give them: the copyright line
    (copyright_line), then the license by name and address, or as given
    where it has neither."""
    parts = []
    line = copyright_line(copyright, published)
    if line:
        parts.append(line if line.endswith(".") else line + ".")
    text = one_line(license_id)
    if text:
        found = known(text)
        if found and found[2]:
            parts.append(f"Dedicated to the public domain under {found[0]} ({found[1]}).")
        elif found:
            parts.append(f"Licensed under {found[0]} ({found[1]}).")
        else:
            parts.append(f"License: {text}.")
    return " ".join(parts)
