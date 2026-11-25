"""
people.py -- the people and organizations a book's settings name.

An author, an adapter, an editor, or a contributor is a name, or a
mapping with name and, optionally, given, family, orcid, and
affiliation; a contributor's mapping has a role too, a MARC relator by
its code (ill) or its term (illustrator). The publisher and an
affiliation are a name, or a mapping with name and, optionally, ror. A
name alone stays valid wherever one is taken, so a setting written as a
list of names reads as it always did.

A person's given and family names are theirs to give, never split from
name by TextbookImprover, since a program can't do that safely; where
both are given an EPUB files the person under "family, given". An ORCID
iD is checked for its check digit (ISO 7064 MOD 11-2, as ORCID describes
it) and a ROR ID for its form and its two-digit checksum, so that a
mistyped one is caught where it's set rather than in a deposit's record.
Each may be given bare or as its address, and is written as its address,
the form both registries prefer.

The relators are the MARC code list's, as Pandoc 3.14's EPUB writer
holds them (relatorMap, src/Text/Pandoc/Writers/EPUB.hs): 261 terms, each
with its code. Pandoc leaves out a role it doesn't know, with no word, so
the setting is checked against the same list.

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

ORCID_RE = re.compile(r"^(?:https?://orcid\.org/)?(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])$",
                      re.I)
# A ROR ID's unique part: a 0, six characters of Crockford's base 32
# (no i, l, o, or u), and two digits of checksum.
ROR_RE = re.compile(r"^(?:https?://ror\.org/)?(0[0-9a-hjkmnp-tv-z]{6})(\d{2})$", re.I)
CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
# A control character has no place in a name, and breaks the XML and the
# vCards a name is written into.
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")

PERSON_KEYS = ("name", "given", "family", "orcid", "affiliation")
CONTRIBUTOR_KEYS = PERSON_KEYS + ("role",)
ORGANIZATION_KEYS = ("name", "ror")
FUNDING_KEYS = ("funder", "award")
AWARD_KEYS = ("number", "title", "url")

RELATORS = {
    "abridger": "abr", "actor": "act", "adapter": "adp", "addressee": "rcp",
    "analyst": "anl", "animator": "anm", "annotator": "ann", "appellant": "apl",
    "appellee": "ape", "applicant": "app", "architect": "arc", "arranger": "arr",
    "art copyist": "acp", "art director": "adi", "artist": "art",
    "artistic director": "ard", "assignee": "asg", "associated name": "asn",
    "attributed name": "att", "auctioneer": "auc", "author": "aut",
    "author in quotations or text abstracts": "aqt",
    "author of afterword, colophon, etc.": "aft", "author of dialog": "aud",
    "author of introduction, etc.": "aui", "autographer": "ato",
    "bibliographic antecedent": "ant", "binder": "bnd", "binding designer": "bdd",
    "blurb writer": "blw", "book designer": "bkd", "book producer": "bkp",
    "bookjacket designer": "bjd", "bookplate designer": "bpd", "bookseller": "bsl",
    "braille embosser": "brl", "broadcaster": "brd", "calligrapher": "cll",
    "cartographer": "ctg", "caster": "cas", "censor": "cns", "choreographer": "chr",
    "cinematographer": "cng", "client": "cli", "collection registrar": "cor",
    "collector": "col", "collotyper": "clt", "colorist": "clr", "commentator": "cmm",
    "commentator for written text": "cwt", "compiler": "com", "complainant": "cpl",
    "complainant-appellant": "cpt", "complainant-appellee": "cpe", "composer": "cmp",
    "compositor": "cmt", "conceptor": "ccp", "conductor": "cnd", "conservator": "con",
    "consultant": "csl", "consultant to a project": "csp", "contestant": "cos",
    "contestant-appellant": "cot", "contestant-appellee": "coe", "contestee": "cts",
    "contestee-appellant": "ctt", "contestee-appellee": "cte", "contractor": "ctr",
    "contributor": "ctb", "copyright claimant": "cpc", "copyright holder": "cph",
    "corrector": "crr", "correspondent": "crp", "costume designer": "cst",
    "court governed": "cou", "court reporter": "crt", "cover designer": "cov",
    "creator": "cre", "curator": "cur", "dancer": "dnc", "data contributor": "dtc",
    "data manager": "dtm", "dedicatee": "dte", "dedicator": "dto", "defendant": "dfd",
    "defendant-appellant": "dft", "defendant-appellee": "dfe",
    "degree granting institution": "dgg", "delineator": "dln", "depicted": "dpc",
    "depositor": "dpt", "designer": "dsr", "director": "drt", "dissertant": "dis",
    "distribution place": "dbp", "distributor": "dst", "donor": "dnr", "draftsman": "drm",
    "dubious author": "dub", "editor": "edt", "editor of compilation": "edc",
    "editor of moving image work": "edm", "electrician": "elg", "electrotyper": "elt",
    "enacting jurisdiction": "enj", "engineer": "eng", "engraver": "egr", "etcher": "etr",
    "event place": "evp", "expert": "exp", "facsimilist": "fac", "field director": "fld",
    "film director": "fmd", "film distributor": "fds", "film editor": "flm",
    "film producer": "fmp", "filmmaker": "fmk", "first party": "fpy", "forger": "frg",
    "former owner": "fmo", "funder": "fnd", "geographic information specialist": "gis",
    "honoree": "hnr", "host": "hst", "host institution": "his", "illuminator": "ilu",
    "illustrator": "ill", "inscriber": "ins", "instrumentalist": "itr",
    "interviewee": "ive", "interviewer": "ivr", "inventor": "inv", "issuing body": "isb",
    "judge": "jud", "jurisdiction governed": "jug", "laboratory": "lbr",
    "laboratory director": "ldr", "landscape architect": "lsa", "lead": "led",
    "lender": "len", "libelant": "lil", "libelant-appellant": "lit",
    "libelant-appellee": "lie", "libelee": "lel", "libelee-appellant": "let",
    "libelee-appellee": "lee", "librettist": "lbt", "licensee": "lse", "licensor": "lso",
    "lighting designer": "lgd", "lithographer": "ltg", "lyricist": "lyr",
    "manufacture place": "mfp", "manufacturer": "mfr", "marbler": "mrb",
    "markup editor": "mrk", "metadata contact": "mdc", "metal-engraver": "mte",
    "moderator": "mod", "monitor": "mon", "music copyist": "mcp",
    "musical director": "msd", "musician": "mus", "narrator": "nrt",
    "onscreen presenter": "osp", "opponent": "opn", "organizer of meeting": "orm",
    "originator": "org", "other": "oth", "owner": "own", "panelist": "pan",
    "papermaker": "ppm", "patent applicant": "pta", "patent holder": "pth",
    "patron": "pat", "performer": "prf", "permitting agency": "pma", "photographer": "pht",
    "plaintiff": "ptf", "plaintiff-appellant": "ptt", "plaintiff-appellee": "pte",
    "platemaker": "plt", "praeses": "pra", "presenter": "pre", "printer": "prt",
    "printer of plates": "pop", "printmaker": "prm", "process contact": "prc",
    "producer": "pro", "production company": "prn", "production designer": "prs",
    "production manager": "pmn", "production personnel": "prd", "production place": "prp",
    "programmer": "prg", "project director": "pdr", "proofreader": "pfr",
    "provider": "prv", "publication place": "pup", "publisher": "pbl",
    "publishing director": "pbd", "puppeteer": "ppt", "radio director": "rdd",
    "radio producer": "rpc", "recording engineer": "rce", "recordist": "rcd",
    "redaktor": "red", "renderer": "ren", "reporter": "rpt", "repository": "rps",
    "research team head": "rth", "research team member": "rtm", "researcher": "res",
    "respondent": "rsp", "respondent-appellant": "rst", "respondent-appellee": "rse",
    "responsible party": "rpy", "restager": "rsg", "restorationist": "rsr",
    "reviewer": "rev", "rubricator": "rbr", "scenarist": "sce",
    "scientific advisor": "sad", "screenwriter": "aus", "scribe": "scr", "sculptor": "scl",
    "second party": "spy", "secretary": "sec", "seller": "sll", "set designer": "std",
    "setting": "stg", "signer": "sgn", "singer": "sng", "sound designer": "sds",
    "speaker": "spk", "sponsor": "spn", "stage director": "sgd", "stage manager": "stm",
    "standards body": "stn", "stereotyper": "str", "storyteller": "stl",
    "supporting host": "sht", "surveyor": "srv", "teacher": "tch",
    "technical director": "tcd", "television director": "tld",
    "television producer": "tlp", "thesis advisor": "ths", "transcriber": "trc",
    "translator": "trl", "type designer": "tyd", "typographer": "tyg",
    "university place": "uvp", "videographer": "vdg", "witness": "wit",
    "wood engraver": "wde", "woodcutter": "wdc", "writer of accompanying material": "wam",
    "writer of added commentary": "wac", "writer of added lyrics": "wal",
    "writer of added text": "wat",
}
RELATOR_CODES = frozenset(RELATORS.values())


def orcid(value):
    """An ORCID iD as its address, from the bare iD or the address, or
    ValueError where it isn't one or its check digit is wrong."""
    found = ORCID_RE.match(str(value).strip())
    if not found:
        raise ValueError(f"{value!r} isn't an ORCID iD, which is four groups of four "
                         "digits, the last character a digit or X (0000-0002-1825-0097)")
    digits = "".join(found.groups()).upper()
    total = 0
    for digit in digits[:-1]:
        total = (total + int(digit)) * 2
    check = (12 - total % 11) % 11
    if digits[-1] != ("X" if check == 10 else str(check)):
        raise ValueError(f"{value!r} isn't an ORCID iD: its last character, its check "
                         "digit, doesn't match the others, so a digit is likely mistyped")
    return "https://orcid.org/" + "-".join(digits[i:i + 4] for i in range(0, 16, 4))


def ror(value):
    """A ROR ID as its address, from its unique part or the address, or
    ValueError where it isn't one or its checksum is wrong."""
    found = ROR_RE.match(str(value).strip())
    if not found:
        raise ValueError(f"{value!r} isn't a ROR ID, which is a 0, six letters and digits, "
                         "and two digits (https://ror.org/05dxps055)")
    unique, checksum = found.group(1).lower(), found.group(2)
    number = 0
    for character in unique:
        number = number * 32 + CROCKFORD.index(character)
    if 98 - (number * 100) % 97 != int(checksum):
        raise ValueError(f"{value!r} isn't a ROR ID: its last two digits, its checksum, "
                         "don't match the rest, so a character is likely mistyped")
    return "https://ror.org/" + unique + checksum


def relator(role):
    """A role's MARC relator code, from its code or its term, or None."""
    text = str(role or "").strip().lower()
    if text in RELATOR_CODES:
        return text
    return RELATORS.get(text)


def name(entry):
    """The name of a person or an organization, as a setting gives it."""
    if isinstance(entry, dict):
        return str(entry.get("name") or "").strip()
    return str(entry or "").strip()


def file_as(entry):
    """"Family, Given", where a person's mapping gives both, else None."""
    if isinstance(entry, dict):
        given = str(entry.get("given") or "").strip()
        family = str(entry.get("family") or "").strip()
        if given and family:
            return f"{family}, {given}"
    return None


def _vcard_text(text):
    """text escaped as a vCard's value is (RFC 2426, 4: a backslash, a
    comma, and a semicolon each after a backslash)."""
    return re.sub(r"([\\,;])", r"\\\1", str(text))


def vcard(entry, organization=False):
    """A person or an organization as a vCard 3.0 (RFC 2426), as IEEE
    LOM's contribute takes one for its entity: FN and N, which 3.0
    requires, N's family and given parts where the mapping sets them; the
    affiliation's name as ORG, or the organization's own; and the ORCID iD,
    or the ROR ID, as URL."""
    lines = ["BEGIN:VCARD", "VERSION:3.0", "FN:" + _vcard_text(name(entry))]
    mapping = entry if isinstance(entry, dict) else {}
    if organization:
        lines.append("N:;;;;")
        lines.append("ORG:" + _vcard_text(name(entry)))
        if mapping.get("ror"):
            lines.append("URL:" + mapping["ror"])
    else:
        lines.append("N:%s;%s;;;" % (_vcard_text(mapping.get("family") or ""),
                                       _vcard_text(mapping.get("given") or "")))
        if name(mapping.get("affiliation")):
            lines.append("ORG:" + _vcard_text(name(mapping["affiliation"])))
        if mapping.get("orcid"):
            lines.append("URL:" + mapping["orcid"])
    lines.append("END:VCARD")
    return "\n".join(lines)


def names(entries):
    """The names of a list of people, empty ones left out."""
    return [n for n in (name(e) for e in entries or []) if n]


def _award(value, where):
    """An award as a setting takes it, its number or name as the funder
    gives it, or a mapping with number, title, and url, as DataCite's
    awardNumber, awardTitle, and awardURI, and the problems it has."""
    import identifiers
    if not isinstance(value, dict):
        text = str(value).strip()
        if isinstance(value, (bool, list)):
            return None, [f"{where} is {value!r}; give its number or name, or a mapping "
                          "with number, title, and url"]
        if CONTROL.search(text):
            return None, [f"{where} is {text!r}, which holds a control character"]
        return (text or None), []
    problems = []
    unknown = sorted(str(k) for k in value if k not in AWARD_KEYS)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        + ", ".join(AWARD_KEYS))
    out = {}
    for key in AWARD_KEYS:
        item = value.get(key)
        if item is None:
            continue
        text = str(item).strip()
        if isinstance(item, (bool, dict, list)):
            problems.append(f"{where}'s {key} is {item!r}; give it as text")
        elif CONTROL.search(text):
            problems.append(f"{where}'s {key} is {text!r}, which holds a control character")
        elif key == "url" and text:
            try:
                out[key] = identifiers.url(text)
            except ValueError as exc:
                problems.append(f"{where}'s url: {exc}")
        elif text:
            out[key] = text
    if not out.get("number") and not out.get("title"):
        problems.append(f"{where} has neither a number nor a title; give the award's "
                        "number, its title, or both")
    return out, problems


def _funding(value, where):
    """A funder and its award as {funder, award}: a funder's name alone, or
    a mapping with funder, an organization, and award (_award)."""
    if not isinstance(value, dict):
        funder, problems = _check(value, where, "organization")
        return ({"funder": funder} if funder is not None else None), problems
    problems = []
    unknown = sorted(str(k) for k in value if k not in FUNDING_KEYS)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        "funder and award")
    if value.get("funder") is None:
        return None, problems + [f"{where} has no funder; give the funder's name, or a "
                                 "mapping with name and ror"]
    funder, more = _check(value["funder"], f"{where}'s funder", "organization")
    problems += more
    out = {"funder": funder}
    if value.get("award") is not None:
        award, more = _award(value["award"], f"{where}'s award")
        problems += more
        if award:
            out["award"] = award
    return out, problems


def _check(value, where, kind):
    """value as kind ("person", "contributor", "organization", or
    "funding"), and the problems it has: a name, or a mapping of the
    kind's keys."""
    if kind == "funding":
        return _funding(value, where)
    problems = []
    if isinstance(value, bool) or value is None:
        return None, [f"{where} is {value!r}; give a name, or a mapping with name"]
    if not isinstance(value, dict):
        text = str(value).strip()
        if CONTROL.search(text):
            return None, [f"{where} is {text!r}, which holds a control character"]
        if kind == "contributor":
            return None, [f"{where} is {text!r}; a contributor is a mapping with name and "
                          "role, the role a MARC relator (ill or illustrator, say)"]
        if not text:
            return None, [f"{where} is empty; give a name"]
        return text, []
    allowed = {"person": PERSON_KEYS, "contributor": CONTRIBUTOR_KEYS,
               "organization": ORGANIZATION_KEYS}[kind]
    unknown = sorted(str(k) for k in value if k not in allowed)
    if unknown:
        problems.append(f"{where} has {', '.join(unknown)}, which it doesn't take; it takes "
                        + ", ".join(allowed))
    out = {}
    for key in allowed:
        if key not in value or value[key] is None:
            continue
        item = value[key]
        if key == "affiliation":
            item, more = _check(item, f"{where}'s affiliation", "organization")
            problems += more
            if item is not None:
                out[key] = item
            continue
        if isinstance(item, (bool, dict, list)):
            problems.append(f"{where}'s {key} is {item!r}; give it as text")
            continue
        text = str(item).strip()
        if CONTROL.search(text):
            problems.append(f"{where}'s {key} is {text!r}, which holds a control character")
            continue
        if key == "orcid":
            try:
                text = orcid(text)
            except ValueError as exc:
                problems.append(f"{where}'s orcid: {exc}")
                continue
        elif key == "ror":
            try:
                text = ror(text)
            except ValueError as exc:
                problems.append(f"{where}'s ror: {exc}")
                continue
        elif key == "role":
            code = relator(text)
            if code is None:
                problems.append(f"{where}'s role is {text!r}, which isn't a MARC relator's code "
                                "or term (ill or illustrator, trl or translator): "
                                "https://www.loc.gov/marc/relators/relaterm.html")
                continue
        if text:
            out[key] = text
    if not out.get("name"):
        problems.append(f"{where} has no name; a mapping needs name, as a reader should "
                        "see it")
    if kind == "contributor" and "role" not in out and not any("role" in p for p in problems):
        problems.append(f"{where} has no role; give a MARC relator (ill or illustrator, say)")
    return out, problems


def check(value, where, kind, prefix=""):
    """value as a setting of kind ("person", "contributor", "organization",
    or "funding") takes it, and the problems it has, each a sentence
    naming where (publisher, authors' second entry), after
    prefix. An ORCID iD and a ROR ID come back as their addresses."""
    value, problems = _check(value, where, kind)
    return value, [prefix + p for p in problems]


ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
            "ninth", "tenth")


def entry(path, index):
    """What an entry of a list of people is called in a message: the
    second of authors is "authors' second entry"."""
    if 0 < index <= len(ORDINALS):
        nth = ORDINALS[index - 1]
    else:
        suffix = "th" if 10 <= index % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(
            index % 10, "th")
        nth = f"{index}{suffix}"
    return f"{path}' {nth} entry" if path.endswith("s") else f"{path}'s {nth} entry"
