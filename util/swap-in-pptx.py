#!/usr/bin/env python3
"""
swap-in-pptx.py -- make the PowerPoint file a run saved from a deck in
another format the deck itself, so it can be edited in PowerPoint.

    python3 util/swap-in-pptx.py --dry-run talk.odp   # say what it would do
    python3 util/swap-in-pptx.py talk.odp lecture.ppt
    python3 util/swap-in-pptx.py --all --part slides
    python3 util/swap-in-pptx.py talk.odp --from ~/Desktop/talk.pptx

Run it from the project's folder, or give -d. A run reads a deck in
OpenDocument's format (.odp) or PowerPoint 97-2003's (.ppt) by saving it
as PowerPoint through LibreOffice into the part's work folder
(output/work/parts/<part>/), and saves it again whenever the original
changes, so the original is the deck and the PowerPoint file is the
run's own: an edit made to that file is lost at the next save. To edit
a deck in PowerPoint from now on, make the PowerPoint file the deck:

  - The PowerPoint file the run saved from the deck as it is now is
    copied into src/<part>/, under the deck's PowerPoint name (talk.pptx
    for talk.odp). The sidecars' rows already name it so, and it's the
    file they were made from, so every row still finds what it names.
  - The original is moved to upstream/<part>/, and never replaced
    there, with a row of upstream/<part>/replaced-decks.csv: when, the
    deck, its SHA-256, the PowerPoint file and its SHA-256, and where
    that came from. upstream/<part>/ travels with the project, as the
    record of what the deck was.

From then on, edit the PowerPoint file in src/<part>/, which a run reads
as it reads any PowerPoint deck.

--from FILE takes a PowerPoint file of your own for one deck instead,
one PowerPoint itself saved from the original, say. PowerPoint and
LibreOffice may number a deck's slides and shapes differently, so the
sidecars' rows that name a slide or a shape by its number, or shapes by
their ids, are worth checking after.

WHAT IT TAKES IN

A deck at the top of src/<part>/, a file and not a link, with no
PowerPoint file of its name there already; a PowerPoint file that's a
zip holding ppt/presentation.xml, and, from the work folder, one saved
from the deck as it is now (saved-decks.json says so; run convert.py
first otherwise). upstream/<part>/ must be this tool's, or not there
yet: a folder there that a part's from names, or one without this
tool's record, is another part's upstream folder, and is left alone. It
waits for no run: one that's going stops it, as it would stop another
run.

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
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lib"))

import decksave                                      # noqa: E402
import projectpaths                                  # noqa: E402

RECORD = "replaced-decks.csv"
RECORD_FIELDS = ("date", "deck", "sha256", "now", "now_sha256", "from")


class Stop(Exception):
    """Why a deck can't be swapped, as a clause."""


def say(text=""):
    print(text, flush=True)


def is_powerpoint(path):
    """Whether a file is a PowerPoint deck as far as its package goes."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile, ValueError):
        return False
    return "ppt/presentation.xml" in names and "[Content_Types].xml" in names


def from_parts(root):
    """Each part's from, as project.yaml writes it, or [] where it can't
    be read: a run says what's wrong with the settings."""
    import yaml
    try:
        with open(projectpaths.of(root).project_file(), encoding="utf-8") as fh:
            parts = (yaml.safe_load(fh) or {})["project"]["parts"]
        return [str(value["from"]) for value in parts.values()
                if isinstance(value, dict) and value.get("from")]
    except (OSError, yaml.YAMLError, KeyError, TypeError, AttributeError):
        return []


class Swap:
    """The decks to swap and what to do with each: worked out by plan(),
    done by execute()."""

    def __init__(self, root, part, decks, every, given=None):
        self.root = os.path.realpath(root)
        self.project = projectpaths.of(self.root)
        self.part = self.project.part(part)
        projectpaths.set_part(self.part, self.root)
        self.source = self.project.sources(self.part)
        self.upstream = os.path.join(self.root, "upstream", self.part)
        self.decks = decksave.other_decks(self.root) if every else list(decks)
        self.given = given
        self.work = []           # (deck, its path, the PowerPoint file to copy, its name)

    def shown(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def plan(self):
        if not self.decks:
            raise Stop(f"src/{self.part}/ holds no deck in another format (.odp, .ppt)")
        self.check_upstream()
        here = {name.lower(): name for name in os.listdir(self.source)}
        for name in self.decks:
            self.work.append(self.check(name, here))

    def check_upstream(self):
        top = os.path.join(self.root, "upstream")
        if os.path.islink(top) or (os.path.lexists(top) and not os.path.isdir(top)):
            raise Stop("upstream/ is a link or isn't a folder, so nothing is moved into it")
        where = f"upstream/{self.part}"
        for value in from_parts(self.root):
            named = os.path.normpath(value).replace(os.sep, "/").lower()
            if named == where.lower() or named.startswith(where.lower() + "/"):
                raise Stop(f"a part's from names {value}, so {where}/ is that part's upstream "
                           "file, and the original deck can't go there; move or rename it, "
                           "and that part's from with it")
        if os.path.islink(self.upstream):
            raise Stop(f"{where} is a link, so nothing is moved into it")
        if os.path.lexists(self.upstream):
            if not os.path.isdir(self.upstream):
                raise Stop(f"{where} is there already and isn't a folder")
            if os.listdir(self.upstream) and not os.path.isfile(
                    os.path.join(self.upstream, RECORD)):
                raise Stop(f"{where}/ is there already without this tool's record "
                           f"({RECORD}), so it's another part's upstream folder, which is "
                           "never added to; move or rename it")

    def check(self, name, here):
        if os.path.basename(name) != name or name in (".", ".."):
            raise Stop(f"{name} isn't a deck's name in src/{self.part}/: give its name alone")
        if name.startswith(".") or name.startswith("~$"):
            raise Stop(f"{name} is a dot name or PowerPoint's lock file, not a deck")
        if not name.lower().endswith(decksave.EXTENSIONS):
            raise Stop(f"{name} isn't a deck in another format: this takes an .odp or a .ppt")
        path = os.path.join(self.source, name)
        if os.path.islink(path):
            raise Stop(f"src/{self.part}/{name} is a link, which this doesn't move")
        if not os.path.isfile(path):
            raise Stop(f"src/{self.part}/{name} isn't there")
        target = decksave.powerpoint_name(name)
        if target.lower() in here:
            raise Stop(f"src/{self.part}/{here[target.lower()]} is there already, and a run "
                       f"reads it in {name}'s place; move {name} out by hand if it's to go")
        if os.path.lexists(os.path.join(self.upstream, name)):
            raise Stop(f"upstream/{self.part}/{name} is there already, and is never replaced; "
                       "move or rename one of them")
        if self.given:
            if len(self.decks) != 1:
                raise Stop("--from gives one deck's PowerPoint file: name one deck with it")
            copy = self.given
            if os.path.islink(copy) or not os.path.isfile(copy):
                raise Stop(f"--from {copy} isn't a file, or is a link")
        else:
            copy = decksave.saved_path(self.root, target)
            if not decksave.current(self.root, name, target):
                why = ("the original has changed since a run saved it"
                       if os.path.isfile(copy) else "no run has saved it as PowerPoint yet")
                raise Stop(f"{name} has no PowerPoint file in output/work/parts/{self.part}/ "
                           f"saved from it as it is now ({why}); run convert.py, which saves "
                           "one, and then this again, or give one with --from")
        if not is_powerpoint(copy):
            raise Stop(f"{copy if self.given else self.shown(copy)} isn't a PowerPoint file "
                       "(a zip holding ppt/presentation.xml)")
        return name, path, copy, target

    def report(self):
        for name, _, copy, target in self.work:
            came = self.given if self.given else self.shown(copy)
            say(f"{name}: {came} copied to src/{self.part}/{target}, and {name} moved to "
                f"upstream/{self.part}/{name}.")

    def execute(self):
        os.makedirs(self.upstream, exist_ok=True)
        record = os.path.join(self.upstream, RECORD)
        for name, path, copy, target in self.work:
            place = os.path.join(self.source, target)
            # Copied beside its place under a dot name a run passes over,
            # then renamed in, so a run never finds half a deck.
            temporary = os.path.join(self.source, "." + target + ".swap")
            shutil.copyfile(copy, temporary)
            if os.path.lexists(place):
                os.remove(temporary)
                raise Stop(f"src/{self.part}/{target} appeared while this ran")
            os.replace(temporary, place)
            was, now = decksave.digest(path), decksave.digest(place)
            # The PowerPoint file first and the original after: stopped
            # between the two, a run reads the PowerPoint file in the
            # original's place, as it reads any beside its original.
            os.rename(path, os.path.join(self.upstream, name))
            new = not os.path.exists(record)
            with open(record, "a", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, RECORD_FIELDS)
                if new:
                    writer.writeheader()
                writer.writerow({
                    "date": datetime.datetime.now(datetime.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"),
                    "deck": name, "sha256": was, "now": target, "now_sha256": now,
                    "from": "--from" if self.given else self.shown(copy)})


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Make the PowerPoint file a run saved from a deck in another format "
                    "(.odp, .ppt) the deck itself, in src/<part>/, the original moved to "
                    "upstream/<part>/, so the deck can be edited in PowerPoint.")
    parser.add_argument("decks", nargs="*", metavar="DECK",
                        help="a deck in src/<part>/ by its name (talk.odp)")
    parser.add_argument("--all", action="store_true",
                        help="every deck in another format in src/<part>/")
    parser.add_argument("-d", "--dir", default=".",
                        help="the project's folder (default: this one)")
    projectpaths.add_part_option(parser)
    parser.add_argument("--from", dest="given", metavar="FILE",
                        help="a PowerPoint file of your own for the one deck named, in place "
                             "of the one a run saved")
    parser.add_argument("--dry-run", action="store_true",
                        help="say what it would do, and do nothing")
    args = parser.parse_args(argv)
    nothing = "Nothing was changed."
    if bool(args.decks) == args.all:
        say(f"Name the decks to swap, or give --all. {nothing}")
        return 2
    root = os.path.abspath(args.dir)
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
        work = Swap(root, args.part, args.decks, args.all, args.given)
        work.plan()
    except projectpaths.Refused as exc:
        say(str(exc))
        return 2
    except (Stop, OSError) as exc:
        say(f"{exc}. {nothing}")
        return 1
    work.report()
    if args.dry_run:
        say(f"\n{nothing[:-1]} (--dry-run).")
        return 0
    try:
        work.execute()
    except (Stop, OSError) as exc:
        say(f"{exc}. Stopped partway; upstream/{work.part}/{RECORD} lists each deck swapped.")
        return 1
    say(f"\nDone: {len(work.work)} deck(s) swapped, each original in upstream/{work.part}/ "
        f"and each swap in upstream/{work.part}/{RECORD}. Edit the PowerPoint file in "
        f"src/{work.part}/ from now on: it's the deck.")
    if args.given:
        say("The PowerPoint file came from --from, so check the sidecars' rows that name a "
            "slide or a shape by its number, or shapes by their ids: they may name others.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
