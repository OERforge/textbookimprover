#!/usr/bin/env python3
"""
import-files.py -- bring what a part's pages name into the part, so a
run reads it: the names that don't name their files as every reader
would, a file named outside the part, and a picture named by URL.

    python3 util/import-files.py --dry-run          # say what it would do
    python3 util/import-files.py                    # do it
    python3 util/import-files.py --part slides --from ../shared --fetch

Run it from the project's folder, or give -d. It reads the part's
Markdown, HTML, and AsciiDoc pages (src/<part>/), as written, and for
each picture or file a page names:

  - A path with a backslash (assets\\figure.png) is written with forward
    slashes, and one in another case than its file's (Figure.PNG for
    figure.png) in its file's case.
  - A picture of one kind under another kind's name (a PNG named .jpg)
    is renamed to its own kind's extension, and each page naming it
    names it so.
  - A file outside the part (a full path, a file: URL, a name leading
    out of src/<part>/, another part's) is copied into
    src/<part>/imported/ when it's under a folder --from names, and the
    page names the copy. Without --from it's named, and left.
  - A picture named by URL is fetched with --fetch, saved into
    src/<part>/remote/ under its hash and its own kind's extension, and
    the page names the copy. Without --fetch it's named, and left.

What's changed is kept first in originals/<part>/, by its path in the
part: each page as it was, and each picture renamed. Each change is a
row of originals/<part>/import-record.csv: the page, the name as it
was and as it is, what was done, where a copy came from, and its
SHA-256. A sidecar row keyed by a name that changed is named, to be
keyed by the new one.

WHAT IT TAKES IN

Nothing is copied or fetched that convert.py would stop on: a file's
first bytes must be what its name says, a kind TextbookImprover knows
(a picture, a medium, a document), and a copy from outside a folder no
dot name leads into below the folder --from names (so not a key in
.ssh/); --from the root, or a folder that holds your home folder, is
refused. A fetch asks for
http: or https: alone, sends no cookie or password, follows up to five
redirects, each checked again, takes no more than 50 MB, waits no more
than a minute for each answer, and refuses an address that isn't on the
public internet (this machine, its network, a link-local address),
checked before it connects and of the address it connected to. Through
a proxy, the proxy is what connects, so only the first check is made. A
picture asked for over http:, at its own address or a redirect's, is
fetched with a warning, since anyone on the way could have answered.

A LaTeX book's \\input and pictures, and a Word file's pictures, aren't
read: a LaTeX book's names are its own to change, and a Word file's
pictures are inside it.

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

import argparse
import csv
import datetime
import hashlib
import html
import http.client
import ipaddress
import os
import re
import shutil
import socket
import ssl
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lib"))

import filekinds                                     # noqa: E402
import projectpaths                                  # noqa: E402
from names import by_url, case_match                 # noqa: E402

PAGE_EXTENSIONS = (".md", ".markdown", ".html", ".htm", ".xhtml", ".adoc", ".asciidoc")
MAX_BYTES = 50 * 1024 * 1024
TIMEOUT = 60
REDIRECTS = 5
AGENT = "TextbookImprover-import-files (+https://github.com/OERforge/textbookimprover)"
RECORD = "import-record.csv"
RECORD_FIELDS = ("date", "page", "was", "now", "what", "from", "sha256")


class Stop(Exception):
    """Why something can't be brought in, as a clause."""


def say(text=""):
    print(text, flush=True)


# -- what a page names -------------------------------------------------------
#
# Each reference is found where it's written, so the page can be changed
# there and nowhere else: (start, end) of the name in the page's text,
# the name, its context ("picture", "link", or "either" for a Markdown
# reference definition), and how it's written ("md", "angle", "html",
# "adoc"). Code, comments, and scripts are passed over.

MD_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*\n.*?^[ \t]{0,3}\1[ \t]*$", re.M | re.S)
MD_CODE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)
HTML_SKIP = re.compile(r"<!--.*?-->|<script\b.*?</script\s*>", re.I | re.S)
ADOC_SKIP = re.compile(r"^(-{4,}|\.{4,}|/{4,})[ \t]*$.*?^\1[ \t]*$", re.M | re.S)
ADOC_CODE = re.compile(r"`[^`\n]+`")
MD_DEST = re.compile(
    r"(!?)\[(?:[^\[\]\\]|\\.|\[(?:[^\[\]\\]|\\.)*\])*\]\(\s*"
    r"(?:<([^<>\n]*)>|((?:[^\s()<>\\]|\\.|\((?:[^\s()\\]|\\.)*\))+))", re.S)
MD_DEFINITION = re.compile(r"^[ ]{0,3}\[[^\]\n]+\]:[ \t]*(?:<([^<>\n]*)>|(\S+))", re.M)
TAG = re.compile(r"<[a-zA-Z][^<>]*>")
ATTRIBUTE = re.compile(r"""\b(src|href|poster|data|srcset)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""",
                       re.I)
STYLE = re.compile(r"""\bstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.I | re.S)
CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s"']*))\s*\)""", re.I)
# The elements whose src, poster, or srcset is a picture or a medium they
# show; another's (an <iframe>'s page, a <script>) is a file it links to.
SHOWS = ("img", "video", "audio", "source", "picture", "image", "input")
ADOC_MACRO = re.compile(r"\b(image|video|audio|link)::?([^\s\[\]]+)\[")


def masked(text, patterns):
    """text with what patterns match blanked, its length and lines kept."""
    for pattern in patterns:
        text = pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    return text


def html_references(text, plain, offset=0):
    """What HTML (plain, its comments and scripts blanked) names."""
    found = []

    def css(start, value):
        for url in CSS_URL.finditer(value):
            group = next(g for g in (1, 2, 3) if url.group(g) is not None)
            found.append((start + url.start(group), start + url.end(group),
                          url.group(group), "picture", "html"))
    for tag in TAG.finditer(plain):
        body = text[tag.start():tag.end()]
        shows = re.match(r"<([a-zA-Z][\w-]*)", body).group(1).lower() in SHOWS
        for attribute in ATTRIBUTE.finditer(body):
            group = next(g for g in (2, 3, 4) if attribute.group(g) is not None)
            start = offset + tag.start() + attribute.start(group)
            value = attribute.group(group)
            name = attribute.group(1).lower()
            if name == "srcset":
                at = 0
                for candidate in value.split(","):
                    word = candidate.strip().split(" ")[0] if candidate.strip() else ""
                    if word:
                        where = value.index(word, at)
                        found.append((start + where, start + where + len(word), word,
                                      "picture", "html"))
                        at = where + len(word)
                    else:
                        at += len(candidate) + 1
                continue
            found.append((start, start + len(value), value,
                          "picture" if shows and name != "href" else "link", "html"))
        for style in STYLE.finditer(body):
            group = 1 if style.group(1) is not None else 2
            css(offset + tag.start() + style.start(group), style.group(group))
    for block in STYLE_BLOCK.finditer(plain):
        css(offset + block.start(1), text[block.start(1):block.end(1)])
    return found


def references(text, extension):
    """Every picture and file a page's text names, where it's written."""
    found = []
    if extension in (".html", ".htm", ".xhtml"):
        return html_references(text, masked(text, [HTML_SKIP]))
    if extension in (".adoc", ".asciidoc"):
        plain = masked(text, [ADOC_SKIP, ADOC_CODE])
        for macro in ADOC_MACRO.finditer(plain):
            found.append((macro.start(2), macro.end(2), macro.group(2),
                          "link" if macro.group(1) == "link" else "picture", "adoc"))
        return found
    plain = masked(text, [MD_FENCE, MD_CODE, HTML_SKIP])
    for dest in MD_DEST.finditer(plain):
        group = 2 if dest.group(2) is not None else 3
        found.append((dest.start(group), dest.end(group), text[dest.start(group):dest.end(group)],
                      "picture" if dest.group(1) else "link",
                      "angle" if group == 2 else "md"))
    for definition in MD_DEFINITION.finditer(plain):
        group = 1 if definition.group(1) is not None else 2
        found.append((definition.start(group), definition.end(group),
                      text[definition.start(group):definition.end(group)], "either",
                      "angle" if group == 1 else "md"))
    found.extend(html_references(text, plain))
    return found


def as_written(value, how):
    """The name a reference gives, as a file's path: unescaped."""
    if how == "html":
        value = html.unescape(value)
    elif how == "md":
        value = re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", value) if "\\" in value and not \
            re.search(r"\\[A-Za-z0-9 ]", value) else value
    return value


def written(name, how, was):
    """name written as the reference was: percent-encoded where it
    was, or where Markdown needs it; HTML's ampersands and quotes
    escaped in HTML."""
    if "%" in was or (how in ("md", "adoc") and re.search(r"[\s()<>]", name)):
        name = urllib.parse.quote(name, safe="/#?=&+-._~!$'*,;:@")
    if how == "html":
        name = html.escape(name, quote=True)
    return name


# -- the project -------------------------------------------------------------

def within(folder, path):
    folder, path = os.path.realpath(folder), os.path.realpath(path)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def sha256(path=None, data=None):
    digest = hashlib.sha256()
    if data is not None:
        digest.update(data)
    else:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def pages_of(source):
    """A part's pages: its Markdown, HTML, and AsciiDoc files, not a dot
    name, a backup, or what a link leads to."""
    found = []
    for folder, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                         and not os.path.islink(os.path.join(folder, d)))
        for name in sorted(files):
            path = os.path.join(folder, name)
            if name.startswith((".", "#", "~$")) or name.endswith("~") \
                    or os.path.islink(path):
                continue
            if os.path.splitext(name)[1].lower() in PAGE_EXTENSIONS:
                found.append(path)
    return found


class Import:
    """What the part's pages name that a run would stop on, and what
    to do with each: worked out by plan(), done by execute()."""

    def __init__(self, root, part, sources_from, fetch, fetcher=None):
        self.root = os.path.realpath(root)
        self.project = projectpaths.of(self.root)
        self.part = self.project.part(part)
        self.source = os.path.realpath(self.project.sources(self.part))
        self.originals = os.path.join(self.root, "originals", self.part)
        self.sources_from = [os.path.realpath(f) for f in sources_from]
        self.fetch = fetch
        self.fetcher = fetcher or fetch_url
        self.edits = {}          # page -> [(start, end, new)]
        self.renames = {}        # real path -> its new name in the part
        self.copies = {}         # real path or URL -> (name in the part, data or None)
        self.rows = []           # the record's rows
        self.left = []           # what stays as it is, and why
        self.notes = []
        self.warnings = []       # pictures fetched over http:

    def shown(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def plan(self):
        for page in pages_of(self.source):
            try:
                with open(page, encoding="utf-8", newline="") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError) as exc:
                self.left.append(f"{self.shown(page)} can't be read as UTF-8 ({exc}), so "
                                 "what it names isn't looked at.")
                continue
            extension = os.path.splitext(page)[1].lower()
            seen = set()
            for start, end, value, context, how in references(text, extension):
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                try:
                    new, what, origin, digest = self.decide(page, value, context, how)
                except Stop as why:
                    self.left.append(f"{self.shown(page)} names {value}, {why}.")
                    continue
                if new is None or new == value:
                    continue
                self.edits.setdefault(page, []).append((start, end, new))
                self.rows.append({"page": self.shown(page), "was": value, "now": new,
                                  "what": what, "from": origin, "sha256": digest})
        self.sidecar_notes()

    def decide(self, page, value, context, how):
        """(the new reference or None, what was done, where from, its
        hash), or Stop."""
        name = as_written(value, how)
        url = by_url(name)
        if url == "remote":
            if context != "picture":
                return None, None, None, None
            return self.remote(name, how, value)
        fragment = ""
        if url == "file":
            parts = urllib.parse.urlsplit(name)
            if parts.netloc not in ("", "localhost"):
                raise Stop(f"a file: URL on another machine ({parts.netloc})")
            return self.outside(urllib.parse.unquote(parts.path), how, value, "")
        if re.match(r"^[a-zA-Z][\w+.-]*:(?![\\/])|^#", name) or not name.strip():
            return None, None, None, None
        match = re.match(r"([^#?]*)(.*)$", name, re.S)
        name, fragment = match.group(1), match.group(2)
        name = urllib.parse.unquote(name)
        what = []
        if "\\" in name:
            name = name.replace("\\", "/")
            what.append("a backslash")
        if re.match(r"^[a-zA-Z]:/", name):
            raise Stop("a Windows drive's path, which isn't found here: copy the file into "
                       f"src/{self.part}/ and name it there")
        if os.path.isabs(name) or name.startswith("~"):
            return self.outside(os.path.expanduser(name), how, value, fragment, what)
        path = os.path.join(self.source, name)
        if not within(self.source, path) or self.project.unreadable(path, self.part):
            return self.outside(path, how, value, fragment, what)
        if not os.path.lexists(path):
            cased = case_match(self.source, name)
            if not cased:
                if what:
                    return written(name, how, value) + fragment, "; ".join(what), "", ""
                return None, None, None, None
            name = cased.replace(os.sep, "/")
            path = os.path.join(self.source, name)
            what.append("another case")
        renamed = self.kind(path, name)
        if renamed:
            name = renamed
            what.append("another kind's extension")
        if not what:
            return None, None, None, None
        return written(name, how, value) + fragment, "; ".join(what), "", ""

    def kind(self, path, name):
        """A picture of another kind under its name: its name under its own
        kind's extension, the rename planned; or None."""
        if not os.path.isfile(path):
            return None
        found = filekinds.mismatch(path)
        if not found or not filekinds.picture_slip(found[0], found[1]):
            return None
        real = os.path.realpath(path)
        if real not in self.renames:
            stem, _ = os.path.splitext(name)
            target = stem + filekinds.EXTENSION_OF[found[0]]
            full = os.path.join(self.source, target)
            if os.path.lexists(full) and not (os.path.isfile(full)
                                              and sha256(full) == sha256(real)):
                target = f"{stem}-{sha256(real)[:8]}{filekinds.EXTENSION_OF[found[0]]}"
            self.renames[real] = target
        return self.renames[real]

    def outside(self, path, how, value, fragment, what=()):
        """A file outside the part: copied into imported/ from a --from
        folder, or Stop."""
        real = os.path.realpath(path)
        if within(self.source, real) and not self.project.unreadable(real, self.part):
            name = os.path.relpath(real, self.source).replace(os.sep, "/")
            return (written(name, how, value) + fragment,
                    "; ".join(list(what) + ["a full path into the part"]), "", "")
        folder = next((f for f in self.sources_from if within(f, real)), None)
        if folder is None:
            raise Stop("outside the part" + (f" ({', '.join(what)} too)" if what else "")
                       + "; --from names a folder to copy such a file in from")
        below = os.path.relpath(real, folder).split(os.sep)
        if any(n.startswith(".") for n in below):
            raise Stop(f"behind a dot name ({next(n for n in below if n.startswith('.'))}), "
                       "which isn't copied in")
        if not os.path.isfile(real):
            raise Stop("not a file here")
        wanted = filekinds.expected(real)
        if wanted is None:
            raise Stop("a kind of file TextbookImprover doesn't know by its name, which "
                       "isn't copied in")
        found = filekinds.mismatch(real)
        extension = os.path.splitext(real)[1]
        if found:
            if not filekinds.picture_slip(found[0], found[1]):
                raise Stop(filekinds.said(real, found[0], found[1], found[2],
                                          os.path.basename(real)).rstrip("."))
            extension = filekinds.EXTENSION_OF[found[0]]
        if real not in self.copies:
            digest = sha256(real)
            stem = os.path.splitext(os.path.basename(real))[0]
            target = "imported/" + stem + extension
            full = os.path.join(self.source, target)
            taken = {n for n, _, _ in self.copies.values()}
            if (os.path.lexists(full) and not (os.path.isfile(full)
                                               and sha256(full) == digest)) \
                    or target in taken:
                target = f"imported/{stem}-{digest[:8]}{extension}"
            self.copies[real] = (target, None, digest)
        target, _, digest = self.copies[real]
        return (written(target, how, value) + fragment, "copied in", real, digest)

    def remote(self, url, how, value):
        """A picture named by URL: fetched with --fetch into remote/, or
        Stop."""
        if not self.fetch:
            raise Stop("a picture named by URL; --fetch saves it into the part")
        full = "https:" + url if url.startswith("//") else url
        if full not in self.copies:
            chain = []
            data = self.fetcher(full, chain=chain)
            hop = plaintext(chain)
            if hop:
                self.warnings.append(
                    f"{full} was fetched over http:"
                    + (f" (a redirect, {hop})" if hop != full else "")
                    + ", not https:, so what came could have been changed on the way: its "
                    "kind is checked, and what it shows can't be. Use an https: address for "
                    "it if there is one, or check the picture.")
            found = filekinds.sniff(data[:filekinds.HEAD])
            if found not in filekinds.PICTURES:
                raise Stop(f"and what it gave is {filekinds.WORDS.get(found, found)}, not a "
                           "picture, so it isn't saved")
            digest = sha256(data=data)
            last = urllib.parse.unquote(urllib.parse.urlsplit(full).path.rsplit("/", 1)[-1])
            stem = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.splitext(last)[0]).strip("-.")[:48]
            target = f"remote/{digest[:12]}-{stem or 'picture'}{filekinds.EXTENSION_OF[found]}"
            self.copies[full] = (target, data, digest)
        target, _, digest = self.copies[full]
        return written(target, how, value), "fetched", full, digest

    def sidecar_notes(self):
        """A sidecar row keyed by a name that changed, to be keyed anew."""
        folder = os.path.join(self.root, "sidecars", self.part)
        changed = {}
        for row in self.rows:
            was = urllib.parse.unquote(row["was"]).replace("\\", "/")
            now = urllib.parse.unquote(html.unescape(row["now"]))
            changed[os.path.splitext(was)[0]] = os.path.splitext(now)[0]
            changed[was] = now
        if not changed or not os.path.isdir(folder):
            return
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".csv"):
                continue
            try:
                with open(os.path.join(folder, name), encoding="utf-8-sig", newline="") as fh:
                    keys = [row[0] for row in csv.reader(fh) if row]
            except (OSError, UnicodeDecodeError, csv.Error):
                continue
            for key in keys:
                if key in changed and changed[key] != key:
                    self.notes.append(f"sidecars/{self.part}/{name} has a row keyed {key}, "
                                      f"which is {changed[key]} now: key it so.")

    def report(self):
        for row in self.rows:
            how = {"copied in": f"copied in from {row['from']}",
                   "fetched": f"fetched from {row['from']}"}.get(row["what"],
                                                               f"for {row['what']}")
            say(f"{row['page']}: {row['was']} -> {row['now']} ({how})")
        for real, target in sorted(self.renames.items()):
            say(f"{self.shown(real)} renamed {self.shown(os.path.join(self.source, target))}, "
                "its own kind's extension")
        for line in self.left:
            say("LEFT: " + line)
        for line in self.warnings:
            say("WARNING: " + line)
        for line in self.notes:
            say("NOTE: " + line)
        if not (self.rows or self.left):
            say(f"Nothing in src/{self.part}/ to bring in.")

    def place(self, name):
        """A file's path in the part, refused if it would land outside."""
        path = os.path.join(self.source, name)
        if not within(self.source, os.path.dirname(path)):
            raise Stop(f"{name} would be outside src/{self.part}/")
        return path

    def keep(self, path):
        """Keep a file of the part in originals/<part>/ before it changes,
        under its path in the part; a later one beside an earlier one."""
        below = os.path.relpath(path, self.source)
        kept = os.path.join(self.originals, below)
        if not within(self.originals, os.path.dirname(kept)) \
                and os.path.lexists(os.path.dirname(kept)):
            raise Stop(f"originals/{self.part}/ leads elsewhere")
        number = 1
        while os.path.lexists(kept):
            if os.path.isfile(kept) and sha256(kept) == sha256(path):
                return
            number += 1
            kept = os.path.join(self.originals, f"{below}.{number}")
        os.makedirs(os.path.dirname(kept), exist_ok=True)
        shutil.copy2(path, kept)

    def execute(self):
        for real, (target, data, digest) in self.copies.items():
            path = self.place(target)
            if os.path.isfile(path) and sha256(path) == digest:
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if data is None:
                shutil.copyfile(real, path)
            else:
                with open(path, "wb") as fh:
                    fh.write(data)
        for real, target in self.renames.items():
            path = self.place(target)
            self.keep(real)
            if not (os.path.isfile(path) and sha256(path) == sha256(real)):
                os.replace(real, path)
            else:
                os.remove(real)
        for page, edits in self.edits.items():
            with open(page, encoding="utf-8", newline="") as fh:
                text = fh.read()
            self.keep(page)
            for start, end, new in sorted(edits, reverse=True):
                text = text[:start] + new + text[end:]
            with open(page, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        if self.rows:
            os.makedirs(self.originals, exist_ok=True)
            record = os.path.join(self.originals, RECORD)
            new = not os.path.exists(record)
            today = datetime.date.today().isoformat()
            with open(record, "a", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, RECORD_FIELDS)
                if new:
                    writer.writeheader()
                for row in self.rows:
                    writer.writerow(dict(row, date=today))


# -- a picture named by URL --------------------------------------------------

def public(address):
    """Whether an address is on the public internet: not this machine,
    its network, a link-local, multicast, or reserved one."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def checked_connection(secure, allowed):
    """An HTTP(S) connection that refuses the address it connected to
    when allowed doesn't take it, before a byte is sent."""
    base = http.client.HTTPSConnection if secure else http.client.HTTPConnection

    class Checked(base):
        def connect(self):
            http.client.HTTPConnection.connect(self)
            peer = self.sock.getpeername()[0]
            if not self._tunnel_host and not allowed(peer):
                self.sock.close()
                raise Stop(f"its server is at {peer}, which isn't on the public internet")
            if secure:
                host = self._tunnel_host or self.host
                self.sock = self._context.wrap_socket(self.sock, server_hostname=host)
    return Checked


def fetch_url(url, allowed=public, limit=MAX_BYTES, timeout=TIMEOUT, chain=None):
    """A picture's bytes, fetched from url: http: or https:, no cookie or
    password, up to five redirects, each address checked, no more than
    limit bytes. Stop on anything else. chain, a list, is given each URL
    asked for, the redirects' too, in order (plaintext says whether one
    was over http:)."""
    for _ in range(REDIRECTS + 1):
        if chain is not None:
            chain.append(url)
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            raise Stop(f"a {scheme}: URL, which isn't fetched here; fetch it yourself")
        if parts.username or parts.password:
            raise Stop("a URL holding a name or a password, which isn't sent")
        host = parts.hostname
        if not host:
            raise Stop("a URL with no host")
        port = parts.port or (443 if scheme == "https" else 80)
        proxy = None if urllib.request.proxy_bypass(host) \
            else urllib.request.getproxies().get(scheme)
        try:
            addresses = {info[4][0] for info in socket.getaddrinfo(host, port,
                                                                   type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            if not proxy:
                raise Stop(f"its host {host} isn't found ({exc.strerror or exc})")
            addresses = set()
        refused = sorted(a for a in addresses if not allowed(a))
        if refused:
            raise Stop(f"its host {host} is at {refused[0]}, which isn't on the public internet")
        connection = checked_connection(scheme == "https", allowed)
        context = ssl.create_default_context() if scheme == "https" else None
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
        if proxy:
            via = urllib.parse.urlsplit(proxy if "//" in proxy else "http://" + proxy)
            if scheme == "https":
                conn = connection(via.hostname, via.port or 8080, timeout=timeout,
                                  context=context)
                conn.set_tunnel(host, port)
            else:
                conn = connection(via.hostname, via.port or 8080, timeout=timeout)
                target = url
        elif scheme == "https":
            conn = connection(host, port, timeout=timeout, context=context)
        else:
            conn = connection(host, port, timeout=timeout)
        try:
            conn.request("GET", target, headers={"User-Agent": AGENT, "Accept": "image/*",
                                                 "Accept-Encoding": "identity"})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise Stop(f"a redirect ({response.status}) to nowhere")
                url = urllib.parse.urljoin(url, location)
                continue
            if response.status != 200:
                raise Stop(f"its server answered {response.status} {response.reason}")
            length = response.getheader("Content-Length")
            if length and length.isdigit() and int(length) > limit:
                raise Stop(f"{int(length)} bytes, more than the {limit} taken")
            data = response.read(limit + 1)
            if len(data) > limit:
                raise Stop(f"more than the {limit} bytes taken")
            return data
        except (OSError, http.client.HTTPException) as exc:
            raise Stop(f"its fetch failed ({exc})")
        finally:
            conn.close()
    raise Stop(f"more than {REDIRECTS} redirects")


def plaintext(chain):
    """The first URL of a fetch's chain asked for over http:, which anyone
    on the way could have answered for the server, or None when every one
    was https:."""
    for url in chain:
        if urllib.parse.urlsplit(url).scheme.lower() == "http":
            return url
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Bring what a part's pages name into the part: names that don't name "
                    "their files as every reader would, a file named outside the part, and "
                    "a picture named by URL.")
    parser.add_argument("-d", "--dir", default=".",
                        help="the project's folder (default: this one)")
    projectpaths.add_part_option(parser)
    parser.add_argument("--from", dest="sources_from", action="append", default=[],
                        metavar="FOLDER",
                        help="copy a file a page names outside the part in from FOLDER, "
                             "into src/<part>/imported/; may be given again. Never a dot "
                             "name below it")
    parser.add_argument("--fetch", action="store_true",
                        help="fetch each picture a page names by URL into "
                             "src/<part>/remote/, from the public internet alone")
    parser.add_argument("--dry-run", action="store_true",
                        help="say what it would do, and do nothing")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.dir)
    nothing = "Nothing was changed."
    above = projectpaths.inside_project(root)
    if above:
        say(f"{root} is inside the project {above}, among its sources or its outputs. Run "
            f"this from the project's folder, or give it with -d {above}. {nothing}")
        return 2
    why = projectpaths.not_a_project(root)
    if why:
        say(f"{why} {nothing}")
        return 2
    try:
        if not args.dry_run:
            for line in projectpaths.by_hand(root, nothing):
                say(line)
        else:
            why = projectpaths.refused_root(root)
            if why:
                raise projectpaths.Refused(f"{root} can't be a project's folder: {why}. "
                                           f"{nothing}")
        for folder in args.sources_from:
            if not os.path.isdir(folder):
                say(f"--from {folder} isn't a folder. {nothing}")
                return 2
            real = os.path.realpath(folder)
            if within(real, os.path.expanduser("~")) or real == os.sep:
                say(f"--from {folder} is {'the root' if real == os.sep else 'your home folder'}"
                    f"{' or holds it' if real != os.sep else ''}: name the folder the files "
                    f"are in. {nothing}")
                return 2
        work = Import(root, args.part, args.sources_from, args.fetch)
        work.plan()
    except projectpaths.Refused as exc:
        say(str(exc))
        return 2
    except Stop as exc:
        say(f"{exc}. {nothing}")
        return 1
    work.report()
    if args.dry_run:
        say(f"\n{nothing[:-1]} (--dry-run).")
        return 0
    try:
        work.execute()
    except Stop as exc:
        say(f"{exc}. Stopped partway; originals/{work.part}/ keeps what was changed.")
        return 1
    if work.rows:
        say(f"\nDone: {len(work.rows)} reference(s) changed, the originals in "
            f"originals/{work.part}/ and each change in originals/{work.part}/{RECORD}.")
    return 1 if work.left else 0


if __name__ == "__main__":
    sys.exit(main())
