"""A fixture laid out as a project: the suites' way of asking where a
project's files are.

A suite makes a folder for a case, calls project() on it, and asks what
that returns (lib/projectpaths.py's object for the folder) where a source
goes and where a run wrote a page, a report, or a target's file. No suite
joins such a path itself, so where a project keeps things is said in one
place.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "lib"))

import projectpaths  # noqa: E402


def project(folder, part="book"):
    """The project a folder is, its part's folders made first: src/<part>/
    is what makes a folder a project laid out with src/, and a sidecar is
    written to sidecars/<part>/ by a case before any run makes it."""
    for kept in ("src", "sidecars"):
        os.makedirs(os.path.join(folder, kept, part), exist_ok=True)
    return projectpaths.of(folder)


# What a book written in one folder keeps at its top when it's laid out:
# its settings, and the definitions' file a LaTeX book's run reads there.
TOP = ("project.yaml", "conversion.yaml", "packaging.yaml", "pdf-layout.yaml",
       "latex-conversion-macros.tex", "upstream")


def settle(folder, part="book", top=()):
    """A folder a case wrote a book into, file by file, laid out as a
    project before its first run: the settings (and the names in top,
    for a file a setting names) stay at the top, a CSV file is a
    sidecar, and everything else is the part's sources. A folder laid
    out already is left as it is. Returns the paths of either."""
    if not projectpaths.is_tree(folder):
        names = [n for n in os.listdir(folder) if n not in TOP and n not in top]
        # Through a folder of its own, since a book may keep a src/ itself.
        staged = os.path.join(folder, ".laying-out")
        sources = os.path.join(staged, "src", part)
        sidecars = os.path.join(staged, "sidecars", part)
        os.makedirs(sources)
        os.makedirs(sidecars)
        for name in names:
            os.rename(os.path.join(folder, name), os.path.join(
                sidecars if name.endswith(".csv") else sources, name))
        for kept in ("src", "sidecars"):
            os.rename(os.path.join(staged, kept), os.path.join(folder, kept))
        os.rmdir(staged)
        projectpaths.forget(folder)
    return projectpaths.of(folder)


# --------------------------------------------------------------------------
# a book written into a plain folder, laid out when a tool first runs in it
# --------------------------------------------------------------------------
# For a suite whose cases write a book file by file and then run a tool
# in its folder: started() in place of subprocess.run lays the folder out
# first, and place() in place of os.path.join answers where a file is,
# before the laying out (the names joined) and after.

SETTINGS = ("project.yaml", "conversion.yaml", "packaging.yaml", "pdf-layout.yaml")
REPORTS = ("output-check.csv", "fidelity.csv", "-sample.yaml", "-sample.csv", "-new.csv",
           "-report.csv", "-census.csv", "-repaired.csv", "-missing.csv",
           "-unpacked.yaml")
TOOLS = ("convert.py", "build-pdf.py", "build-epub.py", "build-cartridge.py")


def named_at_top(folder):
    """The files and folders at a book's top that its conversion.yaml
    names as a setting's value (a metadata file, a template's folder),
    which stay there when the folder is laid out."""
    path = os.path.join(folder, "conversion.yaml")
    if not os.path.isfile(path):
        return ()
    import yaml
    with open(path, encoding="utf-8") as fh:
        try:
            settings = yaml.safe_load(fh)
        except yaml.YAMLError:
            return ()
    found = set()

    def leaves(node):
        if isinstance(node, dict):
            for value in node.values():
                leaves(value)
        elif isinstance(node, list):
            for value in node:
                leaves(value)
        elif isinstance(node, str) and node and not os.path.isabs(node):
            first = node.replace("\\", "/").split("/")[0]
            if first not in ("", ".", "..") and os.path.lexists(os.path.join(folder, first)):
                found.add(first)
    leaves(settings)
    return tuple(sorted(found))


SOURCES = (".docx", ".md", ".html", ".htm", ".adoc", ".tex", ".pptx", ".odp", ".ppt",
           ".key", ".ipynb", ".epub", ".imscc", ".warc", ".zip")


def is_book(folder):
    """Whether a plain folder is a book's, to lay out: it holds a settings
    file or a source at its top. Never the system's temporary folder, a
    home folder, the root, or the repository, whatever they hold: a tool
    run from the folder above a book's is run there."""
    import tempfile
    if not folder or not os.path.isdir(folder) or projectpaths.is_tree(folder):
        return False
    real = os.path.realpath(folder)
    kept_out = {os.path.realpath(p) for p in (
        tempfile.gettempdir(), "/tmp", os.path.expanduser("~"), os.sep,
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}
    if real in kept_out:
        return False
    names = os.listdir(folder)
    return any(n in SETTINGS[:3] for n in names) \
        or any(n.lower().endswith(SOURCES) and os.path.isfile(os.path.join(folder, n))
               for n in names)


def settled(folder):
    """The folder, laid out as a project if it's a book's that isn't."""
    if is_book(folder):
        settle(folder, top=named_at_top(folder))
    return folder


def started(arguments, cwd=None, **options):
    """subprocess.run, a book's folder laid out first where the program
    is one of the tools: the folder -d names, or the one it's run in. Another
    program run in a book's folder (Pandoc on a page, a shell's pipeline)
    is run where the book's sources are, once the folder is laid out."""
    listed = [] if isinstance(arguments, str) else list(arguments)
    if any(os.path.basename(str(a)) in TOOLS for a in listed if len(str(a)) < 400):
        # The folder -d names, or without one the folder it's run in:
        # never both, since a tool given -d may be run from anywhere.
        named = [listed[at + 1] for at, argument in enumerate(listed[:-1]) if argument == "-d"]
        for folder in named or [cwd]:
            settled(folder)
    elif cwd and projectpaths.is_tree(cwd) and not (
            listed and os.path.basename(str(listed[0])).startswith("python")):
        cwd = projectpaths.of(cwd).sources()
    return subprocess.run(arguments, cwd=cwd, **options)


def targets(folder):
    """The names of the folders a project's targets are written to under
    output/, as its conversion.yaml has them: a target's output_dir, or
    its name."""
    import yaml
    path = os.path.join(folder, "conversion.yaml")
    if not os.path.isfile(path):
        return {"html"}
    with open(path, encoding="utf-8") as fh:
        try:
            settings = yaml.safe_load(fh) or {}
        except yaml.YAMLError:
            return set()
    declared = settings.get("targets") if isinstance(settings, dict) else None
    if not isinstance(declared, dict):
        return {"html"}
    return {str((spec or {}).get("output_dir") or name) if isinstance(spec or {}, dict)
            else str(name) for name, spec in declared.items()}


def place(folder, *names):
    """Where a project keeps a file: its settings and a file a setting
    names at its top, a report with its part's, a target's file in the
    target's folder, and anything else among the part's sources. In a
    folder that isn't laid out yet, or isn't a book's, the names joined
    to it."""
    if not projectpaths.is_tree(folder):
        return os.path.join(folder, *names)
    paths = projectpaths.of(folder)
    first = names[0]
    if first in SETTINGS:
        return paths.top(*names)
    # A target's folder before a folder of that name at the top: a target
    # named src is written to output/src/.
    if first in targets(folder):
        if names[1:2] == ("intermediates",):
            # A target's own intermediates, where its settings differ.
            return os.path.join(folder, "output", "work", "targets", first, *names[2:])
        return os.path.join(folder, "output", first, *names[1:])
    if os.path.lexists(os.path.join(folder, first)):
        return paths.top(*names)
    # What a run has written is where it is: a report, a sidecar, an
    # intermediate, a source.
    kept = (os.path.join(folder, "output", "reports", "book"),
            os.path.join(folder, "sidecars", "book"),
            os.path.join(folder, "output", "work", "parts", "book"),
            os.path.join(folder, "src", "book"),
            # A target's archive, and the cartridge's files.
            os.path.join(folder, "output"),
            os.path.join(folder, "output", "packages", "cartridge"))
    for there in kept:
        if os.path.lexists(os.path.join(there, *names)):
            return os.path.join(there, *names)
    if len(names) == 1 and first.endswith(REPORTS):
        return os.path.join(kept[0], first)
    if len(names) == 1 and first.endswith(".json"):
        return os.path.join(kept[2], first)
    if os.path.isdir(os.path.join(folder, "output", first)) \
            and first not in ("work", "reports", "packages"):
        return os.path.join(folder, "output", first, *names[1:])
    if len(names) == 1 and first.endswith(".csv"):
        return paths.sidecar(first)
    return paths.source(*names)


def beside(folder, name):
    """A folder beside a book's, for a second book or a hand's own runs:
    a project can't hold another among its sources."""
    return folder.rstrip(os.sep) + "-" + name
