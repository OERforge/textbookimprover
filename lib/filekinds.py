"""What a file is, by its first bytes, and whether that's what its name
says.

A file a book names, or holds among its sources, is opened by programs
that trust its name: Pillow, librsvg, Poppler, Ghostscript, LuaTeX, a
browser, Pandoc's readers. A web page saved under a picture's name (a
site's error page, a sign-in form), a PDF or PostScript program named
.png, an archive, or a program are each something other than what the
name promises, and some of those programs act on what's inside. So a
file's first bytes are read and compared with its extension before any
program opens it:

    found = filekinds.sniff(head)         # "png", "html", "zip", ...
    why = filekinds.mismatch(path)        # None, or (found, role, expected)

A picture that's a picture of another kind (a PNG named .jpg) is a
naming slip, not a disguise; the caller says so, and a run goes on. Any
other mismatch stops it, but a deck's, which a deck's own reading names
and passes over (role "deck"). An extension this table doesn't know
isn't checked.

Copyright (C) 2026 Robert Szarka

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
import re

# How much of a file is read: enough for an SVG's root element after its
# declaration and comments, and for a PDF's header, which may follow up
# to 1,024 bytes of anything.
HEAD = 4096

# The kinds a picture may be, and the media type of each that a page can
# show (epubsource.sniff's).
PICTURES = ("png", "jpeg", "gif", "webp", "svg", "tiff", "bmp", "pdf", "postscript",
            "wmf", "emf", "jp2", "avif", "heic", "ico")
MEDIA_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif",
               "webp": "image/webp", "svg": "image/svg+xml"}

# What a name says a file is: (role, the kinds it may be).
EXPECTED = {
    ".png": ("picture", ("png",)), ".jpg": ("picture", ("jpeg",)),
    ".jpeg": ("picture", ("jpeg",)), ".jpe": ("picture", ("jpeg",)),
    ".gif": ("picture", ("gif",)), ".webp": ("picture", ("webp",)),
    ".svg": ("picture", ("svg",)), ".tif": ("picture", ("tiff",)),
    ".tiff": ("picture", ("tiff",)), ".bmp": ("picture", ("bmp",)),
    ".pdf": ("picture", ("pdf",)), ".eps": ("picture", ("postscript",)),
    ".ps": ("picture", ("postscript",)), ".wmf": ("picture", ("wmf",)),
    ".emf": ("picture", ("emf",)), ".jp2": ("picture", ("jp2",)),
    ".avif": ("picture", ("avif",)), ".heic": ("picture", ("heic",)),
    ".ico": ("picture", ("ico",)), ".svgz": ("picture", ("gzip",)),
    ".mp4": ("medium", ("mp4",)), ".m4v": ("medium", ("mp4",)),
    ".m4a": ("medium", ("mp4",)), ".mov": ("medium", ("mp4", "quicktime")),
    ".webm": ("medium", ("matroska",)), ".mkv": ("medium", ("matroska",)),
    ".mp3": ("medium", ("mp3",)), ".ogg": ("medium", ("ogg",)),
    ".oga": ("medium", ("ogg",)), ".ogv": ("medium", ("ogg",)),
    ".opus": ("medium", ("ogg",)), ".wav": ("medium", ("wav",)),
    ".flac": ("medium", ("flac",)), ".vtt": ("medium", ("text",)),
    ".docx": ("source", ("zip",)), ".odt": ("source", ("zip",)),
    ".epub": ("source", ("zip",)), ".doc": ("source", ("ole",)),
    # A deck's own reading names one that isn't what its name says, with
    # what it is, before LibreOffice or python-pptx opens it (decksave,
    # deckrun), and converts the rest.
    ".pptx": ("deck", ("zip",)), ".odp": ("deck", ("zip",)), ".ppt": ("deck", ("ole",)),
    ".md": ("source", ("text",)), ".markdown": ("source", ("text",)),
    ".html": ("source", ("text",)), ".htm": ("source", ("text",)),
    ".xhtml": ("source", ("text",)), ".adoc": ("source", ("text",)),
    ".asciidoc": ("source", ("text",)), ".tex": ("source", ("text",)),
    ".ltx": ("source", ("text",)), ".sty": ("source", ("text",)),
    ".cls": ("source", ("text",)), ".bib": ("source", ("text",)),
}

# Kinds of file with no business under a picture's or a medium's name,
# said in words.
WORDS = {
    "html": "a web page (HTML)", "xml": "XML", "pdf": "a PDF",
    "postscript": "PostScript", "zip": "a ZIP archive", "gzip": "a gzip archive",
    "tar": "a tar archive", "7z": "a 7-Zip archive", "rar": "a RAR archive",
    "bzip2": "a bzip2 archive", "xz": "an xz archive", "ole": "an old Office file",
    "elf": "a program (ELF)", "pe": "a Windows program", "macho": "a macOS program",
    "script": "a script", "text": "text", "png": "a PNG picture",
    "jpeg": "a JPEG picture", "gif": "a GIF picture", "webp": "a WebP picture",
    "svg": "an SVG picture", "tiff": "a TIFF picture", "bmp": "a BMP picture",
    "wmf": "a WMF picture", "emf": "an EMF picture", "jp2": "a JPEG 2000 picture",
    "avif": "an AVIF picture", "heic": "a HEIC picture", "ico": "an icon",
    "mp4": "an MP4 file", "quicktime": "a QuickTime file", "matroska": "a WebM file",
    "mp3": "an MP3 file", "ogg": "an Ogg file", "wav": "a WAV file",
    "flac": "a FLAC file", None: "nothing this check knows", "empty": "empty",
}

_SVG = re.compile(rb"<svg[\s>/]", re.I)
_HTML = re.compile(rb"<(!doctype\s+html|html[\s>]|head[\s>]|body[\s>]|meta[\s>]|"
                   rb"title[\s>]|script[\s>]|div[\s>]|p[\s>]|a\s|iframe[\s>])", re.I)
_FTYP_HEIC = (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


def sniff(head):
    """The kind of file head, its first bytes, begins: a name from WORDS,
    "empty", or None when nothing here knows it."""
    if not head:
        return "empty"
    signatures = (
        (b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg"), (b"GIF87a", "gif"),
        (b"GIF89a", "gif"), (b"II*\x00", "tiff"), (b"MM\x00*", "tiff"),
        (b"\xd7\xcd\xc6\x9a", "wmf"), (b"\x00\x00\x00\x0cjP  \r\n\x87\n", "jp2"),
        (b"\x00\x00\x01\x00", "ico"), (b"\xc5\xd0\xd3\xc6", "postscript"),
        (b"%!", "postscript"), (b"\x1a\x45\xdf\xa3", "matroska"), (b"OggS", "ogg"),
        (b"fLaC", "flac"),
        (b"PK\x03\x04", "zip"), (b"PK\x05\x06", "zip"), (b"PK\x07\x08", "zip"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"), (b"\x1f\x8b", "gzip"),
        (b"7z\xbc\xaf\x27\x1c", "7z"), (b"Rar!\x1a\x07", "rar"),
        (b"\xfd7zXZ\x00", "xz"), (b"\x7fELF", "elf"),
        (b"\xcf\xfa\xed\xfe", "macho"), (b"\xce\xfa\xed\xfe", "macho"),
        (b"\xca\xfe\xba\xbe", "macho"), (b"#!", "script"))
    for magic, kind in signatures:
        if head.startswith(magic):
            return kind
    # Signatures of a few letters, which text can begin with too, each
    # held to more of its format than its letters.
    if head[:3] == b"ID3" and len(head) > 4 and head[3] in (2, 3, 4) and head[4] < 0x10:
        return "mp3"
    if head[:3] == b"BZh" and len(head) > 3 and head[3:4] in b"123456789":
        return "bzip2"
    if head[:2] == b"MZ" and len(head) >= 64:
        at = int.from_bytes(head[60:64], "little")
        if head[at:at + 4] == b"PE\x00\x00" or b"\x00" in head[2:64]:
            return "pe"
    if head[:4] == b"RIFF" and len(head) >= 12:
        return {b"WEBP": "webp", b"WAVE": "wav"}.get(head[8:12])
    if head[:2] == b"BM" and len(head) >= 14 and head[6:10] == b"\x00\x00\x00\x00":
        return "bmp"
    if head[:4] == b"\x01\x00\x00\x00" and head[40:44] == b" EMF":
        return "emf"
    if head[:2] in (b"\x01\x00", b"\x02\x00") and head[2:4] == b"\x09\x00":
        return "wmf"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return "avif"
        if brand in _FTYP_HEIC:
            return "heic"
        return "quicktime" if brand == b"qt  " else "mp4"
    if head[:1] == b"\x00" and head[4:8] in (b"moov", b"mdat", b"wide", b"free", b"skip"):
        return "quicktime"
    if head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xe3"):
        return "mp3"
    if head.startswith(b"%PDF-"):
        return "pdf"
    if b"tar\x00" in head[257:263] or head[257:262] == b"ustar":
        return "tar"
    # Text: a byte-order mark, or no NUL in what was read.
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "text"
    if b"\x00" in head:
        return None
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if _SVG.search(text) and text.lstrip().startswith((b"<?xml", b"<!--", b"<svg", b"<!DOCTYPE svg",
                                                      b"<!doctype svg")):
        return "svg"
    if _HTML.match(text) or re.match(rb"<!--.*?-->\s*<(!doctype\s+html|html)", text, re.I | re.S):
        return "html"
    if text.startswith(b"<?xml"):
        return "html" if re.search(rb"<html[\s>]", text, re.I) else "xml"
    return "text"


def read_head(path):
    """A file's first HEAD bytes, or None where it can't be read."""
    try:
        with open(path, "rb") as fh:
            return fh.read(HEAD)
    except OSError:
        return None


def expected(path):
    """(role, kinds) a file's name says it is, or None for a name this
    table doesn't know."""
    return EXPECTED.get(os.path.splitext(path)[1].lower())


def mismatch(path):
    """(found, role, expected kinds) when a file isn't what its name says,
    or None: a known name whose first bytes are another kind of file. A
    source in text may be any text, a page in HTML among them; a picture's
    own name is the only one an SVG or a web page passes as text for."""
    wanted = expected(path)
    if wanted is None:
        return None
    head = read_head(path)
    if head is None:
        return None
    role, kinds = wanted
    found = sniff(head)
    if found in kinds:
        return None
    # A PDF's header may follow up to 1,024 bytes of anything.
    if "pdf" in kinds and b"%PDF-" in head[:1024]:
        return None
    # Text is any text: a page, a program's source, TeX's "%!TEX" line.
    if "text" in kinds and found in ("text", "html", "xml", "svg", "script", "postscript"):
        return None
    return found, role, kinds


def picture_slip(found, role):
    """Whether a mismatch is a picture of another kind under a picture's
    name: a naming slip, which a run warns of, not a disguise."""
    return role == "picture" and found in PICTURES


# What a name promises, where its kind's word isn't the name's own.
NAMED = {".docx": "a Word file", ".doc": "a Word file", ".pptx": "a PowerPoint deck",
         ".ppt": "a PowerPoint deck", ".odp": "an Impress deck", ".odt": "a Writer file",
         ".epub": "an EPUB", ".svgz": "a compressed SVG picture", ".vtt": "WebVTT captions",
         ".md": "Markdown", ".markdown": "Markdown", ".html": "a web page",
         ".htm": "a web page", ".xhtml": "a web page", ".adoc": "AsciiDoc",
         ".asciidoc": "AsciiDoc", ".tex": "LaTeX", ".ltx": "LaTeX",
         ".sty": "a LaTeX package", ".cls": "a LaTeX class", ".bib": "a bibliography",
         ".eps": "an EPS picture", ".ps": "a PostScript picture", ".pdf": "a PDF",
         ".mp4": "an MP4 video", ".m4v": "an MP4 video", ".m4a": "an MP4 audio file",
         ".mov": "a QuickTime video", ".webm": "a WebM video", ".mkv": "a Matroska video"}


def said(path, found, role, kinds, shown=None):
    """What to say of a file that isn't what its name says."""
    name = shown or path
    what = NAMED.get(os.path.splitext(path)[1].lower()) \
        or " or ".join(WORDS.get(k, k) for k in kinds)
    return (f"{name} is named as {what}, and its first bytes are "
            f"{WORDS.get(found, found)}")


def media_type(head):
    """The media type of a picture a page can show, by head, or None:
    PNG, JPEG, GIF, WebP, and SVG (epubsource.sniff's answer)."""
    return MEDIA_TYPES.get(sniff(head))
