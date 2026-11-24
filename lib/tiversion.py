"""
tiversion.py -- TextbookImprover's version, in one place, and what a build
record says of the copy that ran: the version, the commit, whether the
checkout had changes, and a digest of its own files.

The version names a release on the release's commit alone. From the
commit after it, it names the next release with ".dev" after it (PEP
440's development release, "0.11.dev" after 0.10), so a copy of the code
between releases never says it's the last one, even one with no Git to
name its commit, as GitHub's archive of a branch has none; the release
commit drops ".dev". A copy is told apart from another of the same
version by its commit and its digest, and one with no Git by its digest
alone (stamps.own_digest, over bin/, lib/, and vendor/, so the same files
give the same digest from a checkout or an archive).

The moment a run gives every program it starts is its SOURCE_DATE_EPOCH:
the person's where it's set, so a build made again under it writes the
same bytes, and otherwise the moment the run started (one_moment), set for
the run and every program it starts, so the EPUB, the Word files, the PDF,
and the zips are dated alike, not each at its own moment. A moment the run
set is marked (RUN_EPOCH), so that what records the person's choice, a
target's stamp, takes it as unset (given_epoch) and doesn't build every
target again on every run.

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

import os
import shutil
import subprocess
import time

VERSION = "0.11.dev"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The variable by which a run marks the SOURCE_DATE_EPOCH it set itself,
# its value the same moment, for the programs it starts (one_moment).
RUN_EPOCH = "TEXTBOOKIMPROVER_RUN_EPOCH"


def one_moment(environ=None):
    """(seconds, where it came from) for the run: SOURCE_DATE_EPOCH where
    the person set it to a whole number of seconds ("SOURCE_DATE_EPOCH"),
    or one a run that started this one set ("the run's start"); otherwise
    now, set as SOURCE_DATE_EPOCH and marked as the run's own in environ
    (os.environ by default), so every program the run starts has it."""
    environ = os.environ if environ is None else environ
    value = environ.get("SOURCE_DATE_EPOCH", "").strip()
    if value.isdigit():
        own = environ.get(RUN_EPOCH, "") == value
        return int(value), ("the run's start" if own else "SOURCE_DATE_EPOCH")
    seconds = int(time.time())
    environ["SOURCE_DATE_EPOCH"] = environ[RUN_EPOCH] = str(seconds)
    return seconds, "the run's start"


def given_epoch(environ=None):
    """SOURCE_DATE_EPOCH as the person gave it, "" where the run set it
    itself (one_moment) or nobody did."""
    environ = os.environ if environ is None else environ
    value = environ.get("SOURCE_DATE_EPOCH", "")
    return "" if value and environ.get(RUN_EPOCH) == value else value


def describe(root=None):
    """What a build record says of this copy of TextbookImprover: its
    version; its commit, or "none" for a copy that isn't a Git checkout or
    has no git to ask; whether the checkout's tracked files had changes
    ("yes", "no", or "unknown"); and its files' digest."""
    import stamps
    root = root or ROOT
    commit, changed = "none", "unknown"
    git = shutil.which("git")
    if git and os.path.exists(os.path.join(root, ".git")):
        try:
            done = subprocess.run([git, "-C", root, "rev-parse", "HEAD"], capture_output=True,
                                  text=True, timeout=30, stdin=subprocess.DEVNULL)
            if done.returncode == 0 and done.stdout.strip():
                commit = done.stdout.strip()
                status = subprocess.run([git, "-C", root, "status", "--porcelain",
                                         "--untracked-files=no"], capture_output=True,
                                        text=True, timeout=60, stdin=subprocess.DEVNULL)
                if status.returncode == 0:
                    changed = "yes" if status.stdout.strip() else "no"
        except (OSError, subprocess.SubprocessError):
            pass
    return {"version": VERSION, "commit": commit, "changed": changed,
            "digest": stamps.own_digest(root)}
