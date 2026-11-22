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
