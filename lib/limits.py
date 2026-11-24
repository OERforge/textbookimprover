"""
limits.py -- how much of the machine a run's programs may use.

A run's programs are given limits the person running it sets on the
command line (convert.py's --max-memory, --max-time, and --jobs), never a
project's settings, since a hostile project would raise its own. They're
a net under a runaway or hostile file, set well above what a real book
needs: a whole book's LuaLaTeX run took up to 3.2 GB (notes/LATEX-NOTES.md),
and a 15 MB Markdown page of one word repeated made Pandoc 3.14 use 2.1 GB.
Limits change no output, so a target's stamp doesn't count them.

The defaults scale with the memory Linux reports: MemTotal, or the
cgroup's memory.max where that's lower (under WSL2, the virtual machine's
memory, which .wslconfig's memory= sets).

- Each program may use three quarters of it (--max-memory).
- LaTeX builds side by side: as many as fit at 4 GB each in that three
  quarters, at least one, at most the processors and four; Pandoc
  conversions side by side: as many as fit at 2 GB each, on the same terms
  (--jobs sets both).
- Each program may use two hours of processor time (--max-time, 0 for
  none).

They're applied to the run itself, so every program it starts, inside the
sandbox or not, inherits them: RLIMIT_DATA for memory, which counts what a
program writes and not the address space it reserves (GHC's runtime, the
JVM, and Chromium's V8 reserve far more than they use, and RLIMIT_AS would
stop them on the reservation), and RLIMIT_CPU for time, which stops a loop
such as TeX's \\def\\a{\\a}\\a, the case a time limit is for. Pandoc is also
given its heap's limit (GHCRTS=-M), so it stops with its own message, and
a validator's JVM a heap of half the limit (-Xmx). Measured with Pandoc
3.14 on that page under 300 MB and 1 GB, and LuaLaTeX (TeX Live 2026) growing a Lua
table under 500 MB: each stopped in under 5 s, Pandoc saying "Heap
exhausted" under GHCRTS and "Unable to commit" under RLIMIT_DATA, LuaLaTeX
"not enough memory".

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

import os
import re
import signal

GB = 1 << 30
# What one LaTeX build and one Pandoc conversion are given room for, side
# by side, and the most of either at once.
LATEX_ROOM = 4 * GB
PANDOC_ROOM = 2 * GB
MOST_AT_ONCE = 4
# Below this, a whole book's PDF may not build.
ENOUGH = 4 * GB
DEFAULT_SECONDS = 2 * 3600
# Seconds past the processor-time limit before the kernel kills a program
# that ignores the signal it's sent first (SIGXCPU).
GRACE = 60

UNITS = {"": 1, "b": 1, "k": 1 << 10, "kb": 1 << 10, "m": 1 << 20, "mb": 1 << 20,
         "g": GB, "gb": GB, "t": 1 << 40, "tb": 1 << 40}
TIME_UNITS = {"": 1, "s": 1, "m": 60, "min": 60, "h": 3600}


def parse_size(text):
    """Bytes for a size as given (6G, 6000M, 6.5GB, 0 for none), or None
    for none; ValueError for one that isn't a size."""
    found = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", str(text))
    if not found or found.group(2).lower() not in UNITS:
        raise ValueError(f"{text} isn't a size (6G, 6000M)")
    value = int(float(found.group(1)) * UNITS[found.group(2).lower()])
    return value or None


def parse_time(text):
    """Seconds for a time as given (7200, 90m, 2h, 0 for none), or None for
    none; ValueError for one that isn't a time."""
    found = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", str(text))
    if not found or found.group(2).lower() not in TIME_UNITS:
        raise ValueError(f"{text} isn't a time (7200, 90m, 2h)")
    value = int(float(found.group(1)) * TIME_UNITS[found.group(2).lower()])
    return value or None


def shown(size):
    """A size in words: 5.9 GB, 750 MB."""
    if size >= GB:
        return f"{size / GB:.1f} GB"
    return f"{size / (1 << 20):.0f} MB"


def machine_memory():
    """The memory a run has, in bytes: MemTotal, or its cgroup's limit where
    that's lower (version 2's memory.max, version 1's limit_in_bytes);
    None where Linux doesn't say."""
    total = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
                    break
    except (OSError, ValueError, IndexError):
        pass
    for limit in _cgroup_limits():
        if limit and (total is None or limit < total):
            total = limit
    return total


def _cgroup_limits():
    """The memory limits of this process's cgroups, in bytes."""
    found = []
    try:
        with open("/proc/self/cgroup", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return found
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        hierarchy, controllers, path = parts
        if hierarchy == "0":
            candidates = [os.path.join("/sys/fs/cgroup", path.lstrip("/"), "memory.max")]
        elif "memory" in controllers.split(","):
            candidates = [os.path.join("/sys/fs/cgroup/memory", path.lstrip("/"),
                                       "memory.limit_in_bytes")]
        else:
            continue
        for candidate in candidates:
            try:
                with open(candidate, encoding="utf-8") as fh:
                    value = fh.read().strip()
            except OSError:
                continue
            if value.isdigit() and int(value) < (1 << 60):
                found.append(int(value))
    return found


class Limits:
    """A run's limits: memory, what each program may use, in bytes (None
    for none); seconds, its processor time (None for none); jobs, how many
    of a kind run side by side, as --jobs gives it (None to work out);
    machine, the memory the run has (None where Linux doesn't say)."""

    def __init__(self, memory=None, seconds=DEFAULT_SECONDS, jobs=None, machine=None,
                 cpus=None):
        self.machine = machine
        self.memory = memory
        self.seconds = seconds
        self.jobs = jobs
        self.cpus = cpus or os.cpu_count() or 1

    @classmethod
    def given(cls, max_memory=None, max_time=None, jobs=None):
        """The limits from the command line's values, each None where it
        wasn't given; ValueError for one that doesn't read."""
        machine = machine_memory()
        if max_memory is None:
            memory = machine * 3 // 4 if machine else None
        else:
            memory = parse_size(max_memory)
        seconds = DEFAULT_SECONDS if max_time is None else parse_time(max_time)
        if jobs is not None and jobs < 1:
            raise ValueError(f"--jobs {jobs}: give one or more")
        return cls(memory, seconds, jobs, machine)

    def side_by_side(self, room, items):
        """How many of items run at once, each given room bytes."""
        if self.jobs:
            count = self.jobs
        elif self.machine:
            count = max(1, min(self.machine * 3 // 4 // room, self.cpus, MOST_AT_ONCE))
        else:
            count = max(1, min(self.cpus, MOST_AT_ONCE))
        return max(1, min(count, items or 1))

    def latex_jobs(self, items):
        """How many LaTeX builds run at once, of items."""
        return self.side_by_side(LATEX_ROOM, items)

    def pandoc_jobs(self, items):
        """How many Pandoc conversions run at once, of items."""
        return self.side_by_side(PANDOC_ROOM, items)

    def apply(self, environ=None):
        """Give this process, and so every program it starts, the limits;
        and Pandoc, through environ (os.environ), its heap's."""
        import resource
        environ = os.environ if environ is None else environ
        if self.memory:
            _lower(resource, resource.RLIMIT_DATA, self.memory, self.memory)
            # Pandoc's heap two thirds of it, so that it stops with its own
            # word, "Heap exhausted" (exit 251): at nine tenths, a 15 MB page
            # under 1 GB reached the limit first, "Unable to commit".
            heap = max(64 << 20, self.memory * 2 // 3) >> 20
            kept = re.sub(r"(^|\s)-M\S*", " ", environ.get("GHCRTS", "")).strip()
            environ["GHCRTS"] = (kept + " " if kept else "") + f"-M{heap}m"
        if self.seconds:
            _lower(resource, resource.RLIMIT_CPU, self.seconds, self.seconds + GRACE)


    def warnings(self):
        """What a run says of its limits before it starts."""
        said = []
        if self.machine and self.machine < ENOUGH:
            said.append(f"WARNING: this run has {shown(self.machine)} of memory (MemTotal, or "
                        "its cgroup's limit), and a whole book's PDF can take 3.2 GB in one "
                        "LuaLaTeX run, so a long book's PDF may not build. Under WSL, "
                        ".wslconfig's memory= gives the machine more.")
        if self.memory and self.machine and self.memory > self.machine:
            said.append(f"WARNING: --max-memory {shown(self.memory)} is more than the "
                        f"{shown(self.machine)} this run has, so it limits nothing.")
        return said

    def why(self, code, program=""):
        """Why a program that ended with code stopped, where a limit says:
        a sentence, or ""."""
        if self.memory and code == 251 and os.path.basename(program).startswith("pandoc"):
            return (f" It ran out of the memory a program may use ({shown(self.memory)}, "
                    "--max-memory).")
        if self.seconds and code in (-signal.SIGXCPU, -signal.SIGKILL,
                                     128 + signal.SIGXCPU, 128 + signal.SIGKILL):
            return (f" It may have used more than its {self.seconds // 60} minute(s) of "
                    "processor time (--max-time), or been killed.")
        return ""


def java_options():
    """A JVM's options under the memory limit this process was given (a
    validator started by the output check, itself started by a run): a
    heap of half of it, so the JVM stops with its own OutOfMemoryError,
    and nothing where there's none."""
    try:
        import resource
        soft, _hard = resource.getrlimit(resource.RLIMIT_DATA)
    except (ImportError, OSError, ValueError):
        return []
    if soft == resource.RLIM_INFINITY or soft <= 0:
        return []
    return [f"-Xmx{max(256, (soft // 2) >> 20)}m"]


def _lower(resource, which, soft, hard):
    """Set a limit no higher than it is."""
    now_soft, now_hard = resource.getrlimit(which)

    def lowest(value, now):
        return value if now == resource.RLIM_INFINITY else min(value, now)
    hard = lowest(hard, now_hard)
    resource.setrlimit(which, (min(lowest(soft, now_soft), hard), hard))
