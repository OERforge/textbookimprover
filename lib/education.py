"""
education.py -- what a book's settings say of its use in teaching: the
subjects it's classed under, its readers' ages, and the time it takes,
each checked where it's set, and the classifications and the educational
category a Common Cartridge's manifest gives them.

A subject is a name, or a mapping with name, id (its code in a scheme),
and scheme (the scheme's name, CIP 2020 say). A typical age is a range
as schema.org's typicalAgeRange writes one (18-22, or 18- for 18 and
over), and a time required an ISO 8601 duration (PT40H), as its
timeRequired takes. The manifest's classifications follow Common
Cartridge 1.1's profile of LOM, whose purposes are a closed list and
whose taxon path has no field naming its taxonomy, so a classification's
description names the scheme.

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
from xml.sax.saxutils import escape

SUBJECT_KEYS = ("name", "id", "scheme")
# A control character has no place in a record, and breaks the XML a
# value is written into.
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
AGE_RANGE = re.compile(r"^(\d{1,3})-(\d{1,3})?$")
# ISO 8601's duration as schema.org's Duration takes it: P, then years,
# months, weeks, and days, then T and hours, minutes, and seconds, at
# least one of them, the last a decimal where it's given as one.
DURATION = re.compile(r"^P(?=\d|T\d)(?:\d+Y)?(?:\d+M)?(?:\d+W)?(?:\d+D)?"
                      r"(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:[.,]\d+)?S)?)?$")


def subject(value, where):
    """A subject as a setting takes it, a name or {name, id, scheme}, and
    the problems it has, each naming where."""
    if isinstance(value, bool) or value is None or isinstance(value, list):
        return None, [f"{where} is {value!r}; give a name, or a mapping with name, id, "
                      "and scheme"]
    if not isinstance(value, dict):
        text = str(value).strip()
        if CONTROL.search(text):
            return None, [f"{where} is {text!r}, which holds a control character"]
        if not text:
            return None, [f"{where} is empty; give a name"]
        return text, []
    problems = []
    unknown = sorted(str(k) for k in value if k not in SUBJECT_KEYS)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        + ", ".join(SUBJECT_KEYS))
    out = {}
    for key in SUBJECT_KEYS:
        item = value.get(key)
        if item is None:
            continue
        if isinstance(item, (bool, dict, list)):
            problems.append(f"{where}'s {key} is {item!r}; give it as text")
            continue
        if isinstance(item, float):
            # 45.0600 unquoted is the number 45.06 to YAML, and a code
            # isn't a number.
            problems.append(f"{where}'s {key} is {item!r}, a number to YAML, which drops a "
                            "zero at its end; put it in quotes")
            continue
        text = str(item).strip()
        if CONTROL.search(text):
            problems.append(f"{where}'s {key} is {text!r}, which holds a control character")
        elif text:
            out[key] = text
    if not out.get("name"):
        problems.append(f"{where} has no name; a mapping needs name, as a reader should "
                        "see it")
    return out, problems


def age_range(value):
    """A typical age as schema.org's typicalAgeRange writes it, or
    ValueError where it isn't one."""
    text = str(value).strip()
    found = AGE_RANGE.match(text)
    if not found or (found.group(2) and int(found.group(2)) < int(found.group(1))):
        raise ValueError(f"{value!r} isn't a range of ages, which is the youngest, a hyphen, "
                         "and the oldest (18-22), or the youngest and a hyphen (18-)")
    return text


def duration(value):
    """A time required as an ISO 8601 duration, or ValueError where it
    isn't one."""
    text = str(value).strip().upper()
    if not DURATION.match(text):
        raise ValueError(f"{value!r} isn't an ISO 8601 duration, which is P and then its "
                         "parts (PT40H for 40 hours, P2W for two weeks)")
    return text


CHECKS = {"agerange": age_range, "duration": duration}


def subject_parts(entry):
    """(name, id, scheme) of a subject, each "" where it isn't set."""
    if isinstance(entry, dict):
        return tuple(str(entry.get(k) or "").strip() for k in SUBJECT_KEYS)
    return (str(entry or "").strip(), "", "")


def one_line(text):
    """The text as one line, a control character, which no XML record may
    hold, a space."""
    return " ".join(CONTROL.sub(" ", str(text or "")).split())


def _texts(values):
    return [t for t in (one_line(v) for v in values or []) if t]


def _classification(purpose, taxa, description=""):
    """One of the manifest's classifications: its purpose, a taxon path for
    each (id, entry), and a description, the scheme's name."""
    out = ("      <lomimscc:classification>\n"
           "        <lomimscc:purpose>\n"
           f"          <lomimscc:value>{purpose}</lomimscc:value>\n"
           "        </lomimscc:purpose>\n")
    for taxon_id, entry in taxa:
        out += ("        <lomimscc:taxonPath>\n"
                "          <lomimscc:taxon>\n")
        if taxon_id:
            out += f"            <lomimscc:id>{escape(taxon_id)}</lomimscc:id>\n"
        out += ("            <lomimscc:entry>\n"
                f"              <lomimscc:string>{escape(entry)}</lomimscc:string>\n"
                "            </lomimscc:entry>\n"
                "          </lomimscc:taxon>\n"
                "        </lomimscc:taxonPath>\n")
    if description:
        out += ("        <lomimscc:description>\n"
                f"          <lomimscc:string>{escape(description)}</lomimscc:string>\n"
                "        </lomimscc:description>\n")
    return out + "      </lomimscc:classification>\n"


def manifest_educational(education):
    """The manifest's educational category, where the book gives a
    context: its one learning resource type, the profile's fixed IMS
    Common Cartridge, and the context, from LOM's four."""
    context = one_line((education or {}).get("context"))
    if not context:
        return ""
    return ("      <lomimscc:educational>\n"
            "        <lomimscc:learningResourceType>\n"
            "          <lomimscc:value>IMS Common Cartridge</lomimscc:value>\n"
            "        </lomimscc:learningResourceType>\n"
            "        <lomimscc:context>\n"
            "          <lomimscc:source>LOMv1.0</lomimscc:source>\n"
            f"          <lomimscc:value>{escape(context)}</lomimscc:value>\n"
            "        </lomimscc:context>\n"
            "      </lomimscc:educational>\n")


def manifest_classifications(education):
    """The manifest's classifications: the subjects as disciplines, one
    classification for each scheme, in the order the schemes first come,
    its description naming the scheme; the level as an educational level;
    and each objective and prerequisite a taxon of its own."""
    education = education or {}
    out = ""
    schemes = {}
    for entry in education.get("subjects") or []:
        name, code, scheme = subject_parts(entry)
        if name:
            schemes.setdefault(scheme, []).append((code, name))
    for scheme, taxa in schemes.items():
        out += _classification("discipline", taxa, scheme)
    level = one_line(education.get("level"))
    if level:
        out += _classification("educational level", [("", level)])
    for key, purpose in (("objectives", "educational objective"),
                         ("prerequisites", "prerequisite")):
        texts = _texts(education.get(key))
        if texts:
            out += _classification(purpose, [("", t) for t in texts])
    return out
