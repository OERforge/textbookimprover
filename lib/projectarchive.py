"""
projectarchive -- TextbookImprover's manifest of a project, ti-archive.yaml,
and the identity check a run makes against it.

    import projectarchive
    now = projectarchive.manifest(root)       # what the folder holds now
    projectarchive.write(root, now)           # ti-archive.yaml at its top
    kept = projectarchive.read(root)          # None where there's none
    said = projectarchive.check(kept, now)    # what a run does

The manifest says what a book is: every file of the inventory of inputs
(lib/inputs.py) with its size, its SHA-256 as stored, its role and part,
and for a file TextbookImprover reads as text the SHA-256 of that text
without a byte-order mark and with LF line ends; the identifier and
version the files are released under; and digests over them. Packing
writes one into an archive and leaves a copy at the project's top, and
extracting an archive leaves the archive's; until packing is built,
util/write-manifest.py writes the copy.

DIGESTS

Each digest is the SHA-256 of a list in the form of a BagIt manifest: a
line for each file, its hash in hexadecimal, two spaces, and its path
from the project's folder, / between its names, in Unicode NFC, with %,
CR, and LF written %25, %0D, and %0A; the lines sorted by the paths'
UTF-8 bytes. A digest so made doesn't depend on how the files were
copied or zipped. The digests are over these roles:

  inputs    settings, source, sidecar, and named files, each by its text
            hash where it has one, so a change of line ends or a
            byte-order mark alone changes no release
  files     a part of kind files, each as stored
  sources, sidecars, config (settings and named), and upstream, each
            by the hash inputs uses, to say at a glance what changed
  archive   every file listed, as stored

THE IDENTITY CHECK

A project's identifier names the book for life, and its version names
a release; each identifier and version name one set of inputs. Where
ti-archive.yaml is at the project's top, a run that writes outputs
compares the folder with it (check): the same inputs and files, the
same release built again; different ones under a new version, a
revision, or a new identifier, an adaptation, built with a note; different
ones under the manifest's own identifier and version, a stop, naming the
files changed, unless --draft, which builds and says so in the build
record and the colophon. The default identifier, book, stops a run
where there's a manifest, since a book released under it can't be told
from any other.

The manifest is read as data a project's sender wrote: no more than
LONGEST bytes, YAML without anchors or aliases, every field checked, and
no path it names is opened; the run hashes the files its own inventory
lists and compares the lists. Its digests must be those of its own list
of files, and its paths printable. What it records is said in a
message only made printable and cut short (shown).

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

import collections
import hashlib
import os
import re
import stat
import unicodedata

import inputs
import oerconfig
import projectpaths

FORMAT = "textbookimprover-archive/1"
NAME = "ti-archive.yaml"
# A manifest larger than this isn't read: a book of tens of thousands of
# files makes one of a few megabytes.
LONGEST = 16 << 20
MOST_FILES = 200000
DEFAULT_IDENTIFIER = "book"
# The kinds of file a run reads as text, by their endings: a page, a
# LaTeX book's files, a setting, a sidecar. Others are bytes.
TEXT_ENDINGS = (".md", ".markdown", ".html", ".htm", ".xhtml", ".tex", ".ltx", ".latex",
                ".sty", ".cls", ".bib", ".adoc", ".asciidoc", ".yaml", ".yml", ".csv",
                ".css", ".txt")
TEXT_ROLES = ("settings", "source", "sidecar", "named")
INPUT_ROLES = ("settings", "source", "sidecar", "named")
DIGEST_ROLES = collections.OrderedDict([
    ("inputs", INPUT_ROLES), ("files", ("files",)), ("sources", ("source",)),
    ("sidecars", ("sidecar",)), ("config", ("settings", "named")),
    ("upstream", ("upstream",)),
])
HEX = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20
# How many changed files a stop's message names before the report.
NAMED = 3


class Problem(Exception):
    """A manifest that can't be read as one: the message says why."""


def nfc(path):
    """A path as the manifest gives it: / between its names, in NFC."""
    return unicodedata.normalize("NFC", path.replace(os.sep, "/"))


def bag_path(path):
    """A path as a line of a BagIt manifest writes it."""
    return path.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def text_of(data):
    """Text's bytes with LF line ends, as a run reads them."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _inside(path, root):
    real = os.path.realpath(path)
    top = os.path.realpath(root)
    return real == top or real.startswith(top.rstrip(os.sep) + os.sep)


def file_entry(root, entry):
    """The manifest's line for one of the inventory's files, or None for
    one that isn't there: its path, size, SHA-256, text hash where it's
    read as text, role, and part. A link is given by where it points; it's
    read only where it leads to a file inside the project."""
    full = os.path.join(root, *entry.path.split("/"))
    out = collections.OrderedDict(path=nfc(entry.path))
    if os.path.islink(full):
        out["link"] = os.readlink(full)
        if not (_inside(full, root) and os.path.isfile(full)):
            out.update(size="0", sha256=hashlib.sha256(
                ("link:" + out["link"]).encode("utf-8", "surrogateescape")).hexdigest())
            return _finish(out, entry)
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | (
        0 if os.path.islink(full) else getattr(os, "O_NOFOLLOW", 0))
    try:
        fd = os.open(full, flags)
    except OSError:
        return None
    text = entry.role in TEXT_ROLES and entry.path.lower().endswith(TEXT_ENDINGS)
    stored, read_as = hashlib.sha256(), hashlib.sha256()
    size, first, after_cr = 0, True, False
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            stored.update(chunk)
            if text:
                if first and chunk.startswith(b"\xef\xbb\xbf"):
                    chunk = chunk[3:]
                if after_cr and chunk.startswith(b"\n"):
                    chunk = chunk[1:]
                after_cr = chunk.endswith(b"\r")
                read_as.update(text_of(chunk))
            first = False
    out["size"] = str(size)
    out["sha256"] = stored.hexdigest()
    if text:
        out["text"] = read_as.hexdigest()
    return _finish(out, entry)


def _finish(out, entry):
    out["role"] = entry.role
    if entry.part:
        out["part"] = entry.part
    return out


def files_of(root, roles=None):
    """The manifest's files for the project at root as it is now, those
    in roles alone where they're given."""
    root = os.path.abspath(root)
    found = []
    leave_out = () if roles is None else tuple(r for r in ("files", "upstream")
                                               if r not in roles)
    for entry in inputs.inventory(root, leave_out=leave_out):
        if entry.missing or (roles is not None and entry.role not in roles):
            continue
        made = file_entry(root, entry)
        if made is not None:
            found.append(made)
    return sorted(found, key=lambda f: f["path"].encode("utf-8"))


def _hash_for(entry, by_text):
    return entry.get("text") if by_text and entry.get("text") else entry["sha256"]


def digest(files, roles=None, by_text=True):
    """The digest of those of files in roles (all where None), in BagIt's
    form, each by its text hash where by_text and it has one."""
    lines = sorted((f["path"].encode("utf-8"),
                    f"{_hash_for(f, by_text)}  {bag_path(f['path'])}\n")
                   for f in files if roles is None or f["role"] in roles)
    return "sha256:" + hashlib.sha256("".join(line for _, line in lines)
                                      .encode("utf-8")).hexdigest()


def digests(files):
    """Every digest the manifest gives: by role, and the archive's."""
    out = collections.OrderedDict()
    for name, roles in DIGEST_ROLES.items():
        out[name] = digest(files, roles, by_text=(name != "files"))
    out["archive"] = digest(files, None, by_text=False)
    return out


def input_digest(root):
    """The inputs digest of the project at root as it is now, reading
    neither its upstream files nor its files parts', which a run without
    a manifest has no need to."""
    return digest(files_of(root, INPUT_ROLES), INPUT_ROLES)


def identity(root):
    """The project's identifier, version, title, and license, as settled
    from project.yaml and conversion.yaml's project: block."""
    schema, project_schema = inputs.schemas()
    project = oerconfig.resolve(schema, project_schema,
                                inputs._documents(root, schema, project_schema),
                                allow_unknown=True).project
    return collections.OrderedDict(
        (key, str(project.get(key) or "")) for key in ("identifier", "version", "title",
                                                        "license"))


def manifest(root):
    """The manifest the project at root has now."""
    files = files_of(root)
    return collections.OrderedDict([
        ("format", FORMAT), ("book", "."), ("project", identity(root)),
        ("digests", digests(files)), ("files", files)])


def path_of(root):
    return projectpaths.of(root).top(NAME)


def write(root, made):
    """made written to ti-archive.yaml at the project's top, every value
    quoted, through a new file that a link can't stand in for."""
    import yaml

    def plain(value):
        if isinstance(value, dict):
            return {str(k): plain(v) for k, v in value.items()}
        if isinstance(value, list):
            return [plain(v) for v in value]
        return str(value)
    text = ("# What this book is made of (lib/projectarchive.py): its files, their "
            "hashes and roles,\n# and the identifier and version they're released "
            "under. Written when the project is packed; not a setting.\n"
            + yaml.safe_dump(plain(made), default_style='"', sort_keys=False,
                             allow_unicode=True, width=100))
    path = path_of(root)
    new = path + ".new"
    if os.path.lexists(new):
        os.remove(new)
    fd = os.open(new, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(new, path)
    return path


class _Loader(oerconfig.SafeLoader):
    """The safe loader, refusing an anchor or an alias, which a manifest
    never needs and which can make a small file a large structure."""

    def compose_node(self, parent, index):
        import yaml
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise Problem("it uses a YAML anchor or alias, which a manifest never has")
        return super().compose_node(parent, index)


def _string(value, where):
    if not isinstance(value, str):
        raise Problem(f"{where} isn't text")
    return value


def _safe_path(path):
    names = path.split("/")
    return (path == nfc(path) and path.isprintable() and "\\" not in path
            and not path.startswith("/") and all(n not in ("", ".", "..") for n in names))


def shown(value, longest=120):
    """A value a manifest gives, for a message: its characters that aren't
    printable written as escapes, cut to longest."""
    text = "".join(c if c.isprintable() else repr(c)[1:-1] for c in str(value))
    return text if len(text) <= longest else text[:longest - 1] + "…"


def read(root):
    """The manifest at the project's top, checked, or None where there's
    none. Raises Problem where it can't be read as one."""
    import yaml
    path = path_of(root)
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        raise Problem("it's a link")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise Problem(f"it can't be opened ({error.strerror})")
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise Problem("it isn't a file")
        data = fh.read(LONGEST + 1)
    if len(data) > LONGEST:
        raise Problem(f"it's larger than {LONGEST >> 20} MB")
    try:
        made = yaml.load(data.decode("utf-8"), Loader=_Loader)
    except UnicodeDecodeError:
        raise Problem("it isn't UTF-8")
    except yaml.YAMLError as error:
        raise Problem(f"it isn't YAML ({shown(str(error).splitlines()[0])})")
    except RecursionError:
        raise Problem("it's nested deeper than a manifest is")
    if not isinstance(made, dict):
        raise Problem("it isn't a mapping")
    if made.get("format") != FORMAT:
        raise Problem(f"its format isn't {FORMAT}")
    if made.get("book") != ".":
        raise Problem("its book isn't ., the folder it's in")
    project = made.get("project")
    if not isinstance(project, dict):
        raise Problem("its project isn't a mapping")
    for key in ("identifier", "version"):
        _string(project.get(key, ""), f"project.{key}")
    said = made.get("digests")
    if not isinstance(said, dict):
        raise Problem("its digests aren't a mapping")
    files = made.get("files")
    if not isinstance(files, list) or len(files) > MOST_FILES:
        raise Problem(f"its files aren't a list of at most {MOST_FILES}")
    seen = set()
    for number, entry in enumerate(files, 1):
        where = f"file {number}"
        if not isinstance(entry, dict):
            raise Problem(f"{where} isn't a mapping")
        path = _string(entry.get("path"), f"{where}'s path")
        if not _safe_path(path):
            raise Problem(f"{where}'s path isn't one from the project's folder, printable, "
                          "in NFC, with / between names and no . or ..")
        if path in seen:
            raise Problem(f"{shown(path)} is listed twice")
        seen.add(path)
        if "sha256" not in entry:
            raise Problem(f"{shown(path)} has no sha256")
        for key in ("sha256", "text"):
            if key in entry and not (isinstance(entry[key], str) and HEX.fullmatch(entry[key])):
                raise Problem(f"{shown(path)}'s {key} isn't 64 hexadecimal digits")
        if entry.get("role") not in inputs.ROLES:
            raise Problem(f"{shown(path)}'s role isn't one of " + ", ".join(inputs.ROLES))
    # Its digests are its list's: the check compares the run's files with
    # the list, so a digest that says otherwise is a damaged manifest.
    for name, value in digests(files).items():
        if name not in said and name == "upstream":
            continue
        if said.get(name) != value:
            raise Problem(f"its digest {name} isn't that of its own list of files")
    return made


def changed_files(kept, now):
    """(added, changed, removed): the paths, among the inputs and the files
    parts' files, that differ between two manifests' lists, each compared
    as the digest it's in compares it."""
    def table(files):
        return {f["path"]: _hash_for(f, f["role"] != "files") for f in files
                if f["role"] in INPUT_ROLES + ("files",)}
    before, after = table(kept["files"]), table(now["files"])
    added = sorted(p for p in after if p not in before)
    removed = sorted(p for p in before if p not in after)
    changed = sorted(p for p in after if p in before and after[p] != before[p])
    return added, changed, removed


CHANGES = "archive-changes.csv"
NONE = ((), (), ())
Said = collections.namedtuple("Said", "state stop note changes")


def check(kept, now, draft=False, carries=True):
    """What a run that writes outputs does, given the manifest at the
    project's top (kept, or None) and the project as it is now (now):
    Said(state, stop, note, changes). state is none (no manifest),
    release (the inputs the manifest records), revision, adaptation,
    draft (built with --draft where it would stop), or changed (a stop);
    stop is the message to stop with, or None; note a line to say, or
    None; changes the (added, changed, removed) of changed_files. carries
    says a target carries the identifier (an EPUB, or a cartridge from
    an html target's pages), which the default one stops."""
    if kept is None:
        return Said("none", None, None, NONE)
    mine, theirs = now["project"], kept["project"]
    identifier, version = mine.get("identifier", ""), mine.get("version", "")
    released = (f"{shown(theirs.get('identifier', ''))} version "
                f"{shown(theirs.get('version', '')) or '(none)'}")
    same = (now["digests"]["inputs"] == kept["digests"]["inputs"]
            and now["digests"]["files"] == kept["digests"]["files"])
    changes = NONE if same else changed_files(kept, now)
    if identifier == DEFAULT_IDENTIFIER and carries:
        if draft:
            return Said("draft", None, (
                f"--draft: the identifier is the default, {DEFAULT_IDENTIFIER}, which names no "
                "book of its own, so this build is a draft, not a release; the build record "
                "and the colophon say so."), changes)
        return Said("changed", (
            f"This project has a manifest ({NAME}), and its identifier is the default, "
            f"{DEFAULT_IDENTIFIER}, which names no book of its own: an LMS would take its "
            "cartridge for any other book's, and a reading system its EPUB. Give it one "
            "no other book uses, as project.identifier in project.yaml; to build it "
            "anyway, not as a release, run again with --draft. Nothing was built."),
            None, changes)
    if same:
        return Said("release", None, None, NONE)
    if identifier != theirs.get("identifier", ""):
        return Said("adaptation", None, (
            f"NOTE: {NAME} records {released}; this is {identifier} version "
            f"{version or '(none)'}, so it's built as an adaptation of it."), changes)
    if version != theirs.get("version", ""):
        return Said("revision", None, (
            f"NOTE: {NAME} records {released}; this is version {version or '(none)'}, "
            "so it's built as a revision of it."), changes)
    names = [shown(n) for n in list(changes[1]) + list(changes[0]) + list(changes[2])]
    listed = ", ".join(names[:NAMED]) + (f", and {len(names) - NAMED} more"
                                         if len(names) > NAMED else "")
    if draft:
        return Said("draft", None, (
            f"--draft: the inputs differ from {released} as {NAME} records it "
            f"({len(names)} file(s): {listed}), so this build is a draft, not a release; "
            "the build record and the colophon say so."), changes)
    return Said("changed", (
        f"The book's inputs have changed since {released} was recorded in {NAME} "
        f"({len(names)} file(s): {listed}; all of them in output/reports/{CHANGES}). If "
        "this is your book, raise project.version in project.yaml to make a new "
        "release of it. If you're adapting someone else's, give it an identifier of "
        "your own (project.identifier) and add yourself to project.adapters. To build "
        "it anyway, not as a release, run again with --draft. Nothing was built."),
        None, changes)


def write_changes(root, changes):
    """output/reports/archive-changes.csv: each file added, changed, or
    removed since the manifest, a row each, or no file where none is."""
    import sidecars
    folder = os.path.join(projectpaths.of(root).run_output(), "reports")
    path = os.path.join(folder, CHANGES)
    if not any(changes):
        if os.path.isfile(path) and not os.path.islink(path):
            os.remove(path)
        return None
    os.makedirs(folder, exist_ok=True)
    if os.path.lexists(path):
        os.remove(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o644)
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as fh:
        writer = sidecars.csv_writer(fh, lineterminator="\n")
        writer.writerow(["path", "change"])
        for label, names in zip(("added", "changed", "removed"), changes):
            for name in names:
                writer.writerow([name, label])
    return path


# -- what a run tells the programs it starts ----------------------------------

# "<state> <inputs digest>", which a run that checked sets for the programs
# it starts (announce), so that a colophon written in the sandbox says what
# the check found, as tiversion's RUN_COMMIT does for the commit.
RUN_INPUTS = "TEXTBOOKIMPROVER_RUN_INPUTS"
SAID_STATES = ("none", "release", "revision", "adaptation", "draft")


def announce(state, inputs_digest, environ=None):
    """Set RUN_INPUTS in environ (os.environ by default) for the programs
    a run starts."""
    environ = os.environ if environ is None else environ
    environ[RUN_INPUTS] = f"{state} {inputs_digest}"


def run_inputs(environ=None):
    """(state, inputs digest) as the run that started this one set them,
    or None where it set none or what's set isn't of their form."""
    environ = os.environ if environ is None else environ
    said = environ.get(RUN_INPUTS, "").split()
    if len(said) == 2 and said[0] in SAID_STATES and said[1].startswith("sha256:") \
            and HEX.fullmatch(said[1][7:]):
        return said[0], said[1]
    return None
