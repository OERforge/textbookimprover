#!/usr/bin/env python3
"""
fetch-isbn-ranges.py -- fetch the International ISBN Agency's range
message, which says where an ISBN's hyphens go, into the cache convert.py
checks a hyphenated ISBN's setting against.

    python3 util/fetch-isbn-ranges.py
    python3 util/fetch-isbn-ranges.py --output RangeMessage.xml

convert.py fetches the message itself where a setting writes an ISBN with
hyphens and the cache has none, so this is for fetching it beforehand: on
a machine with the network, for one without it, or to have the newest.
It's kept in ~/.cache/textbookimprover/isbn/RangeMessage.xml (under
XDG_CACHE_HOME where that's set) unless --output names another file; on
another machine, put it there, or set TEXTBOOKIMPROVER_ISBN_RANGES to its
path. What's there is replaced only by a message that reads as one, and
the run says the message's date. The message isn't the project's to
republish, so it isn't kept with TextbookImprover.

Needs the network, and nothing but Python.

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
import isbnranges  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Fetch the International ISBN Agency's range message into the cache "
                    "convert.py checks a hyphenated ISBN against.")
    parser.add_argument("--output", metavar="FILE",
                        help="where to keep it (default: " + isbnranges.default_path() + ")")
    args = parser.parse_args()
    path = os.path.abspath(args.output or isbnranges.default_path())
    try:
        ranges = isbnranges.fetch(path)
    except isbnranges.FETCH_ERRORS as exc:
        sys.exit(f"The range message couldn't be fetched from {isbnranges.URL}: "
                 f"{isbnranges.reason(exc)}. Nothing was changed.")
    print(f"Kept the International ISBN Agency's range message"
          f"{' of ' + ranges.date if ranges.date else ''} in {path}: "
          f"{len(ranges.registrants)} registration groups.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
