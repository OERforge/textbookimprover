"""A fixture laid out as a project: the suites' way of asking where a
project's files are.

A suite makes a folder for a case, calls project() on it, and asks what
that returns (lib/projectpaths.py's object for the folder) where a source
goes and where a run wrote a page, a report, or a target's file. No suite
joins such a path itself, so where a project keeps things is said in one
place.
"""

import os
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
