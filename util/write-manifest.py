#!/usr/bin/env python3
"""
write-manifest.py -- write a project's manifest, ti-archive.yaml at its
top, recording its inputs as the release its identifier and version
name, for convert.py's identity check to compare later runs with
(lib/projectarchive.py). Packing a project will write it; until there's
packing, this does.

    python3 util/write-manifest.py -d PROJECT
    python3 util/write-manifest.py -d PROJECT --force

It writes nothing where a manifest records other inputs under the same
identifier and version, which is the release the check guards, unless
--force; and nothing for the default identifier, book, which names no
book of its own. It reads the project's files and writes the one file.

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
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import oerconfig  # noqa: E402
import projectarchive  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Write a project's manifest, ti-archive.yaml, recording its inputs "
                    "under its identifier and version.")
    parser.add_argument("-d", "--dir", default=".", help="the project's folder (.)")
    parser.add_argument("--force", action="store_true",
                        help="write it where one records other inputs under the same "
                             "identifier and version")
    args = parser.parse_args()
    root = args.dir
    try:
        now = projectarchive.manifest(root)
    except oerconfig.ConfigError as exc:
        sys.exit(f"{exc}\nNo manifest was written.")
    project = now["project"]
    if project["identifier"] == projectarchive.DEFAULT_IDENTIFIER:
        sys.exit(f"The identifier is the default, {projectarchive.DEFAULT_IDENTIFIER}, which "
                 "names no book of its own. Give the book one no other book uses, as "
                 "project.identifier in project.yaml. No manifest was written.")
    try:
        kept = projectarchive.read(root)
    except projectarchive.Problem as exc:
        kept = None
        if not args.force:
            sys.exit(f"{projectarchive.NAME} can't be read as a manifest: {exc}. --force "
                     "writes a new one over it. No manifest was written.")
    if kept is not None and not args.force:
        said = projectarchive.check(kept, now)
        if said.state == "changed":
            sys.exit(f"{projectarchive.NAME} records other inputs under "
                     f"{project['identifier']} version {project['version'] or '(none)'}: "
                     "raise project.version for a new release, or --force to record "
                     "these in its place. No manifest was written.")
    path = projectarchive.write(root, now)
    print(f"Wrote {path}: {len(now['files'])} file(s), {project['identifier']} version "
          f"{project['version'] or '(none)'}, inputs {now['digests']['inputs']}.")
    if not project["version"]:
        print("NOTE: the book has no version (project.version), so a later release can't "
              "be told from this one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
