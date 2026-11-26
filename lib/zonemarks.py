"""Windows' marks of a download, read (the report of a part's downloads).

When a file downloaded on Windows is copied into WSL, Windows leaves its
Mark of the Web beside it as a file of its own, named after it with
":Zone.Identifier" added: a few lines of INI that say which security zone
the file came from and, for a file from the internet, the address it was
downloaded from and the page that linked to it. No run reads these as a
book's files (lib/stamps.py, lib/unpacking.py); this module lists them, so
a person can see which of a book's files came from the internet and from
where.

The marks are read as untrusted: no more than MARK_LIMIT bytes, in UTF-8
or UTF-16 with its byte-order mark, and an address is cut to its scheme,
host, port, and path, since a query or a user name in it can carry a
token or a name a report mustn't keep.
"""

import os
import stat

SUFFIX = ":Zone.Identifier"
MARK_LIMIT = 64 * 1024
ZONES = {0: "this computer", 1: "the local intranet", 2: "trusted sites",
         3: "the internet", 4: "restricted sites"}


def address(value):
    """An address cut to its scheme, host, port, and path; a value that
    isn't one (about:internet) as it is, without control characters."""
    from urllib.parse import urlsplit, urlunsplit
    text = "".join(ch for ch in str(value or "") if ch.isprintable()).strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if not parts.scheme or not parts.netloc:
        return text[:200] if text.startswith("about:") else ""
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host + (f":{port}" if port else "")
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))[:500]


def read_mark(path):
    """{"zone": int or None, "address": str, "referrer": str} from a mark,
    or None for one that can't be read as one."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        handle = os.open(path, flags)
    except OSError:
        return None
    try:
        # What's opened is checked, not the name: a link or a pipe put in
        # the mark's place since it was listed is never read.
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            return None
        data = b""
        while len(data) <= MARK_LIMIT:
            piece = os.read(handle, MARK_LIMIT + 1 - len(data))
            if not piece:
                break
            data += piece
    except OSError:
        return None
    finally:
        os.close(handle)
    if len(data) > MARK_LIMIT:
        return None
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", "replace")
    else:
        text = data.decode("utf-8-sig", "replace")
    found, section = {}, ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section != "zonetransfer" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found.setdefault(key.strip().lower(), value.strip())
    if not found:
        return None
    try:
        zone = int(found.get("zoneid", ""))
    except ValueError:
        zone = None
    return {"zone": zone, "address": address(found.get("hosturl")),
            "referrer": address(found.get("referrerurl"))}


def marks(folder, top):
    """[(the marked file's path from top, its mark's reading)] for every
    mark under folder, no link and no dot folder followed, sorted; a mark
    whose file is gone is listed too, and one that can't be read with no
    zone."""
    rows = []
    if not os.path.isdir(folder) or os.path.islink(folder):
        return rows
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".")
                         and not os.path.islink(os.path.join(root, d)))
        for name in sorted(files):
            if not name.endswith(SUFFIX) or len(name) == len(SUFFIX):
                continue
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            marked = os.path.relpath(os.path.join(root, name[:-len(SUFFIX)]), top)
            rows.append((marked.replace(os.sep, "/"),
                         read_mark(path) or {"zone": None, "address": "", "referrer": ""}))
    return sorted(rows, key=lambda row: row[0])


def zone_name(zone):
    """A zone's name, as Windows' own settings name it."""
    if zone is None:
        return "not read"
    return ZONES.get(zone, f"zone {zone}")
