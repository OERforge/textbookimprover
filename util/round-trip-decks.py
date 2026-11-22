#!/usr/bin/env python3
"""
round-trip-decks.py -- PowerPoint decks converted to Markdown and back, and
each compared with the deck it was made from, slide by slide: the check
the deck reader (lib/pptxsource.py) is held to.

    round-trip-decks.py decks/              # every deck in the folder
    round-trip-decks.py decks/ --keep trip/ # and keep what the trip wrote

The folder is a project (its decks in src/<part>/, their sidecars in
sidecars/<part>/) or any folder holding decks and their sidecars. Its
decks, with its sidecars and its project.yaml, are converted by
convert.py through a markdown target; that Markdown, a deck written in
Markdown, through a pptx target; and each deck compared with its trip as
lib/deckcompare.py compares them, for its titles, text and formatting,
lists, tables, pictures and their alt text, equations, and notes. The
decks themselves aren't touched: the trip is made in two projects of its
own, in a folder of its own.

What Pandoc's PowerPoint writer doesn't write, and the pptx target doesn't
put back, is reported with the rest, as a difference: a merged cell. Exit
status is 0 when every deck came back the same, 1 when one didn't or a run
failed.

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
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import deckcompare      # noqa: E402
import pptxremediate    # noqa: E402
import projectpaths     # noqa: E402
import sidecars         # noqa: E402
from names import safe_stem     # noqa: E402

CONVERT = os.path.join(ROOT, "bin", "convert.py")
# The sidecars a deck's conversion reads its decisions from.
SIDECARS = ("image-alt.csv", "table-headers.csv", "slide-titles.csv", "reading-order.csv",
            "bare-links.csv", "math-keep.csv")


def deck_names(given):
    """The PowerPoint decks among a folder's sources, but for the lock
    files PowerPoint leaves beside an open one."""
    return sorted(n for n in os.listdir(given.sources()) if n.lower().endswith(".pptx")
                  and not n.startswith("~$"))


def convert(folder):
    """convert.py in folder, quietly; (return code, its messages)."""
    done = subprocess.run([sys.executable, CONVERT, "--quick", "--quiet"], cwd=folder,
                          capture_output=True, text=True)
    return done.returncode, done.stderr


def project(folder):
    """A project made in folder for the trip's decks, laid out with
    src/; its paths."""
    for kept in ("src", "sidecars"):
        os.makedirs(os.path.join(folder, kept, "slides"))
    return projectpaths.of(folder)


def trip(source, work):
    """The decks in source made Markdown in work/source, and that Markdown
    PowerPoint again in work/trip. Returns ({deck: its trip's file},
    messages of a run that failed)."""
    given = projectpaths.of(source)
    decks = deck_names(given)
    first = os.path.join(work, "source")
    there = project(first)
    for name in decks:
        shutil.copy2(given.source(name), there.source(name))
    # A sidecar that can't be read, said so already, isn't copied.
    for name in SIDECARS:
        if os.path.isfile(given.sidecar(name)) and not sidecars.unreadable(given.sidecar(name)):
            shutil.copy2(given.sidecar(name), there.sidecar(name))
    language = None
    if os.path.isfile(given.project_file()):
        import yaml
        with open(given.project_file(), encoding="utf-8") as fh:
            language = ((yaml.safe_load(fh) or {}).get("project") or {}).get("language")
    settings = ("project:\n  identifier: org.example.round-trip\n  title: Round trip\n"
                "  kind: slides\n" + ("  language: %s\n" % language if language else ""))
    if os.path.isfile(given.project_file()):
        shutil.copy2(given.project_file(), there.project_file())
    with open(there.config_file(), "w", encoding="utf-8") as fh:
        fh.write("targets:\n  md:\n    format: markdown\n")
    code, said = convert(first)
    if not os.path.isdir(there.target_dir("md")):
        return {}, said
    second = os.path.join(work, "trip")
    back = project(second)
    shutil.copytree(there.target_dir("md"), back.sources(), dirs_exist_ok=True)
    with open(back.project_file(), "w", encoding="utf-8") as fh:
        fh.write(settings)
    with open(back.config_file(), "w", encoding="utf-8") as fh:
        fh.write("targets:\n  decks:\n    format: pptx\n")
    code2, said2 = convert(second)
    made = {name: back.target_file("decks", safe_stem(name[:-5]) + ".pptx") for name in decks}
    return {k: v for k, v in made.items() if os.path.isfile(v)}, \
        (said if code else "") + (said2 if code2 else "")


def main():
    parser = argparse.ArgumentParser(
        description="Convert a folder's PowerPoint decks to Markdown and back, and compare "
                    "each with its trip.")
    parser.add_argument("folder", help="a folder of PowerPoint decks, with their sidecars")
    parser.add_argument("--keep", metavar="DIR",
                        help="write the trip in DIR, which must not exist, and keep it")
    args = parser.parse_args()
    source = os.path.abspath(args.folder)
    if args.keep and os.path.exists(args.keep):
        sys.exit("%s exists; --keep makes it." % args.keep)
    given = projectpaths.of(source)
    for name in SIDECARS:
        path = given.sidecar(name)
        said, why = sidecars.rewrite_as_utf8(path)
        if why:
            sys.exit(why)
        for line in said:
            print(line, file=sys.stderr)
    work = os.path.abspath(args.keep) if args.keep else tempfile.mkdtemp(prefix="round-trip-")
    os.makedirs(work, exist_ok=True)
    try:
        made, failed = trip(source, work)
        if failed:
            print(failed.rstrip(), file=sys.stderr)
        alts = pptxremediate.alt_rows(given.sidecar("image-alt.csv"))
        tables = pptxremediate.header_rows(given.sidecar("table-headers.csv"))
        titles = pptxremediate.title_rows(given.sidecar("slide-titles.csv"))
        orders = pptxremediate.order_rows(given.sidecar("reading-order.csv"))
        decks = deck_names(given)
        differing = 0
        for name in decks:
            if name not in made:
                print("%s: no trip was made" % name)
                differing += 1
                continue
            found = deckcompare.compare(
                deckcompare.read(given.source(name), work, alts=alts, tables=tables,
                                 titles=titles, orders=orders),
                deckcompare.read(made[name], work))
            print("%s: %s" % (name, "the same" if not found else
                              "%d difference(s)" % len(found)))
            for difference in found:
                first, second = deckcompare.first_difference(difference.first,
                                                             difference.second)
                print("  %s, %s:\n    %r\n    %r" % (difference.where, difference.what,
                                                     first, second))
            differing += bool(found)
        print("%d of %d deck(s) came back the same." % (len(decks) - differing, len(decks)))
        return 1 if differing or failed else 0
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
