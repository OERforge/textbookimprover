"""
texrecord.py -- what LaTeX built a PDF with, for the build record
(lib/buildrecord.py): the LaTeX release, the TeX Live packages that hold
the files LaTeX read, with their revisions, the fonts the PDF embeds and
where each came from, and every other file LaTeX read outside TeX's tree
and the project, by its full path and SHA-256 (a system font, fontconfig's
settings, a file under --allow-read).

The build that ran LaTeX, inside the sandbox, writes what only it can see
(write): the files LaTeX's -recorder list names, the fonts the PDF's font
descriptors name, each found with luaotfload-tool as LuaLaTeX finds it,
and the hashes of the files outside TeX's tree. It writes each into
output/work/record/tex/pending/, a file per build, and the part's run
moves a target's into output/work/record/tex/ once the target's folder
is in place (promote), so what's kept there describes the PDF output/
holds, built this run or an earlier one, and a build that failed after
LaTeX ran leaves the last one's. The run that holds the lock reads them
(read) as a sandboxed run's data, those of the targets this run's parts
named, and puts the files in TeX's tree into packages by TeX Live's own
database (texlive.tlpdb), which a TeX Live from tug.org and TinyTeX have
and Debian's and Ubuntu's packages don't; there the record lists the
files instead.

Measured on a one-page Markdown book's PDF, 2026-11-24 (TinyTeX, LaTeX
2026-11-01): 57 packages, four IBM Plex faces in TeX Live's plex package,
and 58 other files, fontconfig's settings among them; TeX Live's database
(1.9 MB) read in under 0.02 s, and luaotfload's lookup 0.25 s a face.

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

import json
import os
import re
import shutil
import subprocess

import projectpaths

FOLDER = ("output", "work", "record", "tex")
PENDING = "pending"
# What a build writes at most: files outside TeX's tree it hashes, fonts it
# looks for, and the files in TeX's tree it lists.
MOST_OTHERS = 500
MOST_FONTS = 60
MOST_FILES = 5000
# A file outside TeX's tree larger than this is named, not hashed.
LARGEST = 64 << 20
KERNEL = re.compile(r"LaTeX2e <(\d{4}-\d{2}-\d{2})>(?:\s*patch level (\d+))?")
SUBSET = re.compile(r"^[A-Z]{6}\+")

_ROOT = []


def tex_root():
    """TeX's own folder (kpsewhich's SELFAUTOPARENT), as a real path, or
    None."""
    if not _ROOT:
        found = None
        kpsewhich = shutil.which("kpsewhich")
        if kpsewhich:
            try:
                done = subprocess.run([kpsewhich, "-var-value=SELFAUTOPARENT"],
                                      capture_output=True, text=True, timeout=60,
                                      stdin=subprocess.DEVNULL)
                if done.returncode == 0 and os.path.isabs(done.stdout.strip()):
                    found = os.path.realpath(done.stdout.strip())
            except (OSError, subprocess.SubprocessError):
                pass
        _ROOT.append(found)
    return _ROOT[0]


def _under(path, folder):
    return bool(folder) and (path == folder or path.startswith(folder.rstrip(os.sep) + os.sep))


def _sha256(path):
    import hashlib
    try:
        if os.path.getsize(path) > LARGEST:
            return "larger than 64 MiB"
        found = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                found.update(block)
        return found.hexdigest()
    except OSError:
        return "can't be read"


def pdf_fonts(pdf):
    """The names of the fonts the PDF's font descriptors give, a subset's
    prefix taken off, or None where pikepdf isn't there."""
    try:
        import pikepdf
    except ImportError:
        return None
    names = set()
    try:
        with pikepdf.open(pdf) as doc:
            for obj in doc.objects:
                if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == "/FontDescriptor":
                    name = obj.get("/FontName")
                    if name is not None:
                        names.add(SUBSET.sub("", str(name).lstrip("/")))
                if len(names) >= MOST_FONTS:
                    break
    except Exception:  # noqa: BLE001 -- a PDF pikepdf can't read gives no fonts
        return []
    return sorted(names)


def find_font(name):
    """The file luaotfload finds for name, as LuaLaTeX would, or None."""
    tool = shutil.which("luaotfload-tool")
    if not tool:
        return None
    try:
        done = subprocess.run([tool, f"--find={name}"], capture_output=True, text=True,
                              timeout=60, stdin=subprocess.DEVNULL, errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'Resolved file name "([^"]+)"', done.stdout + done.stderr)
    return os.path.realpath(m.group(1)) if m else None


def _place(path, root):
    """A file as the record names it: {"tex": path in TeX's tree} or
    {"file": path, "sha256": digest}."""
    if root and _under(path, root):
        return {"tex": os.path.relpath(path, root).replace(os.sep, "/")}
    return {"file": path, "sha256": _sha256(path)}


def gather(base, fls, pdf, log, engine):
    """What a build that ran LaTeX read and embedded: the release, the
    files in TeX's tree, the other files with their hashes, and the
    fonts. The project's own files are left out, as its stamp has them."""
    import texreads
    root = tex_root()
    top = os.path.realpath(projectpaths.of(base).top())
    tex, others = [], {}
    for path in texreads.recorded(fls):
        real = os.path.realpath(path)
        if real == os.devnull or _under(real, top):
            continue
        if root and _under(real, root):
            if len(tex) < MOST_FILES:
                tex.append(os.path.relpath(real, root).replace(os.sep, "/"))
        elif len(others) < MOST_OTHERS and os.path.isfile(real):
            others[real] = _sha256(real)
    kernel = KERNEL.search(log or "")
    fonts = {}
    named = pdf_fonts(pdf) if os.path.basename(engine).startswith("lua") else []
    for name in named or []:
        found = find_font(name)
        fonts[name] = _place(found, root) if found else {"found": "no"}
    return {
        "engine": os.path.basename(engine),
        "latex": (kernel.group(1) + (f", patch level {kernel.group(2)}" if kernel.group(2)
                                    else "")) if kernel else "not said",
        "tex files": sorted(set(tex)),
        "other files": others,
        "fonts": fonts if named is not None else "pikepdf isn't installed",
    }


def _file_name(key):
    return re.sub(r"[^A-Za-z0-9._-]", "_", key)[:120] + ".json"


def write(base, key, fls, pdf, log, engine):
    """gather's values for the build key names (a target, or a target and
    its master, "pdf (main.tex)"), into output/work/record/tex/pending/,
    until promote. A failure to write is said by the caller."""
    import buildrecord
    values = dict(gather(base, fls, pdf, log, engine), build=key)
    folder = projectpaths.of(base).top(*FOLDER, PENDING)
    os.makedirs(folder, exist_ok=True)
    buildrecord._write_new(os.path.join(folder, _file_name(key)),
                           json.dumps(values, indent=1, sort_keys=True))


def target_of(key):
    """The target a build's key names: "pdf" of "pdf (main.tex)"."""
    return key.split(" (", 1)[0]


def _pieces(folder):
    """[(file name, build key)] of the pieces in folder, none a link."""
    import buildrecord
    found = []
    if os.path.isdir(folder) and not os.path.islink(folder):
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not name.endswith(".json") or os.path.islink(path):
                continue
            try:
                values = json.loads(buildrecord._read_small(path) or "null")
            except ValueError:
                continue
            if isinstance(values, dict) and isinstance(values.get("build"), str):
                found.append((name, values["build"]))
    return found


def promote(base, target):
    """A target's pending pieces made its kept ones, its earlier ones
    taken away, once its folder is in place: done by the part's run
    (convert.py's record_stamps)."""
    kept = projectpaths.of(base).top(*FOLDER)
    pending = os.path.join(kept, PENDING)
    new = [(n, k) for n, k in _pieces(pending) if target_of(k) == target]
    if not new:
        return
    for name, key in _pieces(kept):
        if target_of(key) == target:
            os.remove(os.path.join(kept, name))
    for name, _key in new:
        os.replace(os.path.join(pending, name), os.path.join(kept, name))


def clear(base):
    """What an earlier run left pending, taken away by the run that holds
    the lock as it starts."""
    folder = projectpaths.of(base).top(*FOLDER, PENDING)
    if os.path.isdir(folder) and not os.path.islink(folder):
        for name in os.listdir(folder):
            if name.endswith(".json"):
                os.remove(os.path.join(folder, name))


# -- the run that holds the lock --------------------------------------------

_PACKAGES = []


def package_database(root):
    """{file in TeX's tree: (package, revision)} from TeX Live's
    texlive.tlpdb, or None where there's none."""
    if _PACKAGES:
        return _PACKAGES[0]
    found = None
    database = os.path.join(root, "tlpkg", "texlive.tlpdb") if root else None
    if database and os.path.isfile(database):
        found, name, revision, files = {}, None, "", []

        def done():
            for path in files:
                found[path] = (name, revision)

        with open(database, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("name "):
                    done()
                    name, revision, files = line[5:].strip(), "", []
                elif line.startswith("revision "):
                    revision = line[9:].strip()
                elif line.startswith(" ") and name:
                    path = line.strip().split(" ")[0]
                    if path.startswith("RELOC/"):
                        path = "texmf-dist/" + path[6:]
                    files.append(path)
        done()
    _PACKAGES.append(found)
    return found


def _strings(values):
    return isinstance(values, list) and all(isinstance(v, str) for v in values)


def summary(values, root):
    """What the record says of one build, from what it wrote: its packages
    and their revisions where TeX Live's database is there, else its
    files in TeX's tree, and what's in TeX's tree but no package
    (generated files, a cache)."""
    database = package_database(root)
    tex = values.get("tex files") if _strings(values.get("tex files")) else []
    out = {"engine": values.get("engine", ""), "latex": values.get("latex", "")}
    if database is None:
        out["package database"] = "none (TeX Live's texlive.tlpdb isn't there)"
        out["tex files"] = tex
    else:
        packages, loose = {}, []
        for path in tex:
            held = database.get(path)
            if held:
                packages[held[0]] = held[1]
            else:
                loose.append(path)
        out["packages"] = {k: packages[k] for k in sorted(packages)}
        out["in TeX's tree, in no package"] = loose
    fonts = values.get("fonts")
    if isinstance(fonts, dict):
        shown = {}
        for name, place in sorted(fonts.items()):
            if isinstance(place, dict) and isinstance(place.get("tex"), str):
                held = database.get(place["tex"]) if database else None
                shown[name] = ({"package": held[0], "revision": held[1], "file": place["tex"]}
                               if held else {"file in TeX's tree": place["tex"]})
            else:
                shown[name] = place
        out["fonts"] = shown
    else:
        out["fonts"] = fonts
    others = values.get("other files")
    out["other files read"] = others if isinstance(others, dict) else {}
    return out


def read(base, targets=None):
    """{build: summary} for each kept build of a target in targets (all,
    where it's None), read as data a sandboxed run wrote
    (buildrecord._read_small)."""
    import buildrecord
    folder = projectpaths.of(base).top(*FOLDER)
    found = {}
    root = tex_root()
    for name, key in _pieces(folder):
        if targets is not None and target_of(key) not in targets:
            continue
        try:
            values = json.loads(buildrecord._read_small(os.path.join(folder, name)) or "null")
        except ValueError:
            continue
        if isinstance(values, dict):
            found[key] = summary(values, root)
    return found
