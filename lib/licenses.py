"""
licenses.py -- what a book's license and copyright line say, for the
outputs that record them.

project.license is the license's SPDX identifier where it has one and
otherwise its name; project.copyright the line as it should read. The
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


def statement(copyright_line, license_id):
    """The rights as one statement, as an EPUB's dc:rights and a
    cartridge's rights description give them: the copyright line, then
    the license by name and address, or as given where it has neither."""
    parts = []
    line = one_line(copyright_line)
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
