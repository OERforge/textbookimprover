"""A part's own sources stripped of their metadata (convert.py
--strip-sources).

What lib/metastrip.py takes out of every output, taken out of the
author's files in src/<part>/ themselves, once, when asked: each file
stripped as a copy in the run's work folder, and only where the copy
differs is the original kept in originals/<part>/, by its path in the
part, and the copy put in its place. Windows' marks of a download
(name:Zone.Identifier, lib/zonemarks.py) are moved there too. Each change
is a row of originals/<part>/strip-record.csv.

A deck's sidecar rows key a picture by the start of its SHA-256
(media/<hash>, lib/pptxremediate.py), which a stripped picture changes:
each such key in the part's sidecars is changed to the new picture's, and
recorded.

The files are parsed in the sandbox, as a run's are: the run copies
them, as bytes, into its work folder (prepare), strips the copies there
in a program of their own inside the sandbox (python3 sourcestrip.py
--inside FOLDER, strip_copies), and then, outside, where the sources
can be written, reads back only regular files it named itself, no link
followed, and puts each changed copy in its source's place (apply). What
the sandboxed program says is checked as text before it's used.

No link is followed and no dot name read; a file that can't be read is
left as it is, and said.
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import zipfile

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import metastrip  # noqa: E402
import sidecars  # noqa: E402
import stamps  # noqa: E402
import zonemarks  # noqa: E402

RECORD = "strip-record.csv"
FIELDS = ("date", "file", "inside", "what", "sha256 before", "sha256 after")
KEY = re.compile(r"(?<![0-9a-f])media/([0-9a-f]{16})(?![0-9a-f])")
DIGEST = re.compile(r"[0-9a-f]{64}")
JOB, RESULT, COPIES = "job.json", "result.json", "files"


class Stop(Exception):
    """Why the sources can't be stripped, as a sentence."""


def sha256(path=None, data=None):
    digest = hashlib.sha256()
    if data is not None:
        digest.update(data)
    else:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def within(folder, path):
    folder, path = os.path.realpath(folder), os.path.realpath(path)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def files(sources):
    """[(path from sources, path)] of every file the strip reads, and
    [(path from sources, path)] of every mark of a download, no link and
    no dot name followed, sorted."""
    found, marks = [], []
    for root, dirs, names in os.walk(sources):
        dirs[:] = sorted(d for d in dirs if not stamps.skipped(d, True)
                         and not os.path.islink(os.path.join(root, d)))
        for name in sorted(names):
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            below = os.path.relpath(path, sources).replace(os.sep, "/")
            if name.endswith(zonemarks.SUFFIX) and not name.startswith("."):
                marks.append((below, path))
            elif not stamps.skipped(name) and metastrip.strippable(name):
                found.append((below, path))
    return found, marks


def picture_changes(before, after, name):
    """{old SHA-256: new} of each picture a strip changed: the file's
    own, or each of a zip's pictures."""
    if name.lower().endswith(metastrip.PICTURE_EXTENSIONS):
        return {sha256(data=before): sha256(data=after)}
    changes = {}
    if not name.lower().endswith(metastrip.ZIP_EXTENSIONS):
        return changes
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(before)) as old, \
                zipfile.ZipFile(io.BytesIO(after)) as new:
            names = set(new.namelist())
            for info in old.infolist():
                if info.filename in names \
                        and info.filename.lower().endswith(metastrip.PICTURE_EXTENSIONS):
                    a, b = old.read(info), new.read(info.filename)
                    if a != b:
                        changes[sha256(data=a)] = sha256(data=b)
    except (zipfile.BadZipFile, OSError, ValueError, EOFError, NotImplementedError):
        pass
    return changes


def keep(path, below, originals):
    """A file kept in originals before it changes or moves, under its path
    in the part, a later one beside an earlier one; the copy there
    already when it's the same."""
    kept = os.path.join(originals, *below.split("/"))
    # The nearest folder there is, links followed, inside the originals:
    # a link among them would have the copy written elsewhere.
    there = os.path.dirname(kept)
    while not os.path.lexists(there) and there != os.path.dirname(there):
        there = os.path.dirname(there)
    if not within(originals, there) and not within(there, originals):
        raise Stop(f"{os.path.dirname(kept)} leads out of the part's originals")
    if within(originals, there) and os.path.realpath(there) != os.path.realpath(originals) \
            and not os.path.isdir(there):
        raise Stop(f"{there} isn't a folder")
    number = 1
    while os.path.lexists(kept):
        if os.path.isfile(kept) and not os.path.islink(kept) and sha256(kept) == sha256(path):
            return kept
        number += 1
        kept = os.path.join(originals, *below.split("/")) + f".{number}"
    os.makedirs(os.path.dirname(kept), exist_ok=True)
    if not within(originals, os.path.dirname(kept)):
        raise Stop(f"{os.path.dirname(kept)} leads out of the part's originals")
    shutil.copy2(path, kept)
    return kept


def put(path, data):
    """A source's new bytes in its place, all at once, its mode kept."""
    import projectpaths
    # A name no file has: a link planted under a fixed one would be
    # written through.
    handle, tmp = projectpaths.Project().temp_file(
        prefix="." + os.path.basename(path)[:40] + ".", suffix=".strip", beside=path)
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(data)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.remove(tmp)


def rekey(sidecar_folder, changes):
    """Each media/<hash> key in the part's sidecars whose picture the
    strip changed given the new picture's; [(sidecar, old key, new key)],
    and [sidecar] of those that couldn't be read as UTF-8 and were left."""
    short = {old[:16]: new[:16] for old, new in changes.items() if old[:16] != new[:16]}
    done, left = [], []
    if not short or not os.path.isdir(sidecar_folder) or os.path.islink(sidecar_folder):
        return done, left
    for name in sorted(os.listdir(sidecar_folder)):
        path = os.path.join(sidecar_folder, name)
        if not name.lower().endswith(".csv") or name.startswith(".") \
                or os.path.islink(path) or not os.path.isfile(path):
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        bom = data.startswith(b"\xef\xbb\xbf")
        try:
            text = data[3 if bom else 0:].decode("utf-8")
        except UnicodeDecodeError:
            if KEY.search(data.decode("latin-1")):
                left.append(name)
            continue
        found = []

        def swap(m):
            if m.group(1) in short:
                found.append((m.group(0), "media/" + short[m.group(1)]))
                return "media/" + short[m.group(1)]
            return m.group(0)
        new = KEY.sub(swap, text)
        if new != text:
            put(path, (b"\xef\xbb\xbf" if bom else b"") + new.encode("utf-8"))
            for old, now in found:
                if (name, old, now) not in done:
                    done.append((name, old, now))
    return done, left


def read_regular(path, folder):
    """A file's bytes, read only when it's a regular file in folder itself,
    no link followed to it or to folder; None otherwise."""
    if os.path.islink(folder) or not os.path.isdir(folder) \
            or os.path.realpath(os.path.dirname(path)) != os.path.realpath(folder):
        return None
    try:
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        import stat
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            return None
        with os.fdopen(os.dup(handle), "rb") as fh:
            return fh.read()
    finally:
        os.close(handle)


def prepare(sources, work, level, keep_list):
    """The part's files to strip copied, as bytes, into work's files/,
    with the job the sandboxed program reads; [(path from sources, path,
    the copy's name)] and the marks of a download (files)."""
    found, marks = files(sources)
    if os.path.islink(work):
        raise Stop(f"{work} is a link")
    shutil.rmtree(work, ignore_errors=True)
    copies = os.path.join(work, COPIES)
    os.makedirs(copies)
    listed = []
    for number, (below, path) in enumerate(found):
        name = f"{number}{os.path.splitext(path)[1].lower()}"
        shutil.copyfile(path, os.path.join(copies, name), follow_symlinks=False)
        listed.append((below, path, name))
    with open(os.path.join(work, JOB), "w", encoding="utf-8") as fh:
        json.dump({"level": level, "keep": list(keep_list),
                   "files": [name for _b, _p, name in listed]}, fh)
    return listed, marks


def strip_copies(work):
    """The sandboxed part: each copy the job names stripped in place, and
    what went and which pictures changed written to the result."""
    with open(os.path.join(work, JOB), encoding="utf-8") as fh:
        job = json.load(fh)
    result = {}
    for name in job["files"]:
        path = os.path.join(work, COPIES, os.path.basename(name))
        with open(path, "rb") as fh:
            before = fh.read()
        said = metastrip.strip_file(path, job["level"], job["keep"])
        with open(path, "rb") as fh:
            after = fh.read()
        result[name] = {"said": [[member, list(removed)] for member, removed in said],
                        "changes": picture_changes(before, after, name) if after != before
                        else {}}
    with open(os.path.join(work, RESULT), "w", encoding="utf-8") as fh:
        json.dump(result, fh)


def _text(value, limit=500):
    return "".join(ch for ch in str(value) if ch.isprintable())[:limit]


def _said(entry):
    """What the sandboxed program says of a copy, as text: [(member, [what
    went])], and {old: new} of its pictures' SHA-256."""
    said, changes = [], {}
    if not isinstance(entry, dict):
        return said, changes
    for item in entry.get("said") or []:
        if isinstance(item, list) and len(item) == 2 and isinstance(item[1], list):
            said.append((_text(item[0]), [_text(w) for w in item[1][:50]]))
    found = entry.get("changes")
    if isinstance(found, dict):
        changes = {k: v for k, v in found.items() if isinstance(k, str) and isinstance(v, str)
                   and DIGEST.fullmatch(k) and DIGEST.fullmatch(v)}
    return said, changes


def apply(listed, marks, work, originals, sidecar_folder):
    """Outside the sandbox: each copy the strip changed put in its
    source's place, the original kept in originals first; each mark of a
    download moved there; the sidecars' keys of a changed picture given
    the new one's; each change a row of the record. A dict of what was
    done: "files" [(path, what went)], "left" [(path, why)], "marks"
    [path], "keys" [(sidecar, old, new)], "unkeyed" [sidecar]."""
    if os.path.lexists(originals) and (os.path.islink(originals)
                                       or not os.path.isdir(originals)):
        raise Stop(f"{originals} isn't a folder of the project's own")
    copies = os.path.join(work, COPIES)
    raw = read_regular(os.path.join(work, RESULT), work)
    try:
        result = json.loads(raw.decode("utf-8")) if raw is not None else None
    except (UnicodeDecodeError, ValueError):
        result = None
    if not isinstance(result, dict):
        raise Stop("the strip, in the sandbox, left no result to read")
    rows, done, left, moved, changes = [], [], [], [], {}
    today = datetime.date.today().isoformat()
    for below, path, name in listed:
        said, changed = _said(result.get(name))
        after = read_regular(os.path.join(copies, name), copies)
        with open(path, "rb") as fh:
            before = fh.read()
        not_read = [w for _m, removed in said for w in removed if "left as it is" in w]
        if after is None:
            left.append((below, "not stripped: its copy couldn't be read back"))
            continue
        if after == before:
            if not_read:
                left.append((below, not_read[0]))
            continue
        keep(path, below, originals)
        put(path, after)
        changes.update(changed)
        what = []
        for member, removed in said or [("", ["changed"])]:
            what.append((member, "; ".join(removed)))
            rows.append({"date": today, "file": below, "inside": member,
                         "what": "; ".join(removed), "sha256 before": sha256(data=before),
                         "sha256 after": sha256(data=after)})
        done.append((below, what))
    for below, path in marks:
        mark = zonemarks.read_mark(path) or {"zone": None, "address": "", "referrer": ""}
        digest = sha256(path)
        keep(path, below, originals)
        os.remove(path)
        moved.append(below)
        what = "Windows' mark of a download, moved here: " + zonemarks.zone_name(mark["zone"]) \
            + (f", from {mark['address']}" if mark["address"] else "")
        rows.append({"date": today, "file": below, "inside": "", "what": what,
                     "sha256 before": digest, "sha256 after": ""})
    keys, unkeyed = rekey(sidecar_folder, changes)
    for name, old, new in keys:
        rows.append({"date": today, "file": "sidecars/" + name, "inside": "",
                     "what": f"key {old} now {new}, its picture stripped",
                     "sha256 before": "", "sha256 after": ""})
    if rows:
        os.makedirs(originals, exist_ok=True)
        record = os.path.join(originals, RECORD)
        if os.path.islink(record):
            raise Stop(f"{record} is a link")
        new = not os.path.exists(record)
        with open(record, "a", encoding="utf-8", newline="") as fh:
            # Guarded against a spreadsheet's formulas, as every CSV a
            # run writes for a person is: a file's name is the book's.
            writer = sidecars.csv_writer(fh)
            if new:
                writer.writerow(FIELDS)
            writer.writerows([row[field] for field in FIELDS] for row in rows)
    shutil.rmtree(work, ignore_errors=True)
    return {"files": done, "left": left, "marks": moved, "keys": keys, "unkeyed": unkeyed}


def strip_sources(sources, originals, sidecar_folder, work, level, keep_list, run=None):
    """The part's sources stripped at the level, each original kept in
    originals and each mark of a download moved there (apply's dict). run
    runs the sandboxed program, a command list, and gives its exit code;
    without it the copies are stripped here."""
    listed, marks = prepare(sources, work, level, keep_list)
    if run is None:
        strip_copies(work)
    else:
        code = run([sys.executable, os.path.abspath(__file__), "--inside",
                    os.path.realpath(work)])
        if code != 0:
            raise Stop(f"the strip, in the sandbox, stopped (exit status {code})")
    return apply(listed, marks, work, originals, sidecar_folder)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--inside":
        strip_copies(sys.argv[2])
    else:
        sys.exit("sourcestrip.py --inside FOLDER: convert.py --strip-sources runs it.")
