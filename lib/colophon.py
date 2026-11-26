"""
colophon.py -- the page generate: colophon in a book's contents makes: its
credits and rights, from the project's settings, and its production
statement, how this copy was made, from what the run knows of itself.

The credits are what a copyright page would hold: the title and the
subtitle, the people by their roles, each name linked to its ORCID iD,
the publisher and the series, the copyright line and the license by name
and deed, the ISBNs, the DOI, the book's address, where to write about
it, who paid for it, and the credit someone reusing it should give. The
production statement names TextbookImprover's version and commit,
Pandoc's version, and the day of the run's moment (SOURCE_DATE_EPOCH, so
that a build made again under it says the same), in a div of class
oer-colophon, which a comparison of two builds can set apart; a PDF's
adds the TeX distribution and the faces its pages are set in, which
LaTeX finds as it sets them (FACES) and names on its next run.

The words are English, marked as such on a page in another language, as
a license's sentence on a page is.

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

import os
import time

import identifiers
import licenses
import people

CLASS = "oer-colophon"
HOME = "https://github.com/OERforge/textbookimprover"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
# The formats an ISBN may be given for, as a reader would name them.
ISBN_FORMATS = (("epub", "EPUB"), ("pdf", "PDF"), ("paperback", "paperback"),
                ("hardcover", "hardcover"))
TERMS = {code: term for term, code in people.RELATORS.items()}


# -- Pandoc's blocks ----------------------------------------------------------

def words(text):
    out = []
    for index, word in enumerate(licenses.one_line(text).split()):
        if index:
            out.append({"t": "Space"})
        out.append({"t": "Str", "c": word})
    return out


def link(inlines, address):
    return {"t": "Link", "c": [["", [], []], inlines, [address, ""]]}


def para(*runs):
    """A paragraph of runs, each text (made words) or a list of inlines."""
    inlines = []
    for run in runs:
        inlines += words(run) if isinstance(run, str) else run
    # Words given apart are joined by a space where neither side has one:
    # "By", a name.
    out = []
    for inline in inlines:
        if out and inline["t"] != "Space" and out[-1]["t"] != "Space" \
                and not (inline["t"] == "Str" and inline["c"][:1] in ".,:;)")\
                and not (out[-1]["t"] == "Str" and out[-1]["c"][-1:] == "("):
            out.append({"t": "Space"})
        out.append(inline)
    return {"t": "Para", "c": out}


def joined(items):
    """Lists of inlines as "A", "A and B", or "A, B, and C"."""
    out = []
    for index, item in enumerate(items):
        if index and len(items) > 2:
            out.append({"t": "Str", "c": ","})
        if index:
            out.append({"t": "Space"})
        if index == len(items) - 1 and index:
            out += [{"t": "Str", "c": "and"}, {"t": "Space"}]
        out += item
    return out


def person(entry):
    """A person's or an organization's name as inlines, linked to its
    ORCID iD or ROR ID where it has one."""
    name = words(people.name(entry))
    if isinstance(entry, dict):
        for key, check in (("orcid", people.orcid), ("ror", people.ror)):
            if entry.get(key):
                try:
                    return [link(name, check(entry[key]))]
                except ValueError:
                    pass
    return name


def named(entries):
    return joined([person(entry) for entry in entries or [] if people.name(entry)])


def sentence(inlines):
    """inlines with a full stop after them, where the last word has none."""
    last = next((i for i in reversed(inlines) if i["t"] == "Str"), None)
    if last is not None and last["c"][-1:] in ".!?":
        return inlines
    return inlines + [{"t": "Str", "c": "."}]


# -- the credits --------------------------------------------------------------

def role_term(code):
    term = TERMS.get(code, code)
    return term[:1].upper() + term[1:]


def license_runs(license_id, noted=False):
    """The license as a sentence's inlines: its name linked to its deed,
    for one this module's licenses knows, or as it's given."""
    text = licenses.one_line(license_id)
    if not text:
        return []
    found = licenses.known(text)
    if found:
        said = (words("dedicated to the public domain under") if found[2]
                else words("licensed under")) + [{"t": "Space"}, link(words(found[0]), found[1])]
    else:
        said = words("under the license " + text)
    if noted:
        return words("Except where otherwise noted,") + [{"t": "Space"}] + said
    said[0] = dict(said[0], c=said[0]["c"][:1].upper() + said[0]["c"][1:])
    return said


def address_of(project):
    """Where the book is found: its DOI's address, or its own."""
    for key, check in (("doi", identifiers.doi), ("url", identifiers.url)):
        if str(project.get(key) or "").strip():
            try:
                value = check(project[key])
            except ValueError:
                continue
            return "https://doi.org/" + value if key == "doi" else value
    return ""


def reuse_credit(project, title):
    """The credit to give the book, as Creative Commons asks it be given
    (its title, linked to where it's found, its authors, or its publisher
    where it names none, and its license), for a license of theirs that
    asks for one; None for CC0 or any other license."""
    found = licenses.known(project.get("license"))
    if not found or found[2]:
        return None
    by = project.get("authors") or ([project["publisher"]] if people.name(
        project.get("publisher")) else [])
    address = address_of(project)
    work = [{"t": "Emph", "c": words(title)}]
    if address:
        work = [link(work, address)]
    runs = ["To reuse this book, credit it as:", work]
    if named(by):
        runs += ["by", named(by)]
    runs += [[{"t": "Str", "c": ","}], "licensed under",
             [link(words(licenses.short_name(project.get("license"))), found[1])]]
    return para(*runs, ".")


def credits(project):
    """The credits and rights, as blocks."""
    out = []
    title = licenses.one_line(project.get("title"))
    subtitle = licenses.one_line(project.get("subtitle"))
    if title:
        out.append(para([{"t": "Emph", "c": words(title + (": " + subtitle if subtitle
                                                           else ""))}]))
    for key, label in (("authors", "By"), ("adapters", "Adapted by"),
                       ("editors", "Edited by")):
        if named(project.get(key)):
            out.append(para(label, sentence(named(project[key]))))
    roles = {}
    for entry in project.get("contributors") or []:
        code = people.relator(entry.get("role")) if isinstance(entry, dict) else None
        if code and people.name(entry):
            roles.setdefault(code, []).append(entry)
    for code, entries in roles.items():
        term = role_term(code)
        if len(entries) > 1 and " " not in term:
            term += "s"
        out.append(para(term + ":", sentence(named(entries))))
    publisher = project.get("publisher")
    place = project.get("place") or {}
    where = ", ".join(licenses.one_line(place.get(k)) for k in ("city", "country")
                      if licenses.one_line(place.get(k)))
    if people.name(publisher):
        out.append(para("Published by", sentence(person(publisher)
                                                 + (words(", " + where) if where else []))))
    series = project.get("series") or {}
    if licenses.one_line(series.get("name")):
        position = licenses.one_line(series.get("position"))
        out.append(para("Part of the series", [{"t": "Emph", "c": words(series["name"])}],
                        (", number " + position + ".") if position else "."))
    line = licenses.copyright_line(project.get("copyright"), project.get("published"))
    rights = license_runs(project.get("license"), licenses.exceptions(
        project.get("licenses"), project.get("license")))
    if line or rights:
        out.append(para(*([line if line.endswith(".") else line + "."] if line else []),
                        sentence(rights) if rights else []))
    isbn = project.get("isbn") or {}
    given = []
    for key, label in ISBN_FORMATS:
        try:
            value = identifiers.isbn(isbn[key]) if str(isbn.get(key) or "").strip() else ""
        except ValueError:
            value = ""
        if value:
            given.append(words(f"ISBN {value} ({label})"))
    if given:
        out.append(para(sentence(joined(given))))
    if str(project.get("doi") or "").strip():
        try:
            doi = "https://doi.org/" + identifiers.doi(project["doi"])
            out.append(para("DOI:", [link(words(doi), doi)]))
        except ValueError:
            pass
    if str(project.get("url") or "").strip():
        try:
            address = identifiers.url(project["url"])
            out.append(para("Online at", [link(words(address), address)], "."))
        except ValueError:
            pass
    if str(project.get("contact") or "").strip():
        try:
            contact = identifiers.contact(project["contact"])
            target = contact if "://" in contact else "mailto:" + contact
            out.append(para("To report a mistake, write to", [link(words(contact), target)],
                            "."))
        except ValueError:
            pass
    funders = []
    for entry in project.get("funding") or []:
        funder = entry.get("funder") if isinstance(entry, dict) else entry
        if not people.name(funder):
            continue
        runs = person(funder)
        award = entry.get("award") if isinstance(entry, dict) else None
        if isinstance(award, dict):
            award = licenses.one_line(" ".join(str(award.get(k) or "") for k in
                                               ("number", "title")))
        if licenses.one_line(award):
            runs += [{"t": "Space"}] + words("(award " + licenses.one_line(award) + ")")
        funders.append(runs)
    if funders:
        out.append(para("Funded by", sentence(joined(funders))))
    credit = reuse_credit(project, title)
    if credit and title:
        out.append(credit)
    return out


# -- the production statement -------------------------------------------------

def day(moment):
    """The day of a moment in seconds, UTC, as "November 26, 2026"."""
    when = time.gmtime(int(moment))
    return f"{MONTHS[when.tm_mon - 1]} {when.tm_mday}, {when.tm_year}"


def moment_now(environ=None):
    """The run's moment: SOURCE_DATE_EPOCH, which a run gives every
    program it starts, or now for a program run by hand."""
    value = (os.environ if environ is None else environ).get("SOURCE_DATE_EPOCH", "").strip()
    return int(value) if value.isdigit() else int(time.time())


def made_with(software, pandoc, moment):
    """"Made with TextbookImprover 0.11 (commit c9dff55) and Pandoc 3.14 on
    November 26, 2026." software is tiversion's version, commit, and
    changed; pandoc a version's numbers."""
    commit = software.get("commit") or "none"
    said = ""
    if commit != "none":
        said = f"commit {commit[:7]}" + (", with changes" if software.get("changed") == "yes"
                                         else "")
    runs = ["Made with", [link(words("TextbookImprover"), HOME)],
            str(software.get("version") or "") + (f" ({said})" if said else "")]
    if pandoc:
        runs.append("and Pandoc " + ".".join(str(n) for n in pandoc))
    runs.append("on " + day(moment) + ".")
    return para(*runs)


# The LaTeX a PDF's preamble gets when it sets a colophon: a count, as each
# page is shipped out, of the fonts its glyphs come from, named by their
# families as luaotfload read them from the fonts' own files (a HarfBuzz
# font's typographic family, or its family, from its face's names; any
# other's from its metadata), opening no file, which LaTeX's list of what it
# read would name, in the order they're first used; written
# to the .aux at the end, where the next run reads it as \OERFacesUsed,
# and a rerun asked for where it differs from what that run read. Only a
# name's letters, digits, spaces, and . - + are kept, since a font's file
# is the font maker's to fill. Lua inside \directlua can hold no percent
# sign, which TeX takes for a comment, and no tilde, which it makes a
# space: the patterns are made from string.char.
FACES = r"""\ifdefined\directlua
\directlua{
  oerfaces = { order = {}, seen = {}, named = {} }
  local GLYPH, HLIST, VLIST, DISC = node.id("glyph"), node.id("hlist"), node.id("vlist"), node.id("disc")
  local function clean(text)
    local out = {}
    for index = 1, string.len(text) do
      local b = string.byte(text, index)
      if (b >= 48 and b <= 57) or (b >= 65 and b <= 90) or (b >= 97 and b <= 122)
          or b == 32 or b == 43 or b == 45 or b == 46 then
        table.insert(out, string.char(b))
      end
    end
    return table.concat(out)
  end
  local function family(id)
    if oerfaces.named[id] then return oerfaces.named[id] end
    local f = font.getfont(id) or {}
    local name = nil
    local face = f.hb and f.hb.shared and f.hb.shared.face
    if face then
      local ok, typographic = pcall(face.get_name, face, 16)
      local ok2, plain = pcall(face.get_name, face, 1)
      name = (ok and typographic) or (ok2 and plain) or nil
    elseif f.shared and f.shared.rawdata and f.shared.rawdata.metadata then
      name = f.shared.rawdata.metadata.familyname
    end
    name = clean(name or f.fullname or f.name or "")
    oerfaces.named[id] = name
    return name
  end
  local function walk(head)
    for n in node.traverse(head) do
      if n.id == GLYPH then
        local name = family(n.font)
        if name and not (name == "") and not oerfaces.seen[name] then
          oerfaces.seen[name] = true
          table.insert(oerfaces.order, name)
        end
      elseif n.id == HLIST or n.id == VLIST then
        if n.head then walk(n.head) end
      elseif n.id == DISC then
        if n.replace then walk(n.replace) end
      end
    end
  end
  luatexbase.add_to_callback("pre_shipout_filter", function(head)
    walk(head)
    return true
  end, "oer.colophon.faces")
  function oerfaces.line()
    local names = oerfaces.order
    local count = 0
    for _ in pairs(names) do count = count + 1 end
    if count == 0 then return "" end
    if count == 1 then return names[1] end
    if count == 2 then return names[1] .. " and " .. names[2] end
    return table.concat(names, ", ", 1, count - 1) .. ", and " .. names[count]
  end
  function oerfaces.distribution()
    local banner = status.banner or ""
    local open = string.find(banner, "(", 1, true)
    local close = open and string.find(banner, ")", open, true)
    if open and close then return clean(string.sub(banner, open + 1, close - 1)) end
    return ""
  end
  function oerfaces.finish()
    local line = oerfaces.line()
    local before = token.get_macro("OERFacesUsed")
    if not (before == line) then
      texio.write_nl("term and log", "Package TextbookImprover Warning: The colophon's faces have changed. Rerun to name them.")
      texio.write_nl("term and log", "")
    end
  end
}
\makeatletter
\AddToHook{enddocument/afterlastpage}{\directlua{oerfaces.finish()}%
  \if@filesw\immediate\write\@mainaux{\string\gdef\string\OERFacesUsed{\directlua{tex.sprint(-2, oerfaces.line())}}}\fi}
\makeatother
\newcommand\OERColophonSet{Set with LuaLaTeX\directlua{
    local d = oerfaces.distribution()
    if not (d == "") then tex.sprint(-2, " from " .. d) end}%
  \ifdefined\OERFacesUsed\ifx\OERFacesUsed\empty\else\space in \OERFacesUsed\fi\fi.}
\fi
"""


def this_run():
    """(software, pandoc, moment) as this run knows them: TextbookImprover's
    version, commit, and changes (the run's one answer, tiversion's
    one_commit), Pandoc's version, and the run's moment."""
    import pandocversion
    import tiversion
    commit, changed = tiversion.one_commit()
    return ({"version": tiversion.VERSION, "commit": commit, "changed": changed},
            pandocversion.version(), moment_now())


def blocks(project, software, pandoc, moment, latex=False):
    """The colophon's body, after its heading: the credits, and the
    production statement in a div of class oer-colophon, a PDF's with its
    TeX and faces (latex, FACES in the preamble). In a div marked English
    where the book's language is another."""
    production = [made_with(software, pandoc, moment)]
    if latex:
        production.append({"t": "Para", "c": [{"t": "RawInline",
                                                "c": ["latex", "\\OERColophonSet"]}]})
    body = credits(project) + [{"t": "Div", "c": [["", [CLASS], []], production]}]
    language = str(project.get("language") or "").strip().lower()
    if language and language.split("-")[0] != "en":
        return [{"t": "Div", "c": [["", [], [["lang", "en"]]], body]}]
    return body
