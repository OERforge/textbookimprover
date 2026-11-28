#!/usr/bin/env python3
"""
check-inputs.py -- run a conversion under strace and check the inventory
of inputs against what it read: each file in the project, outside
output/, that the run read before writing it must be in the inventory
(lib/inputs.py), and each file the inventory lists as a source, a
sidecar, a setting, or a named file must have been read.

    python3 util/check-inputs.py -d PROJECT
    python3 util/check-inputs.py -d PROJECT -- --rebuild

What follows -- is passed to convert.py. The run is the project's own
run, in its sandbox where it has one, and writes output/ as any run does.
The inventory's upstream files and a files part's are listed as not read
without failing, since a run reads an upstream file only to unpack it and
never builds a files part. The project's manifest, ti-archive.yaml,
which a run reads to compare the inputs with, isn't one. Linux only, with strace installed; the
tracing costs about as long again as the run.

Exits 0 when the two agree, 1 when they don't, and 2 when the run
couldn't be traced or failed.

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
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import inputs  # noqa: E402
import projectarchive  # noqa: E402

CALL = re.compile(r'^(\d+)\s+(\w+)\((.*)\)\s+=\s+(-?\d+)(.*)$')
UNFINISHED = re.compile(r'^(\d+)\s+(\w+)\((.*) <unfinished \.\.\.>$')
RESUMED = re.compile(r'^(\d+)\s+<\.\.\. (\w+) resumed>(.*)$')
DIRFD = re.compile(r'^(?:AT_FDCWD|-?\d+)<([^>]*)>, ')
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
WRITES = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC")
# Not failures when unread: a run unpacks an upstream file only into an
# empty folder, and builds no files part.
UNREAD_EXPECTED = ("upstream", "files")
# Read and not inputs: the manifest a run compares the inputs with.
READ_NOT_INPUTS = (projectarchive.NAME,)


def _unescape(text):
    return text.encode("latin-1", "backslashreplace").decode("unicode_escape") \
        .encode("latin-1", "replace").decode("utf-8", "replace")


def _calls(trace):
    pending = {}
    with open(trace, errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            found = UNFINISHED.match(line)
            if found:
                pending[found.group(1)] = (found.group(2), found.group(3))
                continue
            found = RESUMED.match(line)
            if found and found.group(1) in pending:
                name, head = pending.pop(found.group(1))
                line = f"{found.group(1)} {name}({head}{found.group(3)}"
            found = CALL.match(line)
            if found and int(found.group(4)) >= 0:
                yield found.group(2), found.group(3)


def project_reads(trace, root):
    """The files in the project, outside output/, that the traced run
    read before it wrote them, each path from the project's folder with
    / between its names; and those it wrote there."""
    root = os.path.realpath(root)
    read, written, order = {}, {}, 0
    for name, args in _calls(trace):
        order += 1
        dirfd = DIRFD.match(args)
        rest = args[dirfd.end():] if dirfd else args
        quoted = STRING.match(rest)
        if not quoted:
            continue
        given = _unescape(quoted.group(1))
        if dirfd:
            path = os.path.normpath(os.path.join(dirfd.group(1), given))
        elif os.path.isabs(given):
            path = os.path.normpath(given)
        else:
            continue
        if not path.startswith(root + os.sep):
            continue
        relative = os.path.relpath(path, root).replace(os.sep, "/")
        if relative.split("/", 1)[0] == "output":
            continue
        tail = rest[quoted.end():]
        if name in ("open", "openat", "openat2", "creat"):
            if "O_DIRECTORY" in tail:
                continue
            if name == "creat" or any(flag in tail for flag in WRITES):
                written.setdefault(relative, order)
            else:
                read.setdefault(relative, order)
        elif name == "execve":
            read.setdefault(relative, order)
        elif name.startswith("rename"):
            written.setdefault(relative, order)
    inputs_read = {path for path, when in read.items()
                   if when < written.get(path, order + 1)
                   and os.path.isfile(os.path.join(root, path))}
    return inputs_read, set(written)


def compare(read, written, entries):
    """(read and not listed, listed and not read and not expected so,
    listed and not read as expected). A file the run wrote before any
    read of it, as unpacking an upstream file writes a part's sources, was
    the run's to make this time, and not read as an input."""
    listed = {entry.path: entry for entry in entries}
    unlisted = sorted(read - set(listed) - set(READ_NOT_INPUTS))
    unread = sorted(path for path, entry in listed.items()
                    if path not in read and path not in written and not entry.missing
                    and entry.role not in UNREAD_EXPECTED)
    expected = sorted(path for path, entry in listed.items()
                      if path not in read and entry.role in UNREAD_EXPECTED)
    return unlisted, unread, expected


def main():
    parser = argparse.ArgumentParser(
        description="Run a conversion under strace and check the inventory of inputs "
                    "against what it read.")
    parser.add_argument("-d", "--dir", default=".", help="the project's folder (default: here)")
    parser.add_argument("options", nargs="*", help="after --, options for convert.py")
    args = parser.parse_args()
    strace = shutil.which("strace")
    if not strace:
        sys.exit("check-inputs.py needs strace (Linux), which isn't installed.")
    root = os.path.abspath(args.dir)
    convert = os.path.join(os.path.dirname(HERE), "bin", "convert.py")
    with tempfile.TemporaryDirectory(prefix="check-inputs-") as work:
        trace = os.path.join(work, "trace.txt")
        done = subprocess.run(
            [strace, "-f", "-y", "-qq", "-s", "4096", "-e",
             "trace=open,openat,openat2,creat,execve,rename,renameat,renameat2",
             "-o", trace, sys.executable, convert] + args.options,
            cwd=root, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            print(f"The run ended with status {done.returncode}, so what it read isn't "
                  "every input's.", file=sys.stderr)
            return 2
        read, written = project_reads(trace, root)
    unlisted, unread, expected = compare(read, written, inputs.inventory(root))
    for path in unlisted:
        print(f"read, and not in the inventory: {path}")
    for path in unread:
        print(f"in the inventory, and not read: {path}")
    for path in expected:
        print(f"in the inventory, not read, as expected of its role: {path}")
    if unlisted or unread:
        print(f"The inventory and the run disagree: {len(unlisted)} read and not listed, "
              f"{len(unread)} listed and not read.")
        return 1
    print(f"The inventory and the run agree: {len(read)} file(s) read, each listed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
