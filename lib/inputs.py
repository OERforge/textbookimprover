"""
inputs -- the inventory of a project's inputs: every file outside output/
that a run may read, each with its role and its part.

    import inputs
    for entry in inputs.inventory(root):
        print(entry.path, entry.role, entry.part)

A run reads every file in a part's folder, whatever the book uses: the
stamps hash each one, and the check for active content and the report of
files downloaded on Windows read the part's files too. So the inventory
lists what the stamps count, file by file (stamps.tree_entries and
stamps.top_entries), rather than the files the pages name, and the stamps
take the files a target's settings name from named_files below, so that
the two can't come to differ.

ROLES

  settings  project.yaml, conversion.yaml, and packaging.yaml
  source    a file in src/<part>/ of a part that's built
  files     a file in src/<part>/ of a part of kind files, which travels
            with the project and is never built
  sidecar   a file in sidecars/<part>/
  named     a file a target's settings name: a template, a stylesheet, a
            reference document, a header or footer kept in a file,
            latex.macros
  upstream  a file in upstream/: a part's upstream file, which a run
            unpacks into src/<part>/ when that folder is empty, and a
            deck's original that util/swap-in-pptx.py replaced

A file whose name the stamps pass over (a dot name, a backup, an
autosave, a Windows thumbnail or download mark) is in no role: a run
doesn't read it. A file a setting names that isn't there is listed with
the role named and missing true, since making it changes a build.

util/check-inputs.py runs a conversion under strace and names each file
in the project, outside output/, that the run read and the inventory
doesn't list.

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

import collections
import os

import oerconfig
import pagefooter
import projectpaths
import stamps

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = ("settings", "source", "files", "sidecar", "named", "upstream")

Entry = collections.namedtuple("Entry", "path role part missing")


def named_files(root, resolved, fmt, part, schema, latex_book=False):
    """Each file a target's settings name and its build reads, as a full
    path: its path settings (a stylesheet, a template, a reference
    document) in the sections it reads, a header or footer that names a
    file, and latex.macros for a target whose build runs LaTeX. One the
    settings may not name isn't read, here or by the build, which stops
    at it; its value is in the settings digest."""
    project = projectpaths.of(root)
    values = stamps.named_settings(schema, resolved.settings, fmt)
    for key in ("header", "footer"):
        named = pagefooter.named_file(resolved[key], root)
        if named:
            values.append(named)
    if fmt in ("pdf", "latex") or latex_book:
        macros = str(resolved["latex.macros"] or "").strip()
        if macros:
            values.append(macros)
    found = []
    for value in values:
        if os.path.isabs(value):
            if project.inside(value):
                found.append(value)
            continue
        try:
            found.append(project.named(value, part))
        except projectpaths.Refused:
            continue
    return found


def schemas():
    """The conversion schema and the project schema."""
    return (oerconfig.load_schema(os.path.join(os.path.dirname(HERE), "bin",
                                               "schema-conversion.yaml")),
            oerconfig.load_schema(os.path.join(HERE, "schema-project.yaml")))


def _documents(root, schema, project_schema):
    project = projectpaths.of(root)
    documents = []
    for path, which in ((project.project_file(), project_schema),
                        (project.config_file(), schema)):
        if os.path.isfile(path):
            documents.append(oerconfig.load_document(path, which))
    return documents


def parts(root):
    """The project's parts and each one's kind (book, slides, files, or
    None where nothing says), as project.yaml names them, or the folders
    src/ holds where it names none."""
    project = projectpaths.of(root)
    path = project.project_file()
    block = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            data = oerconfig.safe_load(fh) or {}
        block = data.get("project") if isinstance(data, dict) else None
    declared = block.get("parts") if isinstance(block, dict) else None
    if isinstance(declared, dict) and declared:
        return {str(name): (str(value.get("kind") or "book") if isinstance(value, dict)
                            else "book") for name, value in declared.items()}
    src = project.top("src")
    found = sorted(entry.name for entry in os.scandir(src)
                   if entry.is_dir() and not entry.name.startswith(".")) \
        if os.path.isdir(src) else []
    return {name: None for name in found}


def targets(root, schema=None, project_schema=None):
    """Each target conversion.yaml declares, as (name, Resolved, part),
    or the one html target a project that declares none has. Raises
    oerconfig.ConfigError where the settings can't be read, as a run
    stops on them."""
    if schema is None:
        schema, project_schema = schemas()
    documents = _documents(root, schema, project_schema)
    built = {name: kind for name, kind in parts(root).items() if kind != "files"}
    default = projectpaths.BOOK if projectpaths.BOOK in built or len(built) != 1 \
        else next(iter(built))
    found = []
    for name in oerconfig.target_names(documents) or [None]:
        resolved = oerconfig.resolve(schema, project_schema, documents, target=name,
                                     allow_unknown=True)
        part = str(resolved["part"] or "").strip() or default
        found.append((name or "html", resolved, part))
    return found


def _relative(path, root):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")


def inventory(root, latex_books=()):
    """Every input of the project at root, as Entry(path, role, part,
    missing), each path from the project's folder with / between its
    names, sorted by path. latex_books names the parts whose every target
    is a LaTeX book's, whose builds read latex.macros (convert.py knows
    which; a caller that doesn't passes none, and a LaTeX book's macros
    file is listed where a pdf or latex target names it)."""
    root = os.path.abspath(root)
    project = projectpaths.of(root)
    schema, project_schema = schemas()
    entries = {}

    def add(path, role, part=None, missing=False):
        entries.setdefault(path, Entry(path, role, part, missing))

    for path in (project.project_file(), project.config_file(), project.packaging_file()):
        if os.path.isfile(path):
            add(_relative(path, root), "settings")
    kinds = parts(root)
    for part, kind in kinds.items():
        role = "files" if kind == "files" else "source"
        for path, _ in stamps.tree_entries(project.top("src", part), root=root):
            add(f"src/{part}/{path}", role, part)
        if kind != "files":
            for path, _ in stamps.top_entries(root, part):
                add(path, "sidecar", part)
    for _name, resolved, part in targets(root, schema, project_schema):
        for full in named_files(root, resolved, resolved["format"], part, schema,
                                latex_book=part in latex_books):
            path = _relative(full, root)
            add(path, "named", part, missing=not os.path.isfile(full))
    for path, _ in stamps.tree_entries(project.top("upstream"), root=root):
        first = path.split("/", 1)[0]
        add(f"upstream/{path}", "upstream",
            first if "/" in path and first in kinds else None)
    return [entries[path] for path in sorted(entries)]
