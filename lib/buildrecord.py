"""
buildrecord.py -- the build record, output/ti-build.yaml: how one run of
convert.py was made, enough to explain a difference when the same book
built again doesn't come out the same, and to replicate the build.

A run writes it when it ends, built or not, beside the outputs it
describes, and a later run replaces it. Each part's run, inside the
sandbox, leaves what only it knows in output/work/record/<part>.json
(write_part): which targets it built and which were up to date, the
sandbox it ran in, and the limits it had. The run that holds the
project's lock, outside the sandbox, puts those together with what it
asks itself (write): the moment, the command line, the project, this copy
of TextbookImprover, Python and its packages, the parser that read saved
web pages (html5lib, or lxml standing in), the programs a target is
built with, Pandoc's data folders, the platform, the variables that stand
for a setting, every target's and package's stamp (lib/stamps.py), and
the SHA-256 of every file the run's outputs hold.

Every value is a string, as YAML writes it quoted, so no reader takes a
version for a number or "no" for false. Paths are the project's, from its
folder; the command line's, a path inside the project from there too. A
record names the folders --allow-read and --sandbox-read let a run see,
as the stamps do, and so is for the machine it was made on: nothing packs
it yet, and what packs it must leave those out.

What the parts' runs leave is read as data a sandboxed run wrote: a file
that is a link, or too long, is passed over, and the record is written
to a new file that can't be a link someone left in output/.

For each PDF LaTeX built, what it was built with (lib/texrecord.py): the
release, the TeX Live packages and the fonts, and the files read outside
TeX's tree, a file under --allow-read among them.

For each package, how the pages its contents doesn't name were placed,
and the outline --toc read, by its path and SHA-256, which
build-cartridge.py leaves beside the package's stamp (write_package).

And the versions of the checkers the output check ran, which change the
reports and not the outputs.

Not in it yet, of what the archive plan's record holds: a deck's PDF's
and a drawing's LaTeX.

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

import hashlib
import json
import os
import platform
import re
import stat
import sys
import time

import projectpaths

NAME = "ti-build.yaml"
FORMAT = "1"
FRAGMENTS = ("output", "work", "record")
PACKAGES = FRAGMENTS + ("packages",)
# The longest a part's piece may be (bytes): longer, it's passed over.
LONGEST = 1 << 20
# What isn't an output of the run's, under output/: its own files, and
# the record itself.
NOT_OUTPUTS = ("work",)
# What a target may be built with beyond what its stamp asks
# (stamps.COMMON_TOOLS, TEX_TOOLS), by the command that says its version.
OTHER_TOOLS = {
    "bibtex": ["bibtex", "--version"],
    "epstopdf": ["epstopdf", "--version"],
    "kpsewhich": ["kpsewhich", "--version"],
    "pdfseparate": ["pdfseparate", "-v"],
}
# And the Python package that reads a saved web page, which a stamp
# doesn't count: lxml stands in for it where it's missing.
OTHER_PACKAGES = ("html5lib",)


def _strings(value):
    """value with every leaf a string: a mapping's keys and values, a
    list's items; None as ""."""
    if isinstance(value, dict):
        return {str(k): _strings(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strings(v) for v in value]
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "" if value is None else str(value)


def _write_new(path, text):
    """text written to path + ".new", made afresh (never a link or a file
    already there, which is taken away first), then put at path."""
    new = path + ".new"
    if os.path.lexists(new):
        os.remove(new)
    fd = os.open(new, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(new, path)


def _read_small(path):
    """The text of path, a file and not a link, no longer than LONGEST, or
    None."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        data = fh.read(LONGEST + 1)
    if len(data) > LONGEST:
        return None
    return data.decode("utf-8", "replace")


def digest(path):
    found = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            found.update(block)
    return found.hexdigest()


def fragment_path(base, part):
    return os.path.join(projectpaths.of(base).top(*FRAGMENTS), f"{part}.json")


def clear_fragments(base):
    """Take away what an earlier run's parts left, before this run's
    parts leave theirs: done by the run that holds the lock."""
    folder = projectpaths.of(base).top(*FRAGMENTS)
    if os.path.isdir(folder) and not os.path.islink(folder):
        for name in os.listdir(folder):
            if name.endswith(".json"):
                os.remove(os.path.join(folder, name))
    import texrecord
    texrecord.clear(base)


def sandbox_said():
    """The sandbox this process runs in, by the variable the run sets
    inside (lib/sandbox.py), and its version: bubblewrap's, or Landlock's
    ABI."""
    import sandbox
    kind = os.environ.get(sandbox.INSIDE, "")
    if kind == "bwrap":
        import shutil
        import subprocess
        program = shutil.which("bwrap")
        version = ""
        if program:
            done = subprocess.run([program, "--version"], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL)
            version = done.stdout.strip()
        return {"kind": "bubblewrap", "version": version}
    if kind == "landlock":
        return {"kind": "Landlock", "version": str(sandbox.landlock_version())}
    return {"kind": "none", "version": ""}


def write_part(base, part, targets, limits=None, sandbox_env=(), sandbox_read=(),
               allowed=()):
    """What this part's run knows that the run holding the lock doesn't:
    each target built this run or up to date, the sandbox, and the
    limits. Written into output/work/record/, which a run inside the
    sandbox may write."""
    folder = projectpaths.of(base).top(*FRAGMENTS)
    os.makedirs(folder, exist_ok=True)
    values = {
        "part": part,
        "targets": {t.name: {"format": t.format,
                             "built": "up to date" if t.current else "yes" if t.swapped
                             else "no"} for t in targets},
        "sandbox": dict(sandbox_said(), env=list(sandbox_env), read=list(sandbox_read)),
        "allow_read": [str(p) for p in allowed],
    }
    if limits is not None:
        values["limits"] = {"memory": limits.memory, "seconds": limits.seconds,
                            "jobs": limits.jobs}
    path = fragment_path(base, part)
    # A part's run may record twice (a slides run's decks and its
    # PowerPoint targets): the targets of each are kept.
    try:
        previous = json.loads(_read_small(path) or "{}")
    except ValueError:
        previous = {}
    if isinstance(previous, dict) and isinstance(previous.get("targets"), dict):
        values["targets"] = dict(previous["targets"], **values["targets"])
    _write_new(path, json.dumps(_strings(values), indent=1, sort_keys=True))


def write_package(base, values):
    """What a package's build said of itself (build-cartridge.py's
    record_package), kept until the package is built again, as its stamp
    is."""
    folder = projectpaths.of(base).top(*PACKAGES)
    os.makedirs(folder, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", values["package"])[:120]
    _write_new(os.path.join(folder, name + ".json"),
               json.dumps(_strings(values), indent=1, sort_keys=True))


def _packages(base):
    """{package: what its build said}, for each package whose stamp is
    there, read as a sandboxed run's data."""
    folder = projectpaths.of(base).top(*PACKAGES)
    stamps_folder = projectpaths.of(base).top(*projectpaths.STAMPS)
    found = {}
    if not os.path.isdir(folder) or os.path.islink(folder):
        return found
    for name in sorted(os.listdir(folder)):
        try:
            values = json.loads(_read_small(os.path.join(folder, name)) or "null")
        except ValueError:
            continue
        if not isinstance(values, dict) or not isinstance(values.get("package"), str):
            continue
        package = values.pop("package")
        if os.path.isfile(os.path.join(stamps_folder, f"package-{package}.json")):
            found[package] = _strings(values)
    return found


def _fragments(base):
    folder = projectpaths.of(base).top(*FRAGMENTS)
    found = {}
    if os.path.isdir(folder) and not os.path.islink(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".json"):
                try:
                    values = json.loads(_read_small(os.path.join(folder, name)) or "null")
                except ValueError:
                    continue
                if isinstance(values, dict) and isinstance(values.get("part"), str):
                    found[values.pop("part")] = _strings(values)
    return found


def _project(base):
    import yaml
    try:
        with open(projectpaths.of(base).project_file(), encoding="utf-8") as fh:
            values = (yaml.safe_load(fh) or {}).get("project") or {}
    except (OSError, yaml.YAMLError, AttributeError):
        values = {}
    if not isinstance(values, dict):
        values = {}
    return {k: values.get(k, "") for k in ("identifier", "version", "title")}


def _command(base, argv):
    """The command line, the project's folder written as ".": a path
    inside the project read from its folder."""
    root = os.path.realpath(projectpaths.of(base).top())
    out = ["convert.py"]
    for arg in argv:
        if os.path.isabs(arg) and (os.path.realpath(arg) == root
                                   or os.path.realpath(arg).startswith(root + os.sep)):
            arg = os.path.relpath(os.path.realpath(arg), root)
        out.append(arg)
    return out


def _pandoc_data():
    """Whether Pandoc's user data folder holds anything, and whether
    PANDOC_DATA_DIRS was set and how many of its folders hold anything:
    never their paths. TextbookImprover's runs read neither (pandocrun)."""
    home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"),
                                                           ".local", "share")
    folders = [os.path.join(home, "pandoc"), os.path.join(os.path.expanduser("~"), ".pandoc")]
    holds = any(os.path.isdir(f) and os.listdir(f) for f in folders)
    listed = [p for p in os.environ.get("PANDOC_DATA_DIRS", "").split(os.pathsep)
              if p and os.path.isabs(p)]
    return {"user data folder holds files": holds,
            "PANDOC_DATA_DIRS set": "PANDOC_DATA_DIRS" in os.environ,
            "its folders holding files": sum(1 for p in listed
                                              if os.path.isdir(p) and os.listdir(p))}


def _latex(base, targets):
    """What LaTeX built each of targets' PDFs with, this run or the one
    that built what output/ holds (lib/texrecord.py)."""
    import texrecord
    try:
        return texrecord.read(base, targets)
    except OSError:
        return {}


def _platform():
    release = platform.release()
    return {"system": platform.system(), "release": release, "machine": platform.machine(),
            "wsl": "microsoft" in release.lower() or bool(os.environ.get("WSL_DISTRO_NAME"))}


def _stamps(base):
    import stamps
    folder = projectpaths.of(base).top(*projectpaths.STAMPS)
    found = {}
    if os.path.isdir(folder) and not os.path.islink(folder):
        for name in sorted(os.listdir(folder)):
            if os.path.islink(os.path.join(folder, name)):
                continue
            stamp = stamps.read_stamp(os.path.join(folder, name))
            if stamp is not None:
                found[name] = stamp.as_dict()
    return found


def _outputs(base):
    """Each file under output/ the run's outputs hold, by its path from the
    project's folder, and its SHA-256: all but output/work/ and the record."""
    output = projectpaths.of(base).run_output()
    root = projectpaths.of(base).top()
    found = {}
    if not os.path.isdir(output) or os.path.islink(output):
        return found
    for here, dirs, names in os.walk(output):
        if here == output:
            dirs[:] = [d for d in dirs if d not in NOT_OUTPUTS]
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(here, d)))
        for name in sorted(names):
            path = os.path.join(here, name)
            if here == output and name in (NAME, NAME + ".new"):
                continue
            if os.path.isfile(path) and not os.path.islink(path):
                found[os.path.relpath(path, root).replace(os.sep, "/")] = digest(path)
    return found


def _other_tools():
    import shutil
    import subprocess
    found = {}
    for name, command in sorted(OTHER_TOOLS.items()):
        answer = "absent"
        if shutil.which(command[0]):
            try:
                done = subprocess.run(command, capture_output=True, text=True,
                                      stdin=subprocess.DEVNULL, timeout=60)
                lines = (done.stdout.strip() or done.stderr.strip()).splitlines()
                answer = lines[0].strip() if lines else "no answer"
            except (OSError, subprocess.TimeoutExpired):
                answer = "no answer"
        found[name] = answer
    return found


def _first_line(command):
    import subprocess
    try:
        done = subprocess.run(command + ["--version"], capture_output=True, text=True,
                              timeout=120, stdin=subprocess.DEVNULL, errors="replace")
    except (OSError, subprocess.SubprocessError):
        return "no answer"
    lines = [line.strip() for line in (done.stdout or done.stderr).splitlines()
             if line.strip() and not line.startswith("Picked up ")]
    return lines[0] if lines else "no answer"


def _checkers(checks):
    """The versions of the checkers the output check ran (checks: "quick",
    the validators left out, "full", or "wcag", with WCAG's checks too):
    epubcheck, the Nu HTML checker, and veraPDF, by what each's --version
    says, or "not found"; with --wcag, axe-core's version and Ace's, and
    whether veraPDF's WCAG modules were named. They change the reports,
    not the outputs."""
    if checks == "quick":
        return {"validators": "not run (--quick)"}
    import outputcheck
    import pdfcheck
    found = {}
    for name in ("epubcheck", "vnu", "verapdf"):
        command = outputcheck.find_validator(name)
        if not command:
            found[name] = "not found"
        elif name == "verapdf":
            found[name] = (pdfcheck.verapdf_said(command).splitlines() or ["no answer"])[0]
        else:
            found[name] = _first_line(command)
    if checks == "wcag":
        import acecheck
        import axecheck
        path, problem, _note = axecheck.locate_axe()
        found["axe-core"] = axecheck.axe_version(path) if path else f"not used: {problem}"
        command, _why = acecheck.find()
        found["ace"] = (acecheck.version(command) or "no answer") if command else "not found"
        found["verapdf wcag modules"] = "named" if os.environ.get(pdfcheck.WCAG_VARIABLE) \
            else "not named"
    return found


def _html_parser():
    import htmlparse
    return htmlparse.BACKEND or "none"


def values(base, argv, moment, moment_from, status, checks="full"):
    """What the record says, every value a string."""
    import stamps
    import tiversion
    tools = sorted(set(stamps.COMMON_TOOLS + stamps.TEX_TOOLS))
    environment = {}
    for fmt in stamps.OUTPUT_VARIABLES:
        environment.update(stamps.environment_values(fmt))
    if os.environ.get("TZ"):
        environment["TZ"] = os.environ["TZ"]
    parts = _fragments(base)
    return _strings({
        "record": FORMAT,
        "run": {
            "moment": moment,
            "moment, UTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(moment))),
            "moment from": moment_from,
            "exit status": status,
            "command": _command(base, argv),
        },
        "project": _project(base),
        "textbookimprover": tiversion.describe(),
        "python": {"version": sys.version.split()[0],
                   "implementation": platform.python_implementation()},
        "packages": dict(stamps.package_versions(),
                         **stamps.package_versions(OTHER_PACKAGES)),
        "html parser": _html_parser(),
        "checkers": _checkers(checks),
        "tools": dict({name: stamps.tool_version(name) for name in tools}, **_other_tools()),
        "pandoc data": _pandoc_data(),
        "platform": _platform(),
        "environment": environment,
        "parts": parts,
        "packages built": _packages(base),
        "latex": _latex(base, {t for p in parts.values() if isinstance(p, dict)
                               for t in (p.get("targets") or {})}),
        "stamps": _stamps(base),
        "outputs": _outputs(base),
    })


def write(base, argv, moment, moment_from, status, checks="full"):
    """Write output/ti-build.yaml whole, then put it in place."""
    import yaml
    path = os.path.join(projectpaths.of(base).run_output(), NAME)
    text = ("# How this run of TextbookImprover was made (lib/buildrecord.py).\n"
            + yaml.safe_dump(values(base, argv, moment, moment_from, status, checks),
                             default_style='"', sort_keys=False, allow_unicode=True,
                             width=100))
    _write_new(path, text)
    return path
