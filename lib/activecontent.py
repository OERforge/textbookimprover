"""What a part's files can do besides be read (the active-content report).

A structural check, TextbookImprover's own: it reads each file's
structure and runs nothing in it. It isn't a virus scan and doesn't say a
file is malicious: it names what a published source has no need of, so a
person can judge it before the book goes out.

- **Word, PowerPoint, and Excel files** (zipped XML): macros, Excel 4
  macro sheets, embedded objects and controls, relationships to files or
  addresses outside the file other than plain links (a template fetched
  as it opens, a frame, a subdocument), and fields that fetch or run
  (DDE, INCLUDETEXT, INCLUDEPICTURE). A chart's own workbook, which Word
  and PowerPoint keep among a file's embedded objects, is accepted.
- **OpenDocument files:** macros (Basic/, Scripts/), event listeners,
  embedded objects other than a chart, and applets, plug-ins, and frames.
- **PDFs** (pikepdf): an action on opening other than going to a page,
  document and page actions, JavaScript, attached files, forms (XFA
  among them), and launch, submit, import, and remote-go-to actions,
  rich media, movies, sounds, and 3D.
- **HTML pages and SVG pictures:** scripts, event handlers, javascript:
  and other script addresses, embedded frames, objects, and applets,
  forms, a refresh that sends the reader elsewhere, an SVG animation that
  sets a link, an SVG's foreignObject, and an SVG that declares entities,
  which can hold markup no tag shows.
- **An old binary Office file** (.doc, .ppt, .xls) is named as one this
  check can't read.

Each file is read with limits: no more than READ_LIMIT bytes of a page,
a picture, or a zip's member, and a zip's members counted.
"""

import os
import re
import zipfile
from html.parser import HTMLParser

READ_LIMIT = 32 * 1024 * 1024
MEMBERS_LIMIT = 20000
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

OOXML_EXTENSIONS = (".docx", ".docm", ".dotx", ".dotm", ".pptx", ".pptm", ".potx", ".potm",
                    ".ppsx", ".ppsm", ".xlsx", ".xlsm", ".xltx", ".xltm", ".xlam", ".ppam")
ODF_EXTENSIONS = (".odt", ".ott", ".odp", ".otp", ".ods", ".ots", ".odg", ".otg", ".odf")
OLD_OFFICE_EXTENSIONS = (".doc", ".dot", ".ppt", ".pot", ".pps", ".xls", ".xlt")
PAGE_EXTENSIONS = (".html", ".htm", ".xhtml")
EXTENSIONS = OOXML_EXTENSIONS + ODF_EXTENSIONS + OLD_OFFICE_EXTENSIONS + PAGE_EXTENSIONS \
    + (".pdf", ".svg")

REL = re.compile(rb"<Relationship\b[^>]*>")
FIELD = re.compile(rb"<w:instrText[^>]*>([^<]*)</w:instrText>|w:instr=\"([^\"]*)\"")
FIELD_WORDS = (b"DDEAUTO", b"DDE", b"INCLUDETEXT", b"INCLUDEPICTURE", b"IMPORT")
SCRIPT_SCHEMES = ("javascript:", "vbscript:", "livescript:", "data:text/html",
                  "data:application/xhtml", "data:image/svg+xml")
URL_ATTRIBUTES = ("href", "xlink:href", "src", "action", "formaction", "data", "poster",
                  "background", "lowsrc", "dynsrc", "codebase", "srcdoc",
                  # what an SVG animation sets an attribute to
                  "to", "from", "values", "by")
PDF_ACTIONS = ("/JavaScript", "/Launch", "/SubmitForm", "/ImportData", "/GoToR", "/GoToE",
               "/Rendition", "/Movie", "/Sound")
PDF_ANNOTATIONS = ("/RichMedia", "/FileAttachment", "/Movie", "/Sound", "/3D", "/Screen")


def _attr(tag, name):
    m = re.search(name + rb'\s*=\s*"([^"]*)"', tag) or re.search(name + rb"\s*=\s*'([^']*)'", tag)
    return m.group(1).decode("utf-8", "replace") if m else ""


def _cut(address):
    """An address without its query, fragment, or user name: what the
    report says of where a relationship leads."""
    text = "".join(ch for ch in address if ch.isprintable())
    text = re.sub(r"^([a-zA-Z][\w+.-]*://)[^/@]*@", r"\1", text)
    return re.split(r"[?#]", text, maxsplit=1)[0][:200]


class _Finding(dict):
    """{what: [count, an example]}, kept in the order found."""

    def add(self, what, example=""):
        if what in self:
            self[what][0] += 1
        else:
            self[what] = [1, example]

    def rows(self, inside=""):
        return [(inside, what, count, example) for what, (count, example) in self.items()]


def _read_member(archive, info):
    """A zip member's bytes, or None when it's bigger than the limit."""
    if info.file_size > READ_LIMIT:
        return None
    with archive.open(info) as fh:
        data = fh.read(READ_LIMIT + 1)
    return None if len(data) > READ_LIMIT else data


def ooxml(path):
    """A Word, PowerPoint, or Excel file's active parts: [(inside, what,
    count, example)]."""
    found = _Finding()
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MEMBERS_LIMIT:
            return [("", "too many members to check", len(infos), "")]
        names = [i.filename for i in infos]
        lower = [n.lower() for n in names]
        for name, low in zip(names, lower):
            if low.endswith(("vbaproject.bin", "vbadata.xml", "vbaprojectsignature.bin")):
                found.add("macros", name)
            elif "/macrosheets/" in low:
                found.add("Excel 4 macro sheets", name)
            elif "/activex/" in low or "/ctrlprops/" in low:
                found.add("controls", name)
        # A chart's workbook: an embedding a chart part's relationships
        # name, which Word and PowerPoint keep for the chart's data.
        charts = set()
        for info, low in zip(infos, lower):
            if "/charts/_rels/" in low and low.endswith(".rels"):
                data = _read_member(archive, info) or b""
                folder = os.path.dirname(os.path.dirname(info.filename))
                for tag in REL.findall(data):
                    target = _attr(tag, rb"Target")
                    if b'TargetMode="External"' not in tag and target:
                        charts.add(os.path.normpath(os.path.join(folder, target))
                                   .replace(os.sep, "/").lower())
        for name, low in zip(names, lower):
            if "/embeddings/" in low and low not in charts:
                found.add("embedded objects", name)
        for info, low in zip(infos, lower):
            if not low.endswith((".rels", ".xml")):
                continue
            data = _read_member(archive, info)
            if data is None:
                found.add("a part too big to check", info.filename)
                continue
            if low == "[content_types].xml":
                if b"macroEnabled" in data or b"vbaProject" in data:
                    found.add("macros", "declared in [Content_Types].xml")
                continue
            if low.endswith(".rels"):
                for tag in REL.findall(data):
                    if b'TargetMode="External"' not in tag:
                        continue
                    kind = _attr(tag, rb"Type").rsplit("/", 1)[-1]
                    if kind != "hyperlink":
                        found.add(f"outside {kind}", _cut(_attr(tag, rb"Target")))
                continue
            text = b" ".join(a or b for a, b in FIELD.findall(data)).upper()
            words = set(re.findall(rb"[A-Z]+", text))
            for word in FIELD_WORDS:
                if word in words:
                    found.add(f"field {word.decode()}", info.filename)
            if b"<ddeLink" in data or b":ddeLink" in data:
                found.add("DDE link", info.filename)
    return found.rows()


def odf(path):
    """An OpenDocument file's active parts."""
    found = _Finding()
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MEMBERS_LIMIT:
            return [("", "too many members to check", len(infos), "")]
        manifest = b""
        for info in infos:
            if info.filename == "META-INF/manifest.xml":
                manifest = _read_member(archive, info) or b""
        charts = {(_attr(tag, rb"manifest:full-path") or "").rstrip("/")
                  for tag in re.findall(rb"<manifest:file-entry\b[^>]*>", manifest)
                  if b"opendocument.chart" in tag}
        names = [i.filename for i in infos]
        # An object is a folder (Object 1/) or, an OLE object, a file
        # (Object 2); a chart is an object of its own kind, accepted.
        objects = sorted({n.split("/", 1)[0] for n in names if n.startswith("Object ")})
        for top in objects:
            if top not in charts:
                found.add("embedded objects", top)
        for info in infos:
            name = info.filename
            top = name.split("/", 1)[0]
            # A library's own lists (script-lc.xml, dialog-lb.xml) hold no
            # code; a module, a dialog, or a script in Scripts/ does.
            if top in ("Basic", "Scripts") and not name.endswith("/") and not re.search(
                    r"/(?:script|dialog)-l[bc]\.xml$", name):
                found.add("macros", name)
            if not name.endswith(".xml") or top in charts:
                continue
            data = _read_member(archive, info)
            if data is None:
                found.add("a part too big to check", name)
                continue
            for _ in re.finditer(rb"<script:event-listener\b", data):
                found.add("event listeners", name)
            for element, what in ((rb"draw:applet", "applets"), (rb"draw:plugin", "plug-ins"),
                                  (rb"draw:floating-frame", "frames")):
                for _ in re.finditer(rb"<" + element + rb"\b", data):
                    found.add(what, name)
            for tag in re.findall(rb"<draw:object(?:-ole)?\b[^>]*>", data):
                href = _attr(tag, rb"xlink:href")
                if re.match(r"[a-zA-Z][\w+.-]*:", href) or href.startswith(("/", "..")):
                    found.add("outside objects", _cut(href))
    return found.rows()


def pdf(path):
    """A PDF's active parts."""
    import pikepdf
    found = _Finding()
    with pikepdf.open(path) as doc:
        root = doc.Root
        if "/OpenAction" in root:
            action = root.OpenAction
            kind = str(action.get("/S", "")) if isinstance(action, pikepdf.Dictionary) else ""
            if kind and kind != "/GoTo":
                found.add("an action on opening", kind)
        if "/AA" in root:
            found.add("document actions", ", ".join(str(k) for k in root.AA.keys()))
        names = root.get("/Names")
        if isinstance(names, pikepdf.Dictionary):
            if "/JavaScript" in names:
                found.add("JavaScript", "named scripts")
            if "/EmbeddedFiles" in names:
                found.add("attached files", "in the name tree")
        if "/AcroForm" in root and isinstance(root.AcroForm, pikepdf.Dictionary):
            form = root.AcroForm
            found.add("a form", "with XFA" if "/XFA" in form
                      else f"{len(form.get('/Fields', []))} field(s)")
        # Every dictionary, an indirect object's and those written inside
        # it (an annotation's action is often direct), each reference
        # left to the loop that reaches its object.
        for obj in doc.objects:
            if isinstance(obj, pikepdf.Stream):
                obj = obj.stream_dict
            if not isinstance(obj, (pikepdf.Dictionary, pikepdf.Array)):
                continue
            waiting, seen = [(obj, 0)], 0
            while waiting and seen < 10000:
                here, depth = waiting.pop()
                seen += 1
                if isinstance(here, pikepdf.Dictionary):
                    _pdf_dictionary(here, found, here is obj and obj.is_indirect
                                    and obj.objgen == root.objgen)
                    children = here.values()
                elif isinstance(here, pikepdf.Array):
                    children = list(here)
                else:
                    continue
                if depth < 32:
                    waiting += [(child, depth + 1) for child in children
                                if isinstance(child, (pikepdf.Dictionary, pikepdf.Array))
                                and not child.is_indirect]
    return found.rows()


def _pdf_dictionary(obj, found, is_root):
    kind = str(obj.get("/S", ""))
    if kind in PDF_ACTIONS:
        found.add(f"{kind[1:]} actions")
    subtype = str(obj.get("/Subtype", ""))
    if subtype in PDF_ANNOTATIONS:
        found.add(f"{subtype[1:]} annotations")
    if "/AA" in obj and not is_root:
        found.add("actions on a page, a field, or an annotation")


class _Markup(HTMLParser):
    """A page's or an SVG's active parts, by its tags and attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = _Finding()

    def handle_starttag(self, tag, attrs):
        found = self.found
        tag = tag.lower()
        if tag == "script":
            src = dict(attrs).get("src")
            found.add("scripts", _cut(src) if src else "written inline")
        elif tag in ("iframe", "frame", "object", "embed", "applet", "portal", "frameset"):
            found.add(f"embedded {tag} elements", _cut(dict(attrs).get("src")
                                                       or dict(attrs).get("data") or ""))
        elif tag == "form":
            found.add("forms", _cut(dict(attrs).get("action") or ""))
        elif tag == "foreignobject":
            found.add("foreignObject elements, which can hold a page's markup")
        elif tag in ("set", "animate") and (dict(attrs).get("attributename") or "").lower() \
                in ("href", "xlink:href"):
            found.add("animations that set a link")
        elif tag == "meta" and (dict(attrs).get("http-equiv") or "").lower() == "refresh" \
                and "url" in (dict(attrs).get("content") or "").lower():
            found.add("a refresh that sends the reader elsewhere",
                      _cut(dict(attrs).get("content") or ""))
        for name, value in attrs:
            name = (name or "").lower()
            if name.startswith("on") and len(name) > 2:
                found.add("event handlers", f"{name} on <{tag}>")
            elif name in URL_ATTRIBUTES and value:
                plain = re.sub(r"[\x00-\x20]", "", value).lower()
                if plain.startswith(SCRIPT_SCHEMES):
                    found.add("script addresses", f"{name} on <{tag}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def unknown_decl(self, data):
        pass


def markup(path):
    """An HTML page's or an SVG's active parts."""
    with open(path, "rb") as fh:
        data = fh.read(READ_LIMIT + 1)
    if len(data) > READ_LIMIT:
        return [("", "too big to check", 1, "")]
    text = data.decode("utf-8", "replace")
    parser = _Markup()
    if re.search(r"<!ENTITY\b", text):
        parser.found.add("declared entities, which can hold markup no tag shows")
    try:
        parser.feed(text)
        parser.close()
    except (AssertionError, ValueError):
        parser.found.add("markup that couldn't be read whole")
    return parser.found.rows()


def check(path):
    """[(inside, what, count, example)] for one file, by its name and its
    first bytes; a file that can't be read is a finding too."""
    lower = path.lower()
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
        if lower.endswith(OLD_OFFICE_EXTENSIONS) or head == OLE:
            return [("", "an old binary Office file, which this check can't read", 1, "")]
        if lower.endswith(OOXML_EXTENSIONS):
            return ooxml(path)
        if lower.endswith(ODF_EXTENSIONS):
            return odf(path)
        if lower.endswith(".pdf"):
            return pdf(path)
        if lower.endswith(PAGE_EXTENSIONS + (".svg",)):
            return markup(path)
    except Exception as exc:  # a file that can't be read is said, never a traceback
        return [("", f"not read ({type(exc).__name__})", 1, "")]
    return []


def checked(name):
    """Whether check reads a file of this name."""
    return name.lower().endswith(EXTENSIONS)
