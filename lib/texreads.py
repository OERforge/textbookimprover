"""What a book's LaTeX may read: the scan before LaTeX runs, and LaTeX's
own list of what it opened, checked after.

LuaLaTeX opens whatever file the book names, and its Lua whatever file
the person who runs it can: a book's \\input{/home/you/notes.tex}, or Lua's
io.open, puts that file's text in the PDF. Two checks keep a part's LaTeX
to what the part may read (projectpaths.Tree.unreadable), TeX's own
trees, the system's fonts, and TextbookImprover's own folder:

    findings = texreads.scan(text, "src/book/ch1.tex", starts, readable)
    if findings.stops: ...stop, saying texreads.stop_lines(findings.stops)
    for line in texreads.note_lines(findings.notes): ...warn

    outside = texreads.recorded_outside(fls_path, readable)

The scan reads the LaTeX the book supplies (a page's raw LaTeX and
front matter, the PDF settings' files, a LaTeX book's own files) for the
commands that read a file, resolves a name written out as TeX would,
and stops on one that leads outside. A name a macro makes, and Lua,
shell escape, and \\openout, it can't follow, so it names them in a
warning instead.

The recorder is LuaLaTeX's -recorder, which lists every file TeX opens in
a .fls file beside the PDF. It caught \\input, \\openin, \\includegraphics,
img.scan, and Lua's io.open, and missed Lua's io.lines and loadfile
(measured), so it's a second net, not a wall; a sandbox is the wall.

--allow-read FOLDER (allow) lets both accept LaTeX's own files under a
folder of the person's, for one run: a package, a class, a bibliography,
an \\input. Not a picture: one outside the project stops the run whatever
--allow-read says, as a picture a page names does.

Copyright (C) 2026 Robert Szarka

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
import re
import subprocess

# TextbookImprover's own folder, whose files its LaTeX may read.
OWN = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# The folders --allow-read gave, as real paths.
ALLOWED = []

# A file LaTeX draws, not reads as TeX: never let in by --allow-read.
PICTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".pdf", ".eps", ".ps", ".svg", ".gif",
                      ".tif", ".tiff", ".jbig2", ".jb2", ".bmp", ".webp", ".mps")

# What a LaTeX book's own folder holds that TeX reads as TeX.
TEX_EXTENSIONS = (".tex", ".ltx", ".sty", ".cls", ".clo", ".def", ".cfg", ".fd", ".bbx",
                  ".cbx", ".lbx", ".tikz", ".pgf", ".pdf_tex", ".pstex_t")

# A file larger than this isn't a LaTeX source anyone writes; it's read
# in part.
LARGEST = 8 << 20


# The system's own folders, which hold programs, libraries, devices, and
# the system's settings and state, never a book's files: --allow-read
# refuses each and anything under it. TeX's own trees among them
# (/usr/share/texlive, /var/lib/texmf, /etc/texmf) are read without it.
SYSTEM_FOLDERS = ("bin", "boot", "dev", "etc", "lib", "lib32", "lib64", "libx32", "proc",
                  "run", "sbin", "snap", "sys", "usr", "var")
# root's home folder, refused whoever runs the build, as the home folder
# is: a folder under it may be named.
ROOT_HOME = "/root"
# A Windows drive's own folders, under WSL's /mnt/<drive>/.
WINDOWS_FOLDERS = ("windows", "program files", "program files (x86)", "programdata")


def refused_folder(path, home=None):
    """Why --allow-read refuses path, a real folder, or None: the whole
    file system; a system folder or one under it; a folder of mounts
    (/mnt, /media) or a drive's root under it, or a Windows drive's own
    folders; the home folder, or a folder holding it, and /root; or a folder reached
    through a dot name (~/.ssh, ~/.config), which holds settings and
    keys."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    parts = [p for p in path.split(os.sep) if p]
    if not parts:
        return "that's the whole file system"
    if parts[0] in SYSTEM_FOLDERS:
        return (f"that's the system's /{parts[0]} folder, or in it, which holds programs, "
                "libraries, devices, or the system's settings and state (TeX's own trees "
                "there are read without --allow-read)")
    if parts[0] in ("mnt", "media") and len(parts) <= 2:
        return "that's a folder of drives, or a drive's top"
    if parts[0] == "mnt" and len(parts) >= 3 and parts[2].lower() in WINDOWS_FOLDERS:
        return "that's a Windows drive's own folder, of its programs or settings"
    if _under(home, path):
        return "that's your home folder, or holds it, with your settings and keys"
    if path == ROOT_HOME:
        return "that's root's home folder, with its settings and keys"
    dotted = next((p for p in parts if p.startswith(".")), None)
    if dotted:
        return f"that's behind a dot name ({dotted}), where settings and keys are kept"
    return None


def refused_anyway(path, home=None):
    """Why --allow-read-anyway still refuses path, a real folder, or None:
    the whole file system, or the home folder or a folder holding it,
    which the sandbox never shows (sandbox.shown), and /root."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    if path == os.sep:
        return "that's the whole file system"
    if _under(home, path):
        return "that's your home folder, or holds it, with your settings and keys"
    if path == ROOT_HOME:
        return "that's root's home folder, with its settings and keys"
    return None


# The folders --allow-read-anyway accepted that --allow-read refuses,
# each with the reason it overrode, for the run to warn of.
OVERRIDDEN = {}


def allow(folders, home=None, anyway=()):
    """Accept LaTeX's own files under each of folders (--allow-read) for
    the rest of the run, none behind a dot name below it, and under each
    of anyway (--allow-read-anyway) too, which refused_folder's rules
    don't hold back but refused_anyway's do. Returns the folders as real
    paths; one that isn't a folder, or that its rules refuse, raises
    ValueError, naming it. OVERRIDDEN says which rule each of anyway's
    overrode."""
    real = []
    OVERRIDDEN.clear()
    for option, given in (("--allow-read", folders), ("--allow-read-anyway", anyway)):
        for folder in given or ():
            path = os.path.realpath(os.path.expanduser(str(folder)))
            if not os.path.isdir(path):
                raise ValueError(f"{option} {folder}: there's no folder there")
            why = refused_folder(path, home)
            if option == "--allow-read-anyway":
                hard = refused_anyway(path, home)
                if hard:
                    raise ValueError(f"{option} {folder}: {hard}, which nothing lets LaTeX "
                                     "read. Name the folder the book's files are in")
                if why:
                    OVERRIDDEN[path] = why
            elif why:
                raise ValueError(f"{option} {folder}: {why}. Name the folder the book's "
                                 "files are in, or, with your eyes open, give it as "
                                 "--allow-read-anyway")
            if path not in real:
                real.append(path)
    ALLOWED[:] = real
    return list(real)


def not_packaged(package, target, folders, part):
    """Why a package isn't built from target's pages, built with
    --allow-read's folders, and how to have it built: the lines to say."""
    return (f"{package} isn't packaged: its pages are target {target}'s, whose build ran "
            f"LaTeX with --allow-read, letting it read files outside the project "
            f"({', '.join(folders)}). A package holds only what the project does, so that "
            "it can be built again from the project alone, and nothing from outside it goes "
            "with the package to whoever it's given. To package it, put the files LaTeX "
            f"read into the project (src/{part}/), or a package or class of yours into your "
            "own TeX tree (TEXMFHOME, which LaTeX reads without --allow-read), and run "
            f"again without --allow-read, which builds {target} again.")


def _allowed(path, folder):
    """Whether path is under folder with no dot name between them, a
    folder --allow-read-anyway gave too."""
    if not _under(path, folder):
        return False
    below = os.path.relpath(path, folder)
    return not any(p.startswith(".") for p in below.split(os.sep) if p != ".")


def _under(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


# -- TeX's trees and the fonts ----------------------------------------------

_TREES = []


def tex_trees():
    """The folders of the TeX on the path, as real paths: its texmf trees
    (kpsewhich's $TEXMF), the variable and configuration trees, and the
    folders of its texmf.cnf files. None where there's no kpsewhich."""
    if _TREES:
        return list(_TREES[0])
    found = []

    def ask(*args):
        try:
            done = subprocess.run(["kpsewhich", *args], capture_output=True, text=True,
                                  timeout=60, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return ""
        return done.stdout if done.returncode == 0 else ""

    for variable in ("$TEXMF", "$TEXMFVAR", "$TEXMFSYSVAR", "$TEXMFCONFIG", "$TEXMFSYSCONFIG",
                     "$TEXMFCACHE"):
        for folder in ask(f"--expand-path={variable}").strip().split(os.pathsep):
            folder = folder.strip()
            if folder and os.path.isabs(folder):
                found.append(os.path.realpath(folder))
    for cnf in ask("-all", "texmf.cnf").splitlines():
        if cnf.strip():
            found.append(os.path.dirname(os.path.realpath(cnf.strip())))
    trees = sorted({f for f in found if f != os.sep})
    _TREES.append(trees)
    return list(trees)


_FONTS = []


def font_files():
    """The font files fontconfig knows (fc-list), as real paths."""
    if not _FONTS:
        try:
            done = subprocess.run(["fc-list", "--format", "%{file}\n"], capture_output=True,
                                  text=True, timeout=120, stdin=subprocess.DEVNULL)
            listed = done.stdout.splitlines() if done.returncode == 0 else []
        except (OSError, subprocess.SubprocessError):
            listed = []
        _FONTS.append({os.path.realpath(f) for f in listed if f.strip()})
    return _FONTS[0]


def font_settings():
    """The folders of fontconfig's settings, which luaotfload reads."""
    home = os.path.expanduser("~")
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return [os.path.realpath(f) for f in
            ("/etc/fonts", os.path.join(config, "fontconfig"),
             os.path.join(home, ".fonts.conf.d"))] + [
        os.path.realpath(os.path.join(home, ".fonts.conf"))]


def is_picture(path):
    return os.path.splitext(path)[1].lower() in PICTURE_EXTENSIONS


def allowed_elsewhere(path, fonts=True):
    """Whether TeX may read path, a real one, though it isn't the part's:
    TeX's own trees, TextbookImprover's folder, the system's fonts and
    fontconfig's settings, /dev/null, or a folder --allow-read gave, for
    a file that isn't a picture."""
    if path == os.devnull or _under(path, OWN):
        return True
    if any(_under(path, tree) for tree in tex_trees()):
        return True
    if not is_picture(path) and any(_allowed(path, folder) for folder in ALLOWED):
        return True
    if fonts:
        if any(_under(path, folder) for folder in font_settings()):
            return True
        if path in font_files():
            return True
    return False


def why_not(path, readable, fonts=True):
    """Why the part's LaTeX may not read path, or None: readable is the
    part's rule for the project (Tree.unreadable, with the folders this
    build writes), given path as its links lead. A file of the system's
    is taken by the path TeX gives too, where a link of the system's own
    leads elsewhere (fontconfig's /etc/fonts/conf.d/ into
    /usr/share/fontconfig/, Debian's texmf.cnf into /etc/texmf/)."""
    real = os.path.realpath(path)
    if allowed_elsewhere(real, fonts) or allowed_elsewhere(os.path.normpath(path), fonts):
        return None
    return readable(real)


# -- the recorder -----------------------------------------------------------

RECORDER = "-recorder"


def recorded(fls_path):
    """The files a .fls says TeX read, each a full path, in the order
    first read: a name it gives from the folder TeX ran in (its PWD line)
    made whole."""
    try:
        with open(fls_path, encoding="utf-8", errors="surrogateescape") as fh:
            lines = fh.read(LARGEST * 4).splitlines()
    except OSError:
        return []
    pwd, seen = None, []
    for line in lines:
        if line.startswith("PWD "):
            pwd = line[4:]
        elif line.startswith("INPUT "):
            name = line[6:]
            if not os.path.isabs(name):
                name = os.path.join(pwd or os.path.dirname(os.path.abspath(fls_path)), name)
            name = os.path.normpath(name)
            if name not in seen:
                seen.append(name)
    return seen


def recorded_outside(fls_path, readable):
    """[(file, why)] for each file the .fls at fls_path says TeX read and
    the part's LaTeX may not (why_not). A .fls that isn't there gives
    [(None, why)], since then nothing says what was read."""
    if not os.path.isfile(fls_path):
        return [(None, "LaTeX left no list of the files it read")]
    return [(path, why) for path, why in
            ((p, why_not(p, readable)) for p in recorded(fls_path)) if why]


def recorded_lines(outside, shown_from):
    """What to say of what the recorder found, a line a file. shown_from
    makes a path to show: from the project's folder inside it, and a
    file outside it named by its folder's name alone, so that the
    message doesn't carry the machine's paths."""
    lines = []
    for path, why in outside:
        if path is None:
            lines.append(f"  {why}, so the PDF can't be checked.")
        else:
            lines.append(f"  {shown_from(path)}, {why}.")
    return lines


def recorder_stop(outside, shown_from, what="the PDF", then=None, part=None):
    """The message that stops a build whose LaTeX read files the part
    may not; then, what's said last, by default that what was being built
    wasn't; part, the part's name, or None for a plain folder."""
    own = f"src/{part}/" if part else "the folder"
    return ("Stopping: LaTeX read " + (f"{len(outside)} file(s)" if outside[0][0] else
                                       "something")
            + f" that {what} may not be built from, by LaTeX's own list of what it "
            "opened (its -recorder file):\n" + "\n".join(recorded_lines(outside, shown_from))
            + f"\nA part's LaTeX reads only its own sources ({own}), TeX's own files, "
            f"and the system's fonts. Copy each file into {own}, keeping no link to where "
            "it was, and name the copy there; "
            "a package, class, bibliography, or other file of LaTeX's that's yours and kept "
            "elsewhere can be read for one run with --allow-read FOLDER, which a build to be "
            "packed can't use. " + (then or f"{what[0].upper() + what[1:]} wasn't built, and "
                                    "an earlier one is as it was."))


# -- the scan ---------------------------------------------------------------

# Commands that read a file, by how their name is given:
#   (arguments to skip before it, how to read it, what kind of file)
# "arg" is a braced argument (or, for \input, a name up to a space); a
# number is how many braced arguments come before the name; "list" a
# comma-separated list; "pair" a folder and a file; "paths" \graphicspath's
# groups; "openin" \openin's register then name; "after_cs" a control
# sequence first (expl3's stream); "keywords" pdfTeX's image keywords.
READERS = {
    "input": (0, "input", "tex"), "include": (0, "arg", "tex"),
    "@input": (0, "arg", "tex"), "@iinput": (0, "arg", "tex"), "@@input": (0, "input", "tex"),
    "InputIfFileExists": (0, "arg", "tex"), "IfFileExists": (0, "arg", "tex"),
    "usepackage": (0, "list", "sty"), "RequirePackage": (0, "list", "sty"),
    "RequirePackageWithOptions": (0, "list", "sty"),
    "documentclass": (0, "arg", "cls"), "LoadClass": (0, "arg", "cls"),
    "LoadClassWithOptions": (0, "arg", "cls"),
    "includegraphics": (0, "arg", "picture"), "includepdf": (0, "arg", "picture"),
    "includesvg": (0, "arg", "picture"), "includestandalone": (0, "arg", "tex"),
    "pgfimage": (0, "arg", "picture"), "pgfdeclareimage": (1, "arg", "picture"),
    "pdfximage": (0, "keywords", "picture"), "saveimageresource": (0, "keywords", "picture"),
    "lstinputlisting": (0, "arg", "file"), "verbatiminput": (0, "arg", "file"),
    "VerbatimInput": (0, "arg", "file"), "BVerbatimInput": (0, "arg", "file"),
    "LVerbatimInput": (0, "arg", "file"), "inputminted": (1, "arg", "file"),
    "bibliography": (0, "list", "bib"), "addbibresource": (0, "arg", "file"),
    "addglobalbib": (0, "arg", "file"), "addsectionbib": (0, "arg", "file"),
    "bibliographystyle": (0, "arg", "bst"),
    "import": (0, "pair", "tex"), "subimport": (0, "pair", "tex"),
    "includefrom": (0, "pair", "tex"), "inputfrom": (0, "pair", "tex"),
    "subincludefrom": (0, "pair", "tex"), "subinputfrom": (0, "pair", "tex"),
    "graphicspath": (0, "paths", "folder"),
    "openin": (0, "openin", "file"),
    "embedfile": (0, "arg", "file"), "attachfile": (0, "arg", "file"),
    "textattachfile": (0, "arg", "file"), "noattachfile": (0, "arg", "file"),
    "pgfplotstableread": (0, "arg", "file"), "csvreader": (0, "arg", "file"),
    "csvautotabular": (0, "arg", "file"), "csvautolongtable": (0, "arg", "file"),
    "csvautobooktabular": (0, "arg", "file"), "csvautobooklongtable": (0, "arg", "file"),
    "DTLloaddb": (1, "arg", "file"), "DTLloadrawdb": (1, "arg", "file"),
    "pdf@filedump": (2, "arg", "file"), "pdf@filemdfivesum": (0, "arg", "file"),
    "pdf@filesize": (0, "arg", "file"), "pdf@filemoddate": (0, "arg", "file"),
    "pdffiledump": (0, "keywords", "file"), "pdfmdfivesum": (0, "keywords", "file"),
    "pdffilesize": (0, "arg", "file"), "pdffilemoddate": (0, "arg", "file"),
    "file_input:n": (0, "arg", "tex"), "file_get:nnN": (0, "arg", "file"),
    "file_get:nnNTF": (0, "arg", "file"), "file_if_exist:nTF": (0, "arg", "file"),
    "file_if_exist:nT": (0, "arg", "file"), "file_if_exist:nF": (0, "arg", "file"),
    "file_if_exist_input:n": (0, "arg", "tex"), "file_if_exist_input:nF": (0, "arg", "tex"),
    "file_mdfive_hash:n": (0, "arg", "file"), "file_size:n": (0, "arg", "file"),
    "file_timestamp:n": (0, "arg", "file"), "file_hex_dump:n": (0, "arg", "file"),
    "file_hex_dump:nnn": (0, "arg", "file"), "file_get_full_name:nN": (0, "arg", "file"),
    "ior_open:Nn": (0, "after_cs", "file"), "ior_open:NnTF": (0, "after_cs", "file"),
    "ior_open:NnT": (0, "after_cs", "file"), "ior_open:NnF": (0, "after_cs", "file"),
}

# What the scan can't follow, by kind: Lua, which can open any file;
# shell escape, which runs a program; and \openout, which writes one.
UNFOLLOWED = {
    "directlua": "lua", "luaexec": "lua", "luadirect": "lua", "latelua": "lua",
    "luacode": "lua", "luacodestar": "lua", "luafunction": "lua",
    "lateluafunction": "lua",
    "write18": "shell", "ShellEscape": "shell", "sys_shell_now:n": "shell",
    "sys_shell_shipout:n": "shell", "sys_shell_now:e": "shell", "sys_shell_get:nnN": "shell",
    "ior_shell_open:Nn": "shell", "pdfshellescape": None, "immediatewrite18": "shell",
    "openout": "write", "iow_open:Nn": "write",
}
LUA_ENVIRONMENTS = ("luacode", "luacode*", "luacodestar")

# Environments whose text is set as it is written, not run.
VERBATIM = ("verbatim", "verbatim*", "Verbatim", "Verbatim*", "BVerbatim", "BVerbatim*",
            "LVerbatim", "LVerbatim*", "lstlisting", "minted", "comment", "luacode",
            "luacode*", "luacodestar")
# \verb and its kin, whose text runs to the next of the character after.
INLINE_VERBATIM = re.compile(r"\\(verb|lstinline|mintinline|Verb|spverb)\*?"
                             r"(?:\[[^\]\n]*\])?(?:\{[^}\n]*\})?")

# A command's name: expl3's, with its underscores and signature, or
# LaTeX's, with the @ of a package's own.
COMMAND = re.compile(r"\\([A-Za-z@_]+:[A-Za-z]+|[A-Za-z@]+)")

# A name no macro makes: TeX's own characters out of it.
NOT_LITERAL = re.compile(r"[\\#$^~{}%]")

NOTES = {
    "lua": "runs Lua, which can open any file",
    "shell": "runs a program through shell escape",
    "write": "writes a file (\\openout), which TeX keeps to the folder it runs in",
    "made": "names a file by a macro or a variable, which the scan can't follow",
}


class Findings:
    """What the scan found: stops, (where, line, command, name, why) for
    each name leading outside; notes, (where, line, kind, text) for each
    thing it can't follow."""

    def __init__(self):
        self.stops = []
        self.notes = []

    def extend(self, other):
        self.stops.extend(other.stops)
        self.notes.extend(other.notes)
        return self


def without_comments(line):
    """A line of LaTeX less its comment: from the first % not escaped by
    a backslash."""
    index = 0
    while True:
        index = line.find("%", index)
        if index < 0:
            return line
        slashes = 0
        while index - slashes - 1 >= 0 and line[index - slashes - 1] == "\\":
            slashes += 1
        if slashes % 2 == 0:
            return line[:index]
        index += 1


def _blank_inline_verbatim(line):
    out, position = [], 0
    for match in INLINE_VERBATIM.finditer(line):
        if match.start() < position:
            continue
        end = match.end()
        if end < len(line):
            delimiter = line[end]
            close = "}" if delimiter == "{" else delimiter
            stop = line.find(close, end + 1)
            stop = len(line) - 1 if stop < 0 else stop
            out.append(line[position:match.start()] + " " * (stop + 1 - match.start()))
            position = stop + 1
        else:
            out.append(line[position:match.start()] + " " * (end - match.start()))
            position = end
    out.append(line[position:])
    return "".join(out)


def runnable(text):
    """text's lines as TeX would run them, each kept at its number: the
    comments out, and the text of verbatim environments and \\verb blanked;
    and [(line, environment)] for each Lua environment met."""
    lines, inside, lua = [], None, []
    begin = re.compile(r"\\begin\s*\{(" + "|".join(re.escape(v) for v in VERBATIM) + r")\}")
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw
        kept = ""
        while True:
            if inside:
                end = line.find("\\end{" + inside + "}")
                if end < 0:
                    line = ""
                    break
                line = line[end + len("\\end{" + inside + "}"):]
                inside = None
                continue
            line = without_comments(_blank_inline_verbatim(line))
            match = begin.search(line)
            if not match:
                kept += line
                break
            kept += line[:match.end()]
            if match.group(1) in LUA_ENVIRONMENTS:
                lua.append((number, match.group(1)))
            inside = match.group(1)
            line = line[match.end():]
        lines.append(kept)
    return lines, lua


def _skip_space(text, i):
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _group(text, i, opening="{", closing="}"):
    """The text of the balanced group opening at i, and the index after
    it; (None, i) if none opens there."""
    if i >= len(text) or text[i] != opening:
        return None, i
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == opening:
            depth += 1
        elif c == closing:
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return None, i


def _options(text, i):
    """i past a star and any optional arguments ([...])."""
    i = _skip_space(text, i)
    if i < len(text) and text[i] == "*":
        i = _skip_space(text, i + 1)
    while i < len(text) and text[i] == "[":
        _, after = _group(text, i, "[", "]")
        if after == i:
            break
        i = _skip_space(text, after)
    return i


def _plain_name(text, i):
    """A name given as TeX's \\input takes one without braces: up to a
    space or the end of the line; None where a control sequence or a
    group comes first."""
    i = _skip_space(text, i)
    if i >= len(text) or text[i] in "\\{}":
        return None, i
    j = i
    while j < len(text) and text[j] not in " \t\r\n\\{}":
        j += 1
    return text[i:j], j


def names_at(text, i, how, skip):
    """The names a reading command gives, the command's own name ending at
    i: [(name or None where it can't be read)], by how (READERS)."""
    if how == "input":
        j = _options(text, i)
        if j < len(text) and text[j] == "{":
            name, _ = _group(text, j)
            return [name]
        name, _ = _plain_name(text, j)
        return [name]
    if how == "openin":
        j = _skip_space(text, i)
        match = re.compile(r"\\[A-Za-z@]+|\d+").match(text, j)
        if not match:
            return [None]
        j = _skip_space(text, match.end())
        if j < len(text) and text[j] == "=":
            j = _skip_space(text, j + 1)
        if j < len(text) and text[j] == "{":
            name, _ = _group(text, j)
            return [name]
        name, _ = _plain_name(text, j)
        return [name]
    if how == "keywords":
        j = _skip_space(text, i)
        while j < len(text):
            if text[j] == "{":
                name, _ = _group(text, j)
                return [name]
            if text[j] == "\\" or text[j] == "\n":
                return [None]
            j += 1
        return [None]
    j = _options(text, i)
    if how == "after_cs":
        match = re.compile(r"\\[A-Za-z@_:]+").match(text, j)
        if not match:
            return [None]
        j = _skip_space(text, match.end())
    for _ in range(skip):
        _, after = _group(text, j)
        if after == j:
            return [None]
        j = _options(text, after)
    first, after = _group(text, j)
    if first is None:
        return [None]
    if how == "list":
        return [n.strip() for n in first.split(",") if n.strip()] or []
    if how == "pair":
        second, _ = _group(text, _skip_space(text, after))
        if second is None:
            return [None]
        if NOT_LITERAL.search(first) or NOT_LITERAL.search(second):
            return [None]
        return [os.path.join(first.strip(), second.strip())]
    if how == "paths":
        found, k = [], 0
        while k < len(first):
            k = _skip_space(first, k)
            name, after = _group(first, k)
            if name is None:
                break
            found.append(name)
            k = after
        return found or [first]
    return [first]


EXTENSIONS = {"tex": (".tex",), "sty": (".sty",), "cls": (".cls",), "bib": (".bib",),
              "bst": (".bst",), "picture": (), "file": (), "folder": ()}


def resolve(name, kind, starts, readable):
    """Why name, written out, may not be read, or None: from each folder
    of starts, as TeX finds a name from the folder it runs in and the
    folders on its paths, and as it is when it's a full path, each with
    the extension TeX adds (EXTENSIONS)."""
    name = name.strip().strip('"')
    if not name:
        return None
    for start in ([None] if os.path.isabs(name) else starts):
        place = os.path.normpath(name if start is None else os.path.join(start, name))
        for candidate in [place] + [place + e for e in EXTENSIONS.get(kind, ())]:
            real = os.path.realpath(candidate)
            if kind != "picture" and allowed_elsewhere(real, fonts=False):
                continue
            if kind == "picture" and (_under(real, OWN)
                                      or any(_under(real, t) for t in tex_trees())):
                continue
            why = readable(real)
            if why:
                return why
    return None


def scan(text, where, starts, readable, first_line=1):
    """Findings for text, LaTeX the book supplies, from where (a file's
    path from the project's folder, or a page's raw LaTeX said in
    words): a reading command's name written out that resolves outside
    what readable allows, from any of starts, stops; a name a macro
    makes, Lua, shell escape, and \\openout are noted."""
    found = Findings()
    lines, lua = runnable(text)
    for number, environment in lua:
        found.notes.append((where, number + first_line - 1, "lua",
                            "\\begin{" + environment + "}"))
    for index, line in enumerate(lines):
        number = index + first_line
        # A command's arguments may run on to the next lines.
        tail = "\n".join([line] + lines[index + 1:index + 4])
        for match in COMMAND.finditer(line):
            command = match.group(1)
            if command == "write" and re.match(r"\s*18\b", line[match.end():]):
                found.notes.append((where, number, "shell", "\\write18"))
                continue
            if command in UNFOLLOWED:
                kind = UNFOLLOWED[command]
                if kind:
                    found.notes.append((where, number, kind, "\\" + command))
                continue
            if command not in READERS:
                continue
            skip, how, kind = READERS[command]
            for name in names_at(tail, match.end(), how, skip):
                shown = "\\" + command + ("{" + name + "}" if name is not None else "")
                if name is None or NOT_LITERAL.search(name):
                    found.notes.append((where, number, "made", shown))
                    continue
                why = resolve(name, kind, starts, readable)
                if why:
                    found.stops.append((where, number, "\\" + command, name, why))
    return found


def scan_file(path, where, starts, readable):
    """scan() of a file of LaTeX."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(LARGEST)
    except OSError:
        return Findings()
    return scan(text, where, starts, readable)


def tex_files(folder):
    """The files under folder that TeX reads as TeX (TEX_EXTENSIONS), by
    path from it, in order; a dot name and a linked folder passed over,
    as a part's reading does."""
    found = []
    for top, folders, files in os.walk(folder):
        folders[:] = sorted(f for f in folders if not f.startswith(".")
                            and not os.path.islink(os.path.join(top, f)))
        for name in sorted(files):
            if not name.startswith(".") and os.path.splitext(name)[1].lower() in TEX_EXTENSIONS:
                found.append(os.path.relpath(os.path.join(top, name), folder))
    return found


def raw_latex(node, found=None, page=None, pages=None):
    """[(page, text)] for every raw LaTeX block and inline in a Pandoc
    document's JSON, node, its metadata's too, each with the page it's
    on: the id of the nearest page Div pages names (pages: a set of
    ids), or None."""
    if found is None:
        found = []
    if isinstance(node, dict):
        kind = node.get("t")
        if kind in ("RawBlock", "RawInline"):
            content = node.get("c") or ["", ""]
            if len(content) == 2 and str(content[0]).lower() in ("latex", "tex", "beamer"):
                found.append((page, str(content[1])))
            return found
        if kind == "Div" and pages:
            try:
                ident = node["c"][0][0]
            except (KeyError, IndexError, TypeError):
                ident = None
            if ident in pages:
                page = ident
        for value in node.values():
            if isinstance(value, (dict, list)):
                raw_latex(value, found, page, pages)
    elif isinstance(node, list):
        for value in node:
            raw_latex(value, found, page, pages)
    return found


TEMPLATE_PARTIAL = re.compile(r"\$\{?\s*(?:[\w.-]+:)?([\w.-]+)\(\)")


def template_files(path):
    """A Pandoc template and the partials it names that are beside it,
    as Pandoc looks for them: its folder, the template's extension added
    where the name has none."""
    found, todo = [], [os.path.abspath(path)]
    extension = os.path.splitext(path)[1]
    while todo:
        current = todo.pop(0)
        if current in found or not os.path.isfile(current):
            continue
        found.append(current)
        try:
            with open(current, encoding="utf-8", errors="replace") as fh:
                text = fh.read(LARGEST)
        except OSError:
            continue
        for name in TEMPLATE_PARTIAL.findall(text):
            if "/" in name or name.startswith("."):
                continue
            partial = os.path.join(os.path.dirname(current), name)
            if not os.path.splitext(name)[1]:
                partial += extension
            todo.append(partial)
    return found


def stop_lines(stops):
    """What to say of each name that leads outside, a line each."""
    return [f"  {where}" + (f", line {number}" if number else "")
            + f": {command}{{{name}}}, {why}." for where, number, command, name, why in stops]


def part_of(project):
    """The part a run builds, or None for a plain folder."""
    return project.part() if hasattr(project, "part") else None


def stop_message(stops, part, nothing):
    """The message that stops a run whose LaTeX names files outside; part
    None for a plain folder."""
    own = f"src/{part}/" if part else "the folder"
    return (f"Stopping: the book's LaTeX names {len(stops)} file(s) outside what the part "
            f"reads, its own sources ({own}):\n" + "\n".join(stop_lines(stops))
            + f"\nCopy each file into {own}, keeping no link to where it was, and name "
            "the copy there. A package, class, bibliography, or other file of LaTeX's that's "
            "yours and kept elsewhere can be read for one run with --allow-read FOLDER, which "
            "a build to be packed can't use; a picture can't." + (" " + nothing if nothing
                                                                  else ""))


def note_lines(notes, most=3):
    """A warning for what the scan can't follow, a line for each kind,
    with its first places; [] for none."""
    if not notes:
        return []
    kinds = []
    for _w, _n, kind, _t in notes:
        if kind not in kinds:
            kinds.append(kind)
    lines = [f"WARNING: the book's LaTeX does {len(notes)} thing(s) that no check before "
             "LaTeX runs can follow. LaTeX's own list of the files it opened is checked after "
             "it runs, but Lua can read a file that list doesn't name:"]
    for kind in kinds:
        these = [(w, n, t) for w, n, k, t in notes if k == kind]
        places = "; ".join(f"{t} at {w}" + (f", line {n}" if n else "")
                           for w, n, t in these[:most])
        more = f"; and {len(these) - most} more" if len(these) > most else ""
        lines.append(f"  It {NOTES[kind]} ({len(these)}): {places}{more}.")
    # sandbox.INSIDE, which imports this module.
    if os.environ.get("TEXTBOOKIMPROVER_SANDBOX"):
        lines.append("  The run's sandbox keeps it from what's outside the project "
                     "(docs/layout.md, The sandbox).")
    else:
        lines.append("  This run isn't sandboxed (--no-sandbox), so build only a book you trust "
                     "(docs/layout.md, The sandbox).")
    return lines


# -- the part's rule, for a project or a plain folder ----------------------

def rule(project, part=None, also=()):
    """Why a part's LaTeX may not read a path, or None: what the part may
    read (projectpaths.Tree.unreadable), and the folders also names, the
    build's own. project is the path module's object; for a plain folder
    (projectpaths.Project), the folder itself."""
    own = [os.path.realpath(a) for a in also]

    def why(path):
        real = os.path.realpath(path)
        if any(_under(real, folder) for folder in own):
            return None
        if hasattr(project, "unreadable"):
            return project.unreadable(real, part)
        if project.inside(real):
            return None
        return "which leads out of the folder"
    return why


def scan_document(document, where, starts, readable):
    """Findings for a Pandoc document's raw LaTeX, its metadata's too
    (header-includes, include-before, and the rest), each block said to
    be in where (a page, the PDF's metadata)."""
    found = Findings()
    for _page, text in raw_latex(document):
        one = scan(text, where, starts, readable)
        # A block's lines aren't the source's, so none is given.
        found.stops += [(w, None, c, n, y) for w, _n, c, n, y in one.stops]
        found.notes += [(w, None, k, t) for w, _n, k, t in one.notes]
    return found


def scan_files(folder, names, shown, starts, readable):
    """Findings for files of LaTeX: names, paths from folder, each said as
    shown(name) gives it."""
    found = Findings()
    for name in names:
        found.extend(scan_file(os.path.join(folder, name), shown(name), starts, readable))
    return found


def report(findings, say, part, nothing):
    """Say what the scan noted, as one warning; and stop, raising
    SystemExit with the message, if a name leads outside."""
    for line in note_lines(findings.notes):
        say(line)
    if findings.stops:
        raise SystemExit(stop_message(findings.stops, part, nothing))


def shown(top, path):
    """A file's path as a message shows it: from the project's folder,
    top, inside it, and whole outside it, where the person has to find
    it."""
    top = os.path.realpath(top)
    real = os.path.realpath(path)
    return os.path.relpath(real, top) if _under(real, top) and real != top else real
