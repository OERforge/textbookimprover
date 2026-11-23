"""Where a project's files are.

One object, made from the project's folder, answers every question a
script has about a path in it: where the settings are, where a part's
sources, sidecars, reports, and intermediates are, where a target's or a
package's folder is, where a temporary folder goes, and which folder
Pandoc and LaTeX run in. A script asks; it doesn't put a project's path
together itself, so the layout is written down once, here.

    paths = projectpaths.of(args.dir)
    out_dir = paths.target_dir(name, resolved["output_dir"])
    work = paths.temp_dir("build-epub-")
    subprocess.run(command, cwd=paths.run_dir())

A function that is handed the book's folder asks through of(), which
takes a folder or the object itself, so the same function serves when
its caller has the object to give.

of() gives a Tree for a project: a folder whose src/ holds a folder for
each part and no file, with each part's sidecars in sidecars/<part>/ and
everything a run writes under output/. The tools that build stop on any
other folder (not_a_project). A function handed a plain folder, as a
library call is or a tool given a folder of decks, gets a Project, which
answers every question with that one folder: its sources, sidecars,
reports, and intermediates all in it, and each target's folder beside
them. The suites ask the same object where to look for what a run wrote.

A part is a book, a set of decks, or another collection with sources of
its own. Every question that depends on one takes it; a plain folder's
answer is the same for all.

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
import shutil
import subprocess
import sys
import tempfile

PROJECT_NAME = "project.yaml"
CONFIG_NAME = "conversion.yaml"
PACKAGING_NAME = "packaging.yaml"
# A source's document as Pandoc read it, and as the filters left it.
RAW = ".json"
INTERMEDIATE = ".filtered.json"
BOOK = "book"
# The folders at a project's top that no setting's file is read from:
# what runs write, what was taken out of the sources, the sidecars, and
# the files as a publisher sent them.
NOT_NAMED = ("output", "originals", "sidecars", "upstream")


# A part's name, as the project's schema has it: it's a folder's name
# and goes into the search paths Pandoc and LaTeX are given, where a
# colon would start another folder.
PART_NAME = re.compile(r"[a-z][a-z0-9_-]*\Z")


class Refused(SystemExit):
    """A path the settings give that a run won't read; raised, it stops
    the script with its message, as sys.exit does."""


class Project:
    """A plain folder holding everything, and where each thing in it is:
    what a function handed a folder that isn't a project asks. Tree,
    below, is a project.

    root is kept as it was given, so a path made from "." reads as it
    always has in a message ("./epub/book.epub")."""

    def __init__(self, root="."):
        self.root = root

    def _in(self, *names):
        return os.path.join(self.root, *names)

    # -- the settings ------------------------------------------------------

    def project_file(self):
        return self._in(PROJECT_NAME)

    def config_file(self):
        return self._in(CONFIG_NAME)

    def packaging_file(self):
        return self._in(PACKAGING_NAME)

    def top(self, *names):
        """A file or folder at the project's top that isn't a setting's:
        a configuration from an earlier version, say."""
        return self._in(*names)

    def named(self, value, part=None, setting=None):
        """The file or folder a setting names: from the project's folder,
        or as written when it's a full path."""
        return self._in(str(value))

    def named_file(self, value, part=None):
        """The file a setting names where the setting may be text
        instead (a header's or a footer's): its path when it's a file
        the settings may name, and otherwise None."""
        path = self.named(value, part)
        return path if os.path.isfile(path) else None

    def settings_folder(self):
        """The folder a setting's path is read from, for a module that
        still resolves one itself."""
        return self.root

    # -- a part's files ----------------------------------------------------

    def sources(self, part=None):
        """The folder holding a part's sources."""
        return self.root

    def source(self, *names, part=None):
        """A source, a folder of them, or a file a source names, by its
        path from the part's folder; a pattern for glob too."""
        return os.path.join(self.sources(part), *names)

    def source_arg(self, *names, part=None):
        """A source as a program run in run_dir names it: its path from
        that folder."""
        return os.path.relpath(self.source(*names, part=part), self.run_dir(part))

    def sidecar(self, value, part=None):
        """A part's sidecar, by the name its setting gives."""
        return self.named(value)

    def report(self, value, part=None):
        """A draft or a report of a part's, by the name its setting gives."""
        return self.named(value)

    def report_picture(self, key, part=None):
        """A picture a report's row names, where the row's key points
        from the report's folder (a deck's media/...)."""
        return self.named(key)

    def pages(self, part=None, own=None):
        """The folder holding a part's intermediates; own, the folder a
        target was given for its own, where its filters differ."""
        return own or self.root

    def page(self, stem, part=None, own=None, suffix=INTERMEDIATE):
        """One page's intermediate, as the filters left it."""
        return os.path.join(self.pages(part, own), stem + suffix)

    def raw(self, stem, part=None):
        """One source's document as Pandoc read it, before the filters."""
        return os.path.join(self.pages(part), stem + RAW)

    def referenced(self, *names, part=None):
        """The file a page names by a path from its part's folder: a
        picture or a linked file among the sources, or one the run
        extracted or rendered for the part."""
        return os.path.join(self.run_dir(part), *names)

    def media(self, *names, part=None):
        """What a run extracts or renders for a part beside its
        intermediates, by the path a page names it by: a Word file's
        pictures, a LaTeX book's rendered drawings. (A deck saved as
        PowerPoint isn't one: it's the deck from then on, a source beside
        its original.)"""
        return os.path.join(self.run_dir(part), *names)

    def work_file(self, name, part=None):
        """A file one step of a run leaves for a later one (the table
        headers as resolved, say), which no person reads."""
        return self._in(name)

    # -- what a run writes -------------------------------------------------

    def target_dir(self, name, output_dir=None):
        """A target's folder: named after it unless output_dir says."""
        return self._in(str(output_dir or name))

    def target_place(self, name, output_dir=None):
        """Where a target's folder is once it's built: target_dir, but in
        the layout that builds a target beside its folder."""
        return self.target_dir(name, output_dir)

    def put_in_place(self, name, output_dir=None):
        """A target's folder as built put where it's kept, and that
        place; nothing to do where it's built there."""
        return self.target_place(name, output_dir)

    def target_pages(self, name, output_dir=None):
        """A target's own intermediates, where its filters differ from
        the first target's."""
        return os.path.join(self.target_dir(name, output_dir), "intermediates")

    def target_file(self, name, filename, output_dir=None):
        return os.path.join(self.target_dir(name, output_dir), filename)

    def package_file(self, name, package=None):
        """A file a package's build writes: its manifest, its list of
        files, the cartridge itself."""
        return self._in(str(name))

    def put_package_in_place(self, package=None):
        """A package's folder as built put where it's kept, and that
        place; nothing to do where it's built there."""
        return self._in()

    def temp_dir(self, prefix="ti-", suffix=""):
        """A new temporary folder, the caller's to delete."""
        return mkdtemp(prefix=prefix, suffix=suffix)

    def temp_file(self, prefix="ti-", suffix="", beside=None, text=False):
        """A new temporary file, as tempfile.mkstemp gives it (an open
        handle and a path); beside, a file or folder it must share a disk
        with, so that it can be renamed into place."""
        return mkstemp(prefix=prefix, suffix=suffix, text=text,
                       dir=os.path.dirname(beside) if beside else None)

    def unpack_dir(self, part=None):
        """A new folder to unpack an archive of sources into, on the disk
        the sources are on, so its files can be renamed into place."""
        return mkdtemp(prefix=".unpacking-", dir=self.sources(part))

    def run_dir(self, part=None):
        """The folder Pandoc and LaTeX run in for a part: where a page's
        pictures are found by the paths its intermediate names."""
        return self.root

    def originals(self, part=None):
        """The folders, from run_dir, that a page's pictures are looked
        for in after any copies made of them: Pandoc's resource path's
        last entries."""
        return (".",)

    def reference_folders(self, part=None):
        """The folders a path a page names is looked for in, in order:
        what referenced() goes through."""
        return [self.run_dir(part)]

    def tex_env(self, env=None, part=None):
        """The environment for a LaTeX, BibTeX, or Biber run in run_dir
        that reads the book's own files: env, or the run's own, with the
        sources' folder on the programs' search paths when it isn't the
        folder they run in. The paths a face's file is looked for on are
        among them: fontspec's Path=fonts/ names a folder from where the
        book's files are, and LuaTeX looks from the folder it runs in and
        then on those paths, not on TEXINPUTS."""
        env = dict(os.environ if env is None else env)
        folders = [os.path.abspath(os.path.join(self.run_dir(part), o))
                   for o in self.originals(part) if o != "."]
        if folders:
            for name in ("TEXINPUTS", "BIBINPUTS", "BSTINPUTS") + FONT_PATHS:
                env[name] = os.pathsep.join(["."] + folders + [env.get(name, "")])
        return env

    # -- what a part may read ----------------------------------------------

    def inside(self, path):
        """Whether path, its links followed, is in the project."""
        root = os.path.realpath(self.root)
        real = os.path.realpath(path if os.path.isabs(path) else self._in(path))
        return real == root or real.startswith(root.rstrip(os.sep) + os.sep)



class Tree(Project):
    """A project, with a folder for each part's sources:

        src/<part>/               a part's sources
        sidecars/<part>/          its sidecars, under their standard names
        output/<target>/          a target's folder
        output/packages/<name>/   a package's
        output/reports/<part>/    drafts, reports, and samples
        output/work/parts/<part>/ intermediates and what a run extracts
                                  or renders, where Pandoc and LaTeX run
        output/work/targets/<target>/  a target's own intermediates
        output/work/staging/targets/<target>/  a target being built
        output/work/replaced/<target>/  the folder it replaces, for the
                                  moment of the swap
    """

    def __init__(self, root):
        super().__init__(root)
        # The sources' folder goes into TEXINPUTS and Pandoc's resource
        # path whole, where the separator would begin a folder of the
        # path's own choosing.
        if os.pathsep in os.path.abspath(root):
            raise Refused(f"{os.path.abspath(root)} has a {os.pathsep!r} in its path, which "
                          "the programs a run starts read as the end of a folder's name. "
                          "Move or rename the project's folder.")

    def default_part(self):
        """The part a target is made from when it names none, whose the
        project's contents are: book, or the one folder src/ holds."""
        if not hasattr(self, "_only"):
            try:
                found = sorted(e.name for e in os.scandir(self._in("src")) if e.is_dir())
            except OSError:
                found = []
            self._only = BOOK if BOOK in found or len(found) != 1 else found[0]
        return self._only

    def part(self, part=None):
        """The part meant: the one named, the one this run builds
        (set_part), or the project's own when it has one alone (book, or
        the one folder under src/). A name that isn't a part's stops the
        run: it's a folder's name here and part of a search path for
        Pandoc and LaTeX."""
        if not part:
            part = _PART[0]
        if not part:
            part = self.default_part()
        if not PART_NAME.match(str(part)):
            raise Refused(
                f"src/{part}/ in {os.path.abspath(self.root)} can't be a part of a project: a "
                "part's name is a lowercase letter, then lowercase letters, digits, - and _. "
                "Rename the folder (src/book/ for a book), or, for a book that keeps a src/ "
                "of its own, move it into the new layout with util/move-to-src.py.")
        return part

    def _made(self, *names):
        folder = self._in(*names)
        os.makedirs(folder, exist_ok=True)
        return folder

    def sources(self, part=None):
        part = self.part(part)
        return self._in("src", part)

    def sidecar(self, value, part=None):
        part = self.part(part)
        return self._in("sidecars", part, os.path.basename(str(value)))

    def report(self, value, part=None):
        part = self.part(part)
        return os.path.join(self._made("output", "reports", part),
                            os.path.basename(str(value)))

    def report_picture(self, key, part=None):
        part = self.part(part)
        names = str(key).split("/")
        if any(n in ("", ".", "..") or os.sep in n or (os.altsep and os.altsep in n)
               for n in names):
            raise Refused(f"{key!r} can't be a picture's place among a part's reports: it "
                          "leads out of their folder.")
        return os.path.join(self._made("output", "reports", part), *names)

    def pages(self, part=None, own=None):
        part = self.part(part)
        return own or self.run_dir(part)

    def target_pages(self, name, output_dir=None):
        return self._made("output", "work", "targets", name)

    def referenced(self, *names, part=None):
        part = self.part(part)
        made = os.path.join(self.run_dir(part), *names)
        return made if os.path.lexists(made) else self.source(*names, part=part)

    def work_file(self, name, part=None):
        part = self.part(part)
        return os.path.join(self.run_dir(part), name)

    def target_place(self, name, output_dir=None):
        return self._in("output", str(output_dir or name))

    def target_dir(self, name, output_dir=None):
        """Where a target's build writes: its folder, or, in a run that
        builds each target beside its folder (build_beside), the folder
        it's built in, which put_in_place swaps in when the build is
        done."""
        if _BESIDE[0]:
            return self._in(*STAGING, str(output_dir or name))
        return self.target_place(name, output_dir)

    def put_in_place(self, name, output_dir=None):
        """A target's folder as this run built it put in the place of the
        one an earlier run left, whole: a page the book no longer has
        isn't left in it, and a build that stops leaves the earlier
        folder as it was. A folder that isn't empty can't be replaced in
        one step, so it's two: the earlier folder to output/work/replaced/,
        then the new one into its place, and the earlier one deleted (it
        isn't kept: replaced/ holds it for the moment of the swap). A
        run stopped between the two is put right by the next (settle).
        Nothing was built (no folder in staging): nothing is done."""
        folder = str(output_dir or name)
        return _swap(self._in(*STAGING, folder), self.target_place(name, output_dir),
                     self._in(*REPLACED, folder))

    def _package(self, package=None):
        """The package no file names is the book's cartridge, or another
        part's, named for the part."""
        if not package:
            part = self.part()
            package = "cartridge" if part == BOOK else f"cartridge-{part}"
        return str(package)

    def put_package_in_place(self, package=None):
        """A package's folder as this run built it put in the place of
        the one an earlier run left, as a target's is (put_in_place)."""
        package = self._package(package)
        return _swap(self._in(*PACKAGE_STAGING, package), self._in("output", "packages", package),
                     self._in(*REPLACED, "packages", package))

    def package_file(self, name, package=None):
        """A file of a package's, in its folder, or, in a run that
        builds beside (build_beside), in the folder it's built in."""
        package = self._package(package)
        if _BESIDE[0]:
            return os.path.join(self._made(*PACKAGE_STAGING, package), str(name))
        return os.path.join(self._made("output", "packages", package), str(name))

    def run_dir(self, part=None):
        part = self.part(part)
        return self._made("output", "work", "parts", part)

    def _unnamed(self, value, part=None):
        """Why the settings may not name value, or None when they may.

        A setting's path is read from the project's top and nowhere else:
        one name is one file, so nothing put among the sources (which may
        be a publisher's package, unpacked) can stand in for a file the
        settings name. It may lead to the top, to a folder of the
        person's own there, or into the sources of the part being built,
        when it says so (src/book/preamble.md). It may not lead out of
        the project, a link followed; into what a run wrote, what was
        taken out of the sources, the sidecars, the publisher's files, or
        another part; or to a name beginning with a dot, which is where
        a checkout keeps what was never meant for a book."""
        value = str(value)
        if not value.strip() or "\0" in value:
            return "which is no file's name"
        if os.path.isabs(value) or value.startswith(("\\", "~")) \
                or (len(value) > 1 and value[1] == ":"):
            return "a full path, where a setting's path is from the project's folder"
        root = os.path.realpath(self.root)
        real = os.path.realpath(os.path.join(root, value))
        if real == root or not real.startswith(root.rstrip(os.sep) + os.sep):
            return "which leads out of the project's folder"
        names = os.path.relpath(real, root).split(os.sep)
        written = [n for n in value.replace("\\", "/").split("/") if n not in ("", ".")]
        if any(n.startswith(".") for n in names + written):
            return "which has a name beginning with a dot"
        first = names[0].casefold()
        if first in NOT_NAMED:
            return f"which is in {names[0]}/"
        if first == "src":
            own = self.part(part)
            if len(names) < 3 or names[1] != own:
                return f"which is in src/ and not among the sources of the part built (src/{own}/)"
        return None

    def named(self, value, part=None, setting=None):
        """The file or folder a setting names, from the project's top;
        a path the settings may not name stops the run (_unnamed)."""
        why = self._unnamed(value, part)
        if why:
            raise Refused(
                f"{setting or 'A setting'} names {value}, {why}. A file a setting names is "
                "kept in the project's folder: at its top, in a folder of its own there "
                f"(templates/), or among the sources of the part being built (src/"
                f"{self.part(part)}/); copy it there and name the copy.")
        return self._in(str(value))

    def named_file(self, value, part=None):
        if self._unnamed(value, part):
            return None
        path = self._in(str(value))
        return path if os.path.isfile(path) else None

    def reference_folders(self, part=None):
        part = self.part(part)
        return [self.run_dir(part), self.sources(part)]

    def originals(self, part=None):
        part = self.part(part)
        return (".", os.path.relpath(self.sources(part), self.run_dir(part)))


# kpathsea's search paths for a face's file, OpenType and TrueType.
FONT_PATHS = ("OPENTYPEFONTS", "TTFONTS")


def is_tree(folder):
    """Whether a folder is a project: it has a src/ that holds at least
    one folder and no file, since a part is a folder there and nothing
    else belongs beside the parts. A book kept in one folder with a src/
    of its own (a course's documents in src/, their shared files in
    folders below) has files there, and isn't one. A dot file isn't
    counted: a .gitkeep or a .DS_Store says nothing of the layout."""
    src = os.path.join(folder, "src")
    try:
        entries = [e for e in os.scandir(src) if not e.name.startswith(".")]
    except OSError:
        return False
    return any(e.is_dir() for e in entries) and all(e.is_dir() for e in entries)


def not_a_project(folder):
    """Why a folder isn't a project and what to do about it, as a
    tool's message less its last sentence, or None for one that is. A
    tool that builds stops on such a folder: it's never read as a book
    kept in one folder, whose every file would be the book's."""
    if is_tree(folder):
        return None
    src = os.path.join(folder, "src")
    try:
        loose = sorted(e.name for e in os.scandir(src)
                       if not e.name.startswith(".") and not e.is_dir())
    except OSError:
        loose = None
    if loose:
        why = ("its src/ holds files of its own (" + ", ".join(loose[:3])
               + (", ..." if len(loose) > 3 else "") + "), and no file belongs beside the "
               "parts' folders there")
    elif loose is None:
        why = "it has no src/"
    else:
        why = "its src/ holds no part's folder"
    return (f"{folder} isn't a project: {why}. A project keeps each part's sources in a "
            "folder of its own under src/ (src/book/ for a book, src/slides/ for decks), "
            "its sidecars in sidecars/<part>/, and its settings files at the top. For a "
            "book kept in one folder, as earlier versions read it, util/move-to-src.py -d "
            f"{folder} moves it into that layout, and with --dry-run says what it would do "
            "first. For a new book, make src/book/ and put its sources there.")


# The variable by which a run tells the tools it starts which folder is
# the project's, for name_from_project. It decides how a path is printed
# and nothing else.
NAMED_FROM = "TEXTBOOKIMPROVER_NAMED_FROM"


class _NamedFromProject:
    """A stream that prints a file of the project's by its path from the
    project's folder (name_from_project)."""

    def __init__(self, stream, roots):
        self._stream = stream
        # A path of the project's: the folder, a separator, and a name
        # after it. The folder itself, and a folder merely beginning with
        # its name, are left as they are.
        self._inside = re.compile(
            "(?:" + "|".join(re.escape(root + os.sep) for root in roots) + r")(?=\.?\w)")

    def write(self, text):
        # A command a run echoes ("+ pandoc ...") is run in another
        # folder, and is printed as it was run.
        if not text.startswith("+ "):
            text = self._inside.sub("", text)
        return self._stream.write(text)

    def __getattr__(self, name):
        return getattr(self._stream, name)


def name_from_project(root=None, stdout=False):
    """Have this program's messages name a file of the project's by its
    path from the project's folder (output/reports/book/x.csv), as the
    pages on a project's folders do, and not by its whole path, which is
    longer, differs from one computer to the next, and tells whoever
    reads the messages where on the computer the project is kept. root
    is the project's folder; left out, it's the one the run that started
    this program named (NAMED_FROM), and with neither nothing changes. A
    program that starts others gives root, which they inherit.

    What's written to standard error is a message. Standard output is
    left as it is unless stdout says it holds messages too: a tool whose
    standard output is read by the run that started it (the files
    split-pages.py, build-epub.py, and build-pdf.py wrote, a line each)
    writes whole paths there, which are read from another folder."""
    if root is not None:
        os.environ[NAMED_FROM] = os.path.abspath(root)
    root = os.environ.get(NAMED_FROM, "")
    if not os.path.isabs(root) or not os.path.isdir(root):
        return
    roots = sorted({os.path.abspath(root), os.path.realpath(root)}, key=len, reverse=True)
    if any(os.path.dirname(one) == one for one in roots):   # the file system's root
        return
    for name in ("stderr",) + (("stdout",) if stdout else ()):
        stream = getattr(sys, name)
        if stream is not None and not isinstance(stream, _NamedFromProject):
            setattr(sys, name, _NamedFromProject(stream, roots))


# The file in output/ that says a run made the folder, and what it holds:
# a run writes into output/ and replaces what's there, so it takes only a
# folder it made itself.
MARKER = ".textbookimprover"
MARKER_TEXT = ("TextbookImprover writes this folder: everything in it is made from the "
               "project's sources and settings, and deleting it is always safe.\n")
_LOCKS = []


def claim_output(folder, nothing="Nothing was converted."):
    """Make the project's output/ this run's: an output/ that holds
    something and wasn't made by a run stops it, and a new or empty one
    gets the marker. Nothing in a folder that isn't a project, which
    has no output/. nothing is the message's last sentence."""
    project = of(folder)
    if not isinstance(project, Tree):
        return None
    output = project.top("output")
    marker = os.path.join(output, MARKER)
    if os.path.islink(output) or (os.path.lexists(output) and not os.path.isdir(output)):
        raise Refused(f"{output} is a link or a file, where a project keeps the folder a "
                      "run writes. Move it away and run this again.")
    if os.path.isdir(output) and not os.path.isfile(marker) and os.listdir(output):
        raise Refused(
            f"{output} holds files and wasn't made by a run (it has no {MARKER}). A run "
            "writes into output/ and replaces what's there, so it takes only a folder it "
            "made. Move or rename the folder; if an earlier version's run made it, delete "
            f"it. {nothing}")
    os.makedirs(output, exist_ok=True)
    if not os.path.isfile(marker):
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(MARKER_TEXT)
    return marker


def lock(folder, nothing="Nothing was converted."):
    """Hold the project for this run: a second
    run in the same project stops while the first goes, since both would
    write the same files. The lock is the operating system's on
    output/work/lock, let go when the run ends however it ends; where
    there's no such lock (Windows itself), there's none."""
    project = of(folder)
    if not isinstance(project, Tree):
        return None
    try:
        import fcntl
    except ImportError:
        return None
    work = project.top("output", "work")
    os.makedirs(work, exist_ok=True)
    path = os.path.join(work, "lock")
    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip()
        handle.close()
        raise Refused(
            f"Another run is going in this project ({os.path.abspath(project.root)})"
            + (f", process {holder}" if holder.isdigit() else "")
            + f". Wait for it to end, or stop it, and run this again. {nothing}") from None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    _LOCKS.append(handle)          # kept open, and so held, until the run ends
    return path


# The folders of a project that a run reads or writes whole. One that is
# a link would take the run wherever it leads, out of the project too: a
# project unpacked with output as a link would have the link's target
# written and emptied, and one with src/book as a link would have another
# folder's files read as the book's.
OWN_FOLDERS = ("src", "sidecars", "output", "originals", "upstream")

# What output/ keeps for itself, which no target's folder is named.
OUTPUT_OWN = ("reports", "work", "packages")


def refused_link(folder, parts=()):
    """The first of a project's own folders that is a link, as a message,
    or None: src/, sidecars/, output/, originals/, and upstream/, a part's
    folder in each of the first two, output/work/, and under it tmp/,
    staging/ and replaced/ and their folders for targets and packages."""
    names = list(OWN_FOLDERS) + [os.path.join("output", "work")] + [
        os.path.join("output", "work", *below)
        for below in (("tmp",), ("staging",), ("staging", "targets"), ("staging", "packages"),
                      ("replaced",), ("replaced", "packages"))]
    for part in parts:
        names += [os.path.join("src", part), os.path.join("sidecars", part)]
    for name in names:
        path = os.path.join(folder, name)
        if os.path.islink(path):
            return (f"{path} is a link (to {os.readlink(path)}), where a project keeps "
                    "a folder of its own: a run would read or write wherever it leads. Put "
                    "the folder itself there")
    return None


def tex_tree():
    """The TeX tree's folder, where kpsewhich says, or None."""
    kpsewhich = shutil.which("kpsewhich")
    if not kpsewhich:
        return None
    done = subprocess.run([kpsewhich, "-var-value=TEXMFROOT"], capture_output=True,
                          text=True, stdin=subprocess.DEVNULL)
    found = done.stdout.strip()
    return os.path.realpath(found) if found else None


def _holds(folder, path):
    folder, path = os.path.realpath(folder), os.path.realpath(path)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def refused_root(root, home=None, own=None, tex=tex_tree):
    """Why root can't be a project's folder, or None. Everything in a
    project's folder is the project's to read, so a folder that holds
    more than a book (a home folder's keys, another project, the programs
    a run starts) can't be one: a hostile book's ![](.ssh/id_rsa) would
    be inside it. home, own (TextbookImprover's folder), and tex (what
    finds the TeX tree) are given by a check."""
    real = os.path.realpath(root)
    home = os.path.realpath(home or os.path.expanduser("~"))
    own = own or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if real == os.sep:
        return "it's the file system's root"
    if real == home:
        return "it's your home folder; make a folder for the book and run it there"
    if re.match(r"^/mnt/[a-zA-Z](/|$)", real):
        return ("it's on a Windows drive (" + real[:6] + "); WSL reads those slowly and "
                "can't keep their files' permissions. Copy the book into your WSL home")
    if os.pathsep in real:
        return ("its path holds a colon, which TEXINPUTS and Pandoc's resource path take "
                "as a separator")
    if _holds(real, home):
        return "it holds your home folder"
    if _holds(real, own):
        return "it holds TextbookImprover's own folder"
    tree = tex() if tex else None
    if tree and _holds(real, tree):
        return "it holds the TeX tree"
    parent = os.path.dirname(real)
    while parent and parent != os.path.dirname(parent):
        marker = os.path.join(parent, "output", ".textbookimprover")
        if os.path.isfile(marker) or (os.path.isdir(os.path.join(parent, "src")) and any(
                os.path.isfile(os.path.join(parent, name))
                for name in (PROJECT_NAME, CONFIG_NAME, PACKAGING_NAME))):
            return f"it's inside another project, {parent}"
        parent = os.path.dirname(parent)
    return None


def inside_project(folder):
    """The project a folder is in the sources or the outputs of (the
    nearest folder above it named src or output whose own parent holds
    src/ and a settings file, or a marked output/), or None: a tool run
    there is told where the project is, and doesn't adopt it."""
    here = os.path.realpath(folder)
    while here != os.path.dirname(here):
        parent = os.path.dirname(here)
        if os.path.basename(here) in ("src", "output") and (
                os.path.isfile(os.path.join(parent, "output", ".textbookimprover"))
                or (os.path.isdir(os.path.join(parent, "src")) and any(
                    os.path.isfile(os.path.join(parent, name))
                    for name in (PROJECT_NAME, CONFIG_NAME, PACKAGING_NAME)))):
            return parent
        here = parent
    return None


_KNOWN = {}
# The part this run builds, when the driver has said: a run builds one
# part, and every path asked for without a part's name is that part's.
_PART = [None, None]


def by_hand(folder, nothing="Nothing was built."):
    """For a tool that builds, run by hand in a project and not started
    by a run: what a run does before it writes anything, done here. The
    folder is one a project may be (refused_root), none of its own
    folders is a link (refused_link), output/ is one a run made
    (claim_output), no other run is going (lock), what a stopped run left
    of its builds is put right (settle), and this process's temporary
    files are kept in the project (use_tmp). Stops with the reason,
    nothing its last sentence; returns the notes to print, one for each
    folder put back."""
    root = os.path.abspath(folder)
    why = refused_root(root)
    if why:
        raise Refused(f"{root} can't be a project's folder: {why}. {nothing}")
    try:
        parts = sorted(entry.name for entry in os.scandir(os.path.join(root, "src")))
    except OSError:
        parts = []
    why = refused_link(root, parts)
    if why:
        raise Refused(f"{why}. {nothing}")
    claim_output(root, nothing)
    lock(root, nothing)
    use_tmp(root)
    return [f"NOTE: output/{name}/ is put back as it was: an earlier run stopped while "
            "replacing it." for name in settle(root)]


def set_part(part, folder=None):
    """Make part the one every path is asked of in this run: the driver
    says so once it knows which part it builds, and passes --part to each
    script it starts, which says so too, each with the project's folder."""
    if part is not None and not PART_NAME.match(str(part)):
        raise Refused(f"{part!r} can't be a part's name: a lowercase letter, then lowercase "
                      "letters, digits, - and _.")
    _PART[:] = [str(part) if part else None, folder if part else None]


def run_part():
    """The part this run builds, when the driver has said, or None."""
    return _PART[0]


def contents_apply():
    """Whether the project's contents and numbering are this run's
    part's: they order and number the book's pages, so a run of another
    part (its decks) has neither."""
    if not _PART[0] or _PART[1] is None:
        return True
    project = of(_PART[1])
    return not isinstance(project, Tree) or _PART[0] == project.default_part()


def add_part_option(parser):
    """The --part option of a script the driver starts for one part."""
    parser.add_argument("--part", default=None, metavar="NAME",
                        help="the part of the project to work on, as convert.py passes "
                             "it; the book's when left out")


def of(folder="."):
    """The Project for a folder, the same object each time it's asked
    for; a Project is given back as it is."""
    if isinstance(folder, Project):
        return folder
    if folder not in _KNOWN:
        _KNOWN[folder] = (Tree if is_tree(folder) else Project)(folder)
    return _KNOWN[folder]


def forget(folder):
    """Ask again what layout a folder is in, the next time it's asked
    for: for the run that lays a project out itself, by making its parts'
    folders, after it had asked."""
    _KNOWN.pop(folder, None)


# -- a target built beside its folder ----------------------------------------
#
# A run builds each target in output/work/staging/targets/<target>/ and
# puts the folder in output/<target>/'s place when the build is done, so
# that a build that fails or is stopped leaves the last good output, and
# a target's folder holds one build's files and no earlier one's.

STAGING = ("output", "work", "staging", "targets")
PACKAGE_STAGING = ("output", "work", "staging", "packages")
REPLACED = ("output", "work", "replaced")
_STAGED_IN = ((os.path.join(*STAGING) + os.sep, "output"),
              (os.path.join(*PACKAGE_STAGING) + os.sep, os.path.join("output", "packages")))
_BESIDE = [False]


def build_beside(folder, on=True):
    """Have this process build each target of the project beside its
    folder: target_dir answers the folder under
    output/work/staging/ until put_in_place swaps it in. Said by the run
    and by each builder the run starts; a builder run by hand writes the
    target's folder itself, as it did. Nothing in a folder that isn't a
    project."""
    _BESIDE[0] = bool(on) and isinstance(of(folder), Tree)
    return _BESIDE[0]


def builds_beside():
    """Whether this process builds each target beside its folder."""
    return _BESIDE[0]


def adopt(sample, place, verb=None):
    """What a person does to use a sample a run wrote, as a message says
    it: "rename it to project.yaml" where the sample lies beside the file
    it stands for, and "move it to ./project.yaml" where it's in a folder
    of the run's own, which nothing reads a setting from. verb, the same
    as the message's last words on it ("renaming it", "moving it there")."""
    beside = os.path.dirname(os.path.abspath(sample)) == os.path.dirname(os.path.abspath(place))
    if verb:
        return "renaming it" if beside else "moving it there"
    return f"rename it to {os.path.basename(place)}" if beside else f"move it to {place}"


def placed(path):
    """A path in a target's or a package's folder as a message names it:
    where it will be once the folder is in place, not where it's built."""
    for built, kept in _STAGED_IN:
        head, found, rest = str(path).partition(built)
        if found and (not head or head.endswith(os.sep)):
            return os.path.join(head, kept, rest)
    return path


def _swap(built, place, kept):
    """built put in place's stead by two renames, what was there held in
    kept between them and then deleted; place. Nothing where nothing was
    built, or the process doesn't build beside."""
    if not _BESIDE[0] or not os.path.isdir(built) or os.path.islink(built):
        return place
    try:
        _delete(kept)
        os.makedirs(os.path.dirname(kept), exist_ok=True)
        os.makedirs(os.path.dirname(place), exist_ok=True)
        if os.path.lexists(place):
            os.rename(place, kept)       # a link is moved, never followed
        os.rename(built, place)
        _delete(kept)
        for emptied in (os.path.dirname(kept), os.path.dirname(os.path.dirname(kept)),
                        os.path.dirname(built), os.path.dirname(os.path.dirname(built))):
            if os.path.basename(emptied) != "work" and os.path.isdir(emptied) \
                    and not os.listdir(emptied):
                os.rmdir(emptied)
    except OSError as exc:
        raise Refused(f"{place} couldn't be replaced by what this run built ({exc}). "
                      f"What was built is in {built}; an earlier folder, where there "
                      f"was one, is there still or in {kept}, and the next run puts "
                      "it back.") from None
    return place


def _delete(path):
    """A folder and what it holds, or a file or link, no link followed."""
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def settle(folder):
    """Put right what a stopped run left of its builds, in the layout
    with src/, before this run builds anything: a folder in
    output/work/replaced/ goes back to output/ when the target's folder
    is missing there (the run stopped between a swap's two steps), and is
    deleted when it isn't (it stopped after them), a package's folder
    under replaced/packages/ likewise; every unfinished build in
    output/work/staging/ is deleted. The names put back, as a list (a
    package's as packages/<name>).
    The marker and the lock come first, as for the temporary folder; only
    a folder's name that a target's can be is put back."""
    project = of(folder)
    if not isinstance(project, Tree):
        return []
    back = []
    kept = project.top(*REPLACED)
    for path in (kept, project.top("output", "work", "staging")):
        if os.path.islink(path) or (os.path.lexists(path) and not os.path.isdir(path)):
            raise Refused(f"{os.path.abspath(path)} is a link or a file, where a run keeps "
                          "the folders it's building. Move it away and run this again.")
    def restore(held, place_in, label):
        for name in sorted(os.listdir(held)):
            was = os.path.join(held, name)
            place = project.top(*place_in, name)
            if PART_NAME.match(name) and len(name) <= 64 and os.path.isdir(was) \
                    and not os.path.islink(was) and not os.path.lexists(place) \
                    and (place_in != ("output",) or name not in OUTPUT_OWN):
                os.makedirs(os.path.dirname(place), exist_ok=True)
                os.rename(was, place)
                back.append(label + name)
            else:
                _delete(was)
    if os.path.isdir(kept):
        packages = os.path.join(kept, "packages")
        if os.path.isdir(packages) and not os.path.islink(packages):
            restore(packages, ("output", "packages"), "packages/")
        restore(kept, ("output",), "")
    _delete(project.top("output", "work", "staging"))
    return back


# -- temporary files ---------------------------------------------------------
#
# Every temporary folder and file a script makes is made here, with
# tempfile's own names and arguments, so that where they go is decided in
# one place.

def use_tmp(folder, empty=True):
    """Keep this run's temporary files in the project, in
    output/work/tmp/: emptied when a run starts (not for a run of
    one part that a project's run started, which shares its folder), and
    named to this process and every program it starts as the temporary
    folder (TMPDIR). What an interrupted run leaves is then inside the
    project, where the next run clears it, and nothing of a book's is
    written to a folder other users of the machine share. The marker and
    the lock come first: the folder is emptied only in an output/ a run
    made, by the one run that holds it. Nothing in a folder that isn't a
    project."""
    project = of(folder)
    if not isinstance(project, Tree):
        return None
    path = os.path.abspath(project.top("output", "work", "tmp"))
    if os.path.islink(path) or (os.path.lexists(path) and not os.path.isdir(path)):
        raise Refused(f"{path} is a link or a file, where a run keeps its temporary files. "
                      "Move it away and run this again.")
    if empty and os.path.isdir(path):
        shutil.rmtree(path)           # never through a link: rmtree follows none
    os.makedirs(path, exist_ok=True)
    os.environ["TMPDIR"] = path
    tempfile.tempdir = None           # asked again, now that TMPDIR is set
    return path


def mkdtemp(suffix=None, prefix=None, dir=None):
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)


def mkstemp(suffix=None, prefix=None, dir=None, text=False):
    return tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir, text=text)


def TemporaryDirectory(*args, **kwargs):
    return tempfile.TemporaryDirectory(*args, **kwargs)


def NamedTemporaryFile(*args, **kwargs):
    return tempfile.NamedTemporaryFile(*args, **kwargs)
