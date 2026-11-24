"""The sandbox a run converts in: what it can see, write, and reach.

A book can make the programs a run starts read files: raw LaTeX's
\\input, Lua's io.open and io.lines, a picture a page names, a writer that
fetches what a page names by URL. The read checks stop what can be found
by reading the book (texreads, convert.py's check_reads); a sandbox is
the wall behind them, for what can't be found that way.

    kind, why = sandbox.available()          # "bwrap", "landlock", or None
    code = sandbox.run(kind, command, base, part, ...)

A run of one part, once it has unpacked the part's upstream file and
made its sidecars UTF-8, starts itself again inside the sandbox and
waits for it (convert.py's enter_sandbox). Inside:

- bubblewrap (bwrap), where it works: the system's programs and
  libraries (/usr), the parts of /etc a run reads (SHOWN_ETC), a passwd,
  group, and hosts file of its own, TeX's trees, TextbookImprover's
  folder, its Python, the programs on the path and the tools the
  environment names, the person's own fonts, and the project, all
  read-only; output/ writable; /tmp and the home folder empty and
  writable, and gone when the run ends; no network; a new session, so
  it can't type into the terminal it was started from.
- Landlock, where bubblewrap doesn't work: the same folders, read-only,
  and output/ writable, but an outside file's name and size are still
  visible, though not its contents, /etc's passwd is the system's, and
  TCP is refused only from Landlock's version 4 (Linux 6.7).
- With neither, the run stops, unless --no-sandbox.

The environment inside is TextbookImprover's own list (KEPT, KEPT_PREFIXES),
anything else dropped, with --sandbox-env NAME for one more; and
--sandbox-read PATH shows one more file or folder, read-only.

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

import ctypes
import os
import re
import shutil
import signal
import subprocess
import sys

import projectpaths
import texreads

# The variable a run inside is started with, naming the sandbox; the run
# inside believes it only when the sandbox can be seen (inside()).
INSIDE = "TEXTBOOKIMPROVER_SANDBOX"
OWN = texreads.OWN

# The environment a run keeps inside, by name and by prefix: the locale and
# the clock, the path, Python's, TeX's, Pandoc's, TextbookImprover's own,
# and each tool's (convert.py, outputcheck, pdfcheck, acecheck, axecheck,
# decksave, the reveal.js copy). A token, a key, an agent's socket, the
# display, and a proxy aren't among them.
KEPT = ("PATH", "LANG", "LANGUAGE", "TZ", "TERM", "COLUMNS", "LINES", "NO_COLOR",
        "SOURCE_DATE_EPOCH", "HOME", "USER", "LOGNAME", "TMPDIR",
        "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING", "PYTHONUTF8",
        "PYTHONHASHSEED", "PYTHONWARNINGS", "VIRTUAL_ENV",
        "JAVACMD", "JAVA_HOME", "JAVA_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS",
        "EPUBCHECK_JAR", "VNU_JAR", "VERAPDF", "VERAPDF_WCAG", "ACE", "AXE_CORE_DIR",
        "PLAYWRIGHT_BROWSERS_PATH", "REVEALJS_DIR", "LIBREOFFICE", "CLASSPATH_PREFIX",
        "DOWNSAMPLED", "BOOK_LATEX_COLORS", "BOOK_LATEX_LAYOUT",
        "FONTCONFIG_FILE", "FONTCONFIG_PATH", "NODE_PATH")
KEPT_PREFIXES = ("LC_", "OER_", "TEXTBOOKIMPROVER_", "TEX", "KPSE", "BIBINPUTS", "BSTINPUTS",
                 "PANDOC")
# Variables whose value names a file or folder a program needs to see:
# the tools the environment names, and TeX's and Python's paths.
NAMING = ("EPUBCHECK_JAR", "VNU_JAR", "VERAPDF", "VERAPDF_WCAG", "ACE", "AXE_CORE_DIR",
          "PLAYWRIGHT_BROWSERS_PATH", "REVEALJS_DIR", "LIBREOFFICE", "JAVA_HOME", "JAVACMD",
          "VIRTUAL_ENV", "PYTHONPATH", "NODE_PATH", "TEXMFHOME", "TEXMFLOCAL", "TEXINPUTS",
          "FONTCONFIG_FILE", "FONTCONFIG_PATH")

# What of /etc a run reads (the traces of three books' builds, and what
# the programs it starts read besides): the dynamic loader's cache, the
# fonts' settings, the paper size, Perl's and latexmk's, TeX's, Java's,
# LibreOffice's, Ghostscript's, ImageMagick's, the XML catalogs, the
# certificates, the time zone, the media types Python's mimetypes reads,
# the links Debian's alternatives make. Inside bubblewrap, passwd, group,
# and hosts are files of the sandbox's own (written()), naming only the
# person running it.
SHOWN_ETC = ("alternatives", "fonts", "ghostscript", "gnutls", "ImageMagick-6",
             "ImageMagick-7", "java", "LatexMk", "ld.so.cache", "ld.so.conf", "ld.so.conf.d",
             "libpaper.d", "libreoffice", "localtime", "magic", "mime.types",
             "nsswitch.conf", "os-release", "papersize", "paperspecs", "perl", "ssl",
             "texmf", "timezone", "xdg", "xml", "xpdfrc")
ETC_PREFIXES = ("java-", "ImageMagick")
# The person's own fonts and fontconfig's settings, under the home folder.
HOME_SHOWN = (".fonts", ".fonts.conf", ".fonts.conf.d", os.path.join(".local", "share", "fonts"),
              os.path.join(".config", "fontconfig"))
# The top of the system: shown read-only, or made the links they are.
TOP_SYSTEM = ("bin", "sbin", "lib", "lib32", "lib64", "libx32")


class Unavailable(Exception):
    """Why a sandbox can't be had here."""


# -- what's here --------------------------------------------------------------

def bwrap_works():
    """Whether bubblewrap is here and can make its namespaces: None, or why
    not, in words."""
    program = shutil.which("bwrap")
    if not program:
        return "bubblewrap (bwrap) isn't installed"
    command = [program, "--unshare-all", "--die-with-parent", "--ro-bind", "/usr", "/usr"]
    command += system_links()
    command += ["--proc", "/proc", "--dev", "/dev", "true"]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=20,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"bubblewrap couldn't be started ({exc})"
    if done.returncode != 0:
        said = (done.stderr.strip().splitlines() or [""])[-1]
        return f"bubblewrap couldn't make its namespaces here ({said or done.returncode})"
    return None


def landlock_version():
    """Landlock's version (ABI) in this kernel, or 0."""
    if not sys.platform.startswith("linux"):
        return 0
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        version = libc.syscall(SYS_CREATE_RULESET, None, ctypes.c_size_t(0),
                               ctypes.c_uint32(1))
    except (OSError, AttributeError):
        return 0
    return version if version > 0 else 0


def available():
    """(kind, why): "bwrap" where bubblewrap works, else "landlock" where
    the kernel has it, else None, with why bubblewrap doesn't work."""
    why = bwrap_works()
    if why is None:
        return "bwrap", None
    if landlock_version():
        return "landlock", why
    return None, why


def inside():
    """The sandbox this run is in, or None: what INSIDE says, believed only
    where it shows (bubblewrap's new process numbers, Landlock's refusal to
    list /). A run that says it's inside and isn't raises Unavailable."""
    kind = os.environ.get(INSIDE)
    if not kind:
        return None
    if kind == "bwrap" and os.getpid() <= 3:
        return kind
    if kind == "landlock":
        try:
            os.listdir("/")
        except PermissionError:
            return kind
    raise Unavailable(f"{INSIDE} says the run is inside {kind}, and it isn't")


# -- what's shown -------------------------------------------------------------

def system_links():
    """bubblewrap's arguments for /bin, /lib and the rest: a link where the
    system has one (/bin -> usr/bin), the folder read-only where it has a
    folder."""
    args = []
    for name in TOP_SYSTEM:
        path = os.path.join(os.sep, name)
        if os.path.islink(path):
            args += ["--symlink", os.readlink(path), path]
        elif os.path.isdir(path):
            args += ["--ro-bind", path, path]
    return args


def _under(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def etc_shown():
    """The entries of /etc a run reads, those that are here."""
    try:
        names = os.listdir("/etc")
    except OSError:
        return []
    return sorted(os.path.join("/etc", n) for n in names
                  if n in SHOWN_ETC or n.startswith(ETC_PREFIXES))


# Mounts of another machine's drives: WSL's of Windows' (drvfs, over 9p),
# and a virtual machine's shared folder (9p).
OTHER_DRIVES = ("9p", "v9fs", "drvfs")


def _mounts():
    """(mount point, its file system's type) for each mount, from
    /proc/self/mounts, its octal escapes read; [] where it can't be read."""
    if "mounts" not in _CACHE:
        found = []
        try:
            with open("/proc/self/mounts", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    fields = line.split()
                    if len(fields) >= 3:
                        point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)),
                                       fields[1])
                        found.append((point, fields[2]))
        except OSError:
            pass
        _CACHE["mounts"] = found
    return _CACHE["mounts"]


_CACHE = {}


def on_other_drive(path, mounts=None):
    """Whether a folder is on another drive than the system's: under /mnt
    or /media, where WSL mounts Windows' drives and a desktop a removable
    one, or on a mount of another machine's drive (OTHER_DRIVES). WSL puts
    Windows' own program folders on the path (/mnt/c/Windows/System32 and
    the rest): the sandbox shows none of them, and they leave its path, as
    --allow-read refuses /mnt and /media unless told otherwise."""
    if not path or not os.path.isabs(path):
        return False
    plain = os.path.abspath(path)
    if any(_under(plain, top) for top in ("/mnt", "/media")):
        return True
    real = os.path.realpath(plain)
    if any(_under(real, top) for top in ("/mnt", "/media")):
        return True
    return any(kind in OTHER_DRIVES and point != os.sep and _under(real, point)
               for point, kind in (_mounts() if mounts is None else mounts))


def program_folders(mounts=None):
    """The folders of the programs on the path, and of what a link there
    leads to, outside /usr: a tool installed in the home folder or /opt,
    reached through a link in ~/.local/bin. A folder on another drive
    (on_other_drive) isn't one, and isn't looked into, which under WSL
    would read Windows' folders over its slow file system on every run."""
    found = []
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder or not os.path.isabs(folder) or on_other_drive(folder, mounts) \
                or not os.path.isdir(folder):
            continue
        real = os.path.realpath(folder)
        if _under(real, "/usr"):
            continue
        found.append(real)
        try:
            entries = os.listdir(real)
        except OSError:
            continue
        for name in entries:
            path = os.path.join(real, name)
            if not os.path.islink(path):
                continue
            target = os.path.realpath(path)
            if _under(target, "/usr") or on_other_drive(target, mounts) \
                    or not os.path.exists(target):
                continue
            parent = os.path.dirname(target)
            # A program in a bin/ folder is shown with the install around it.
            found.append(os.path.dirname(parent) if os.path.basename(parent) == "bin"
                         else parent)
    return found


def python_folders():
    """This Python's folders: its prefixes, the folder of the name it was
    started by and of the file that name leads to, and every folder on its
    path."""
    found = [sys.prefix, sys.base_prefix, sys.exec_prefix,
             os.path.dirname(os.path.abspath(sys.executable)),
             os.path.dirname(os.path.realpath(sys.executable))]
    found += [p for p in sys.path if p and os.path.isabs(p)]
    return [os.path.realpath(p) for p in found if os.path.exists(p)]


def link_chain(path):
    """The links a path goes through to its file, each (where the link
    is, what it says), in the order they're met: a Python that uv or pyenv
    keeps under the home folder is often reached by a link to a folder of
    links."""
    found, seen = [], set()
    todo = [p for p in os.path.abspath(path).split(os.sep) if p]
    here = os.sep
    while todo and len(seen) < 40:
        here = os.path.join(here, todo.pop(0))
        if os.path.islink(here) and here not in seen:
            seen.add(here)
            said = os.readlink(here)
            found.append((here, said))
            rest = [p for p in said.split(os.sep) if p]
            here = os.sep if os.path.isabs(said) else os.path.dirname(here)
            todo = rest + todo
    return found


def python_links():
    """The links this Python's names go through (link_chain), for the
    sandbox to make where it shows their files."""
    found = []
    for path in (sys.executable, sys.prefix, sys.base_prefix, sys.exec_prefix):
        for link in link_chain(path):
            if link not in found:
                found.append(link)
    return found


def named_folders(environment):
    """The files and folders the kept environment's variables name, a
    file's folder for a file (a jar finds its libraries beside it)."""
    found = []
    for name in NAMING:
        for value in environment.get(name, "").split(os.pathsep):
            value = value.strip().rstrip("/") if value.strip() != "/" else ""
            if not value or not os.path.isabs(value):
                continue
            real = os.path.realpath(value)
            if os.path.isfile(real):
                found.append(os.path.dirname(real))
            elif os.path.isdir(real):
                found.append(real)
    return found


def tex_folders():
    """TeX's trees and its programs' folder."""
    found = list(texreads.tex_trees())
    program = shutil.which("lualatex") or shutil.which("kpsewhich")
    if program:
        found.append(os.path.dirname(os.path.realpath(program)))
    return found


def home_shown(home):
    return [os.path.join(home, n) for n in HOME_SHOWN if os.path.exists(os.path.join(home, n))]


def shown(base, environment, also=(), home=None):
    """The real paths shown read-only, besides /usr, /etc's, and the
    project: TextbookImprover's folder, Python's, the programs', TeX's, the
    tools the environment names, the fonts' cache, the person's fonts, and
    also (--allow-read's folders, --sandbox-read's paths). None is the root,
    the home folder, or a folder holding it, whose binding would undo the
    empty home folder; such a one is left out, said in the second list."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    root = os.path.realpath(projectpaths.of(base).top())
    wanted = [OWN] + python_folders() + program_folders() + tex_folders() \
        + named_folders(environment) + home_shown(home) + ["/var/cache/fontconfig"] \
        + [os.path.realpath(p) for p in also]
    paths, left = [], []
    for path in wanted:
        if not os.path.exists(path) or _under(path, "/usr") or _under(path, "/etc") \
                or _under(path, root) or _under(path, "/proc") or _under(path, "/dev"):
            continue
        if path == os.sep or _under(home, path):
            left.append(path)
            continue
        if path not in paths:
            paths.append(path)
    # A folder inside another shown one needs no binding of its own.
    paths = [p for p in paths if not any(q != p and _under(p, q) for q in paths)]
    return sorted(paths), sorted(set(left))


# -- the environment ----------------------------------------------------------

def environment(base, kind, extra=()):
    """The environment inside: the kept variables, and extra
    (--sandbox-env), and INSIDE naming the sandbox; TeX's variable tree
    (TEXMFVAR) and caches in the project's output/work/, since TeX's own
    tree is read-only inside."""
    kept = {k: v for k, v in os.environ.items()
            if k in KEPT or k.startswith(KEPT_PREFIXES) or k in extra}
    if "PATH" in kept:
        kept["PATH"] = os.pathsep.join(p for p in kept["PATH"].split(os.pathsep)
                                       if p and not on_other_drive(p))
    work = os.path.realpath(projectpaths.of(base).run_work())
    kept["TEXMFVAR"] = os.path.join(work, "texmf-var")
    kept["XDG_CACHE_HOME"] = os.path.join(work, "cache")
    kept[INSIDE] = kind
    return kept


# -- bubblewrap ---------------------------------------------------------------

def written(base, home):
    """The passwd, group, and hosts files the sandbox shows, written into
    output/work/sandbox/: only the person running it, and localhost."""
    folder = os.path.realpath(projectpaths.of(base).run_work("sandbox"))
    os.makedirs(folder, exist_ok=True)
    uid, gid = os.getuid(), os.getgid()
    try:
        import pwd
        name = pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        name = "person"
    files = {"passwd": f"{name}:x:{uid}:{gid}::{home}:/bin/sh\n",
             "group": f"{name}:x:{gid}:\n",
             "hosts": "127.0.0.1 localhost\n::1 localhost\n"}
    made = {}
    for file, text in files.items():
        path = os.path.join(folder, file)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        made[file] = path
    return made


def bwrap_command(base, command, paths, home=None):
    """The bubblewrap command that runs command, a list, in base inside the
    sandbox, paths shown read-only besides the system's."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    root = os.path.realpath(projectpaths.of(base).top())
    output = os.path.realpath(projectpaths.of(base).run_output())
    args = [shutil.which("bwrap"), "--unshare-all", "--die-with-parent", "--new-session",
            "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr"] + system_links()
    for path in etc_shown():
        args += ["--ro-bind", path, path]
    for file, path in written(base, home).items():
        args += ["--ro-bind", path, os.path.join("/etc", file)]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/run"]
    # The home folder empty and writable, before anything under it is shown.
    if not _under(home, "/tmp") and home != os.sep:
        args += ["--tmpfs", home]
    for path in sorted(paths, key=lambda p: p.count(os.sep)):
        args += ["--ro-bind", path, path]
    # A link of Python's in a folder the sandbox makes empty (the home
    # folder, /tmp), made again there; one in a folder it shows is there.
    for link, said in python_links():
        if any(_under(link, top) for top in ("/tmp", "/run", home)) \
                and not any(_under(link, shown) for shown in paths):
            args += ["--symlink", said, link]
    args += ["--ro-bind", root, root, "--bind", output, output, "--chdir", root]
    return args + list(command)


# -- Landlock -----------------------------------------------------------------

SYS_CREATE_RULESET, SYS_ADD_RULE, SYS_RESTRICT_SELF = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
RULE_PATH_BENEATH, RULE_NET_PORT = 1, 2
FS = {"execute": 1, "write_file": 2, "read_file": 4, "read_dir": 8, "remove_dir": 16,
      "remove_file": 32, "make_char": 64, "make_dir": 128, "make_reg": 256, "make_sock": 512,
      "make_fifo": 1024, "make_block": 2048, "make_sym": 4096, "refer": 8192,
      "truncate": 16384, "ioctl_dev": 32768}
# What a folder of sockets alone takes: making a socket there and
# removing one, as LibreOffice makes and removes its own in /tmp, which
# it can't be told to put elsewhere.
SOCKETS = FS["make_sock"] | FS["remove_file"]
FILE_RIGHTS = FS["execute"] | FS["write_file"] | FS["read_file"] | FS["truncate"] \
    | FS["ioctl_dev"]
READ = FS["execute"] | FS["read_file"] | FS["read_dir"]


def _handled(version):
    rights = sum(FS.values())
    if version < 2:
        rights &= ~FS["refer"]
    if version < 3:
        rights &= ~FS["truncate"]
    if version < 5:
        rights &= ~FS["ioctl_dev"]
    return rights


class _Ruleset(ctypes.Structure):
    _fields_ = [("fs", ctypes.c_uint64), ("net", ctypes.c_uint64), ("scoped", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed", ctypes.c_uint64), ("fd", ctypes.c_int32)]


def landlock_restrict(readable, writable, sockets=(), project=()):
    """Restrict this process, and every program it starts, to reading
    readable and writing writable, with no TCP where the kernel can refuse
    it (version 4 on) and no reaching another process's abstract socket or
    signalling one outside (version 6 on); in sockets, only making a
    socket and removing one (SOCKETS); and project read but not run.
    Nothing written can be run: a writable folder has every right but
    executing, so a program can't write one there, or find one among the
    project's files, and start it (under WSL, a Windows program, which
    would run outside any sandbox). Raises Unavailable on failure.
    Called in the child before the run inside starts (run's preexec_fn)."""
    version = landlock_version()
    if not version:
        raise Unavailable("the kernel has no Landlock")
    libc = ctypes.CDLL(None, use_errno=True)
    handled = _handled(version)
    attr = _Ruleset(handled, 3 if version >= 4 else 0, 3 if version >= 6 else 0)
    size = 24 if version >= 6 else 16 if version >= 4 else 8
    ruleset = libc.syscall(SYS_CREATE_RULESET, ctypes.byref(attr), ctypes.c_size_t(size),
                           ctypes.c_uint32(0))
    if ruleset < 0:
        raise Unavailable(f"Landlock's ruleset: {os.strerror(ctypes.get_errno())}")
    try:
        for paths, rights in ((readable, READ), (writable, handled & ~FS["execute"]),
                              (sockets, SOCKETS), (project, READ & ~FS["execute"])):
            for path in paths:
                try:
                    fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                except OSError:
                    continue
                try:
                    allowed = rights & handled
                    if not os.path.isdir(path):
                        allowed &= FILE_RIGHTS
                    rule = _PathBeneath(allowed, fd)
                    if libc.syscall(SYS_ADD_RULE, ruleset, RULE_PATH_BENEATH,
                                    ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
                        raise Unavailable(f"Landlock's rule for {path}: "
                                          f"{os.strerror(ctypes.get_errno())}")
                finally:
                    os.close(fd)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise Unavailable("no_new_privs couldn't be set")
        if libc.syscall(SYS_RESTRICT_SELF, ruleset, ctypes.c_uint32(0)) < 0:
            raise Unavailable(f"Landlock's restriction: {os.strerror(ctypes.get_errno())}")
    finally:
        os.close(ruleset)


def landlock_paths(base, paths):
    """(readable, writable, project) for Landlock: the system's, /etc's,
    and the shown paths read-only; output/ and the devices a program
    writes to writable; and the project, read-only, whose files, like
    what's written, can't be run (landlock_restrict)."""
    root = os.path.realpath(projectpaths.of(base).top())
    readable = ["/usr", "/proc"] + [os.path.join(os.sep, n) for n in TOP_SYSTEM] \
        + etc_shown() + ["/etc/passwd", "/etc/group", "/etc/hosts", "/dev/urandom",
                         "/dev/random"] + [p for p in VAR_READ if os.path.exists(p)] \
        + list(paths)
    writable = [os.path.realpath(projectpaths.of(base).run_output()), "/dev/null", "/dev/zero", "/dev/full",
                "/dev/shm", "/dev/tty"]
    return readable, writable, [root]


# What of /var a program reads under Landlock: Debian's LibreOffice keeps
# its shared extensions' cache there, by a link from /usr/lib/libreoffice,
# and stops when it's refused (bubblewrap shows no /var, and LibreOffice
# goes on without what isn't there).
VAR_READ = ("/var/spool/libreoffice",)
# Where LibreOffice makes the socket by which a second LibreOffice finds
# the first, a name it can't be given another place for.
LIBREOFFICE_SOCKETS = ("/tmp",)


# -- running inside -----------------------------------------------------------

def run(kind, command, base, environment_inside, paths, sockets=()):
    """Run command, a list, in base inside the sandbox kind, and wait:
    its exit code. It runs in a session of its own (bubblewrap's
    --new-session, and Landlock's start_new_session), so a book's program
    can't type into the terminal (TIOCSTI) and the keyboard's Ctrl-C
    doesn't reach it: a run stopped while it waits stops what it started
    (stop), and is stopped itself. sockets: folders where, under Landlock,
    a program may make and remove a socket and nothing else
    (LIBREOFFICE_SOCKETS, for a run that saves a deck through LibreOffice);
    bubblewrap's /tmp is its own already."""
    root = os.path.realpath(projectpaths.of(base).top())
    os.makedirs(environment_inside["TEXMFVAR"], exist_ok=True)
    os.makedirs(environment_inside["XDG_CACHE_HOME"], exist_ok=True)
    if kind == "bwrap":
        process = subprocess.Popen(bwrap_command(base, command, paths), env=environment_inside)
    else:
        readable, writable, project = landlock_paths(base, paths)
        process = subprocess.Popen(command, cwd=root, env=environment_inside,
                                   start_new_session=True,
                                   preexec_fn=lambda: landlock_restrict(readable, writable,
                                                                        sockets, project))
    try:
        return process.wait()
    except KeyboardInterrupt:
        stop(process, kind)
        raise


def stop(process, kind, grace=30):
    """Tell what the sandboxed run started to end (SIGTERM to each of its
    processes but bubblewrap's own, the run inside then ending what it
    started, as a run told alone to end does), wait for it up to grace
    seconds, and then kill it, bubblewrap taking every process in its
    namespace with it."""
    for pid in _descendants(process.pid):
        try:
            with open(f"/proc/{pid}/comm", encoding="utf-8") as fh:
                if fh.read().strip() == "bwrap":
                    continue
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if kind != "bwrap":
        # Landlock's child is the run itself.
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _descendants(root):
    """The processes started from root, at any depth, by /proc."""
    children = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return []
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", encoding="utf-8", errors="replace") as fh:
                parent = int(fh.read().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        children.setdefault(parent, []).append(int(name))
    out, todo = [], [root]
    while todo:
        for child in children.get(todo.pop(), []):
            out.append(child)
            todo.append(child)
    return out
