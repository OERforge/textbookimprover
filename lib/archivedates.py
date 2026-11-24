"""
archivedates.py -- the dates, modes, and owners of what goes into the zip
and tar files TextbookImprover writes itself, so that a build made again
under SOURCE_DATE_EPOCH writes the same bytes.

A zip records each member's date, from the file's modification time when
it's added from disk (ZipFile.write) or the moment it's added from bytes
(writestr with a name), and the file's mode; a tar records the date, the
mode, and the owner's number and name, and its gzip wrapper a date and the
file's name of its own. Each of those differs between two builds of the
same book: the files were written at another moment, by another person,
under another umask, into a temporary file of another name.

So, for a zip member: the moment SOURCE_DATE_EPOCH names, in UTC, where
it's set (zip_time), and otherwise the file's modification time or now,
as zipfile gives it; and a mode of 0644, or 0755 for a file anyone may
run. For a tar member: the same date, the same modes, and no owner (0,
with no name). And the gzip wrapper holds no date and no name. Members
copied from another zip keep their own ZipInfo, which is what the program
that wrote that zip gave them, and aren't this module's.

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

import gzip
import os
import shutil
import stat
import tarfile
import time
import zipfile

# A zip's dates run from 1980 through 2107 (its DOS date's seven bits of
# year), so a moment outside that is given as the nearer end.
ZIP_FIRST = (1980, 1, 1, 0, 0, 0)
ZIP_LAST = (2107, 12, 31, 23, 59, 58)


def epoch(environ=None):
    """The moment SOURCE_DATE_EPOCH names, in seconds, or None where it
    isn't set to a whole number of seconds, as build-cartridge.py's
    build_day reads it."""
    value = (os.environ if environ is None else environ).get("SOURCE_DATE_EPOCH", "")
    return int(value) if value.strip().isdigit() else None


def zip_time(seconds):
    """A moment as a zip member's date: its year to second in UTC, within
    what a zip can hold, and an even second, which is all a zip keeps."""
    found = time.gmtime(seconds)[:6]
    found = max(ZIP_FIRST, min(ZIP_LAST, tuple(found)))
    return found[:5] + (found[5] - found[5] % 2,)


def _mode(path):
    """0755 for a file anyone may run, else 0644, as a zip's or tar's
    member's mode, whatever the umask it was written under."""
    try:
        runnable = path is not None and bool(os.stat(path).st_mode & stat.S_IXOTH)
    except OSError:
        runnable = False
    return 0o755 if runnable else 0o644


def zip_info(name, path=None, environ=None, compress=zipfile.ZIP_DEFLATED):
    """The ZipInfo for a member called name, from the file at path or from
    bytes when path is None: SOURCE_DATE_EPOCH's date where it's set, else
    the file's modification time, or now, as zipfile would give."""
    seconds = epoch(environ)
    if seconds is not None:
        info = zipfile.ZipInfo(name, zip_time(seconds))
    elif path is not None:
        info = zipfile.ZipInfo.from_file(path, name)
    else:
        info = zipfile.ZipInfo(name, time.localtime(time.time())[:6])
    info.compress_type = compress
    info.create_system = 3    # Unix's, so the mode is read as one
    info.external_attr = (stat.S_IFREG | _mode(path)) << 16
    return info


def write_file(archive, path, name, environ=None, compress=zipfile.ZIP_DEFLATED):
    """Add the file at path to the open zip archive as name (zip_info)."""
    info = zip_info(name, path, environ, compress)
    with open(path, "rb") as source, archive.open(info, "w") as member:
        shutil.copyfileobj(source, member, 1 << 20)


def write_bytes(archive, name, data, environ=None, compress=zipfile.ZIP_DEFLATED):
    """Add data to the open zip archive as name (zip_info)."""
    archive.writestr(zip_info(name, None, environ, compress), data)


def write_tar_gz(target, members, environ=None):
    """Write target, a gzipped tar of members, (path, name) pairs in the
    order given: each a file's contents, a link's as its file's, with SOURCE_DATE_EPOCH's date where
    it's set (else its own, to the second), a mode of 0644 or 0755, and
    no owner; the gzip wrapper with no date and no file's name."""
    seconds = epoch(environ)
    with open(target, "wb") as raw, \
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as packed, \
            tarfile.open(fileobj=packed, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for path, name in members:
            # By the open file, so a link is packed as what it leads to,
            # as a zip packs it.
            with open(path, "rb") as fh:
                info = archive.gettarinfo(arcname=name, fileobj=fh)
                info.mtime = seconds if seconds is not None else int(info.mtime)
                info.mode = _mode(path)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, fh)
