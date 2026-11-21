# A project's folders

A project is one folder: the settings at its top, what you write in `src/` and `sidecars/`, and everything a run writes in `output/`. This page says what goes where, what a run does to each folder, and how to bring a book kept the earlier way into it.

```
my-book/
  project.yaml            the book's name, title, contents, and parts
  conversion.yaml         targets and conversion settings (optional)
  packaging.yaml          packages (optional)
  cover.png  book.css     files a setting names
  src/
    book/                 a part's sources: Word, Markdown, HTML, LaTeX, pictures
      _pt/                pages finished by hand, copied through as they are
    slides/               another part, if the project has one
  sidecars/
    book/                 the part's sidecars, under their standard names
  upstream/               a publisher's file or folder a part is unpacked from
  originals/              reserved
  output/                 everything a run writes; safe to delete
    html/  epub/  pdf/    one folder for each target
    packages/cartridge/   one folder for each package
    reports/book/         the part's reports, drafts, and samples
    work/                 a run's own files
```

## What you keep

**The settings** are at the top: [`project.yaml`](project-settings.md), [`conversion.yaml`](conversion-settings.md), and [`packaging.yaml`](packaging-settings.md), each optional but the first, which names the book. [Configuration](configuration.md) says how they fit together.

**A file a setting names** (a cover, a stylesheet, a template, a reference document, `latex-conversion-macros.tex`, a `pdf.metadata` file) is at the top too, or in a folder of your own there, and the setting gives its path from the top. A run stops at a setting whose path is a full path, leads out of the project, begins with a dot, or leads into `output/`, `sidecars/`, `upstream/`, `originals/`, or another part's sources. A path into the sources of the part being built is allowed (`pdf.metadata: src/book/_preamble.md`). A header's or footer's text that isn't such a file is text.

**A part's sources** are in `src/<part>/`, with the pictures and other files they name, at the paths the sources give. Nothing else belongs in `src/`: a file at its top, beside the parts' folders, makes the folder a book kept the earlier way. A page finished by hand goes in the part's `_pt/` ([HTML sources](html.md)).

**A part's sidecars** are in `sidecars/<part>/`, each under its standard name (`image-alt.csv`, `table-headers.csv`, and the rest: [Sidecars and reports](sidecars.md)). The `sidecars:` and `reports:` settings name nothing here, and a run stops at either.

**`upstream/`** holds a file or folder as a publisher sent it: a cartridge, an EPUB, a WARC, a CNXML repository. A part whose `from` names one is unpacked from it ([Unpacking](#unpacking-a-part-from-upstream)).

**`originals/`** is a name kept for files a tool takes out of the sources. Nothing writes there yet.

## Parts

A part is a book, a set of decks, or another collection with sources of its own. A project with one folder under `src/` has one part, a book or slides as `project.kind` or its files say, and needs to say nothing more. A project with more than one names them in `project.yaml`, and a run stops, with the lines to add, when it doesn't:

```yaml
project:
  parts:
    book:
      kind: book
    slides:
      kind: slides
```

Each target is made from one part: the one its `part:` names in `conversion.yaml`, or the part called `book`. A run builds every part that has a target, one after another, and `--part NAME` builds one.

`project.contents` and `project.numbering` are the book's. A part may give its own `identifier`, `title`, `contents`, and `numbering` in its block, which a run of that part uses in the project's place: a student's and an instructor's version kept as two book parts are then two courses to an LMS. A second book part with no identifier of its own gets a warning.

## What a run writes

Everything a run writes is under `output/`, and nothing there is yours to edit: delete the folder and the next run makes it again. (What you decided is in `sidecars/`, never there.)

- **`output/<target>/`**: a target's files, in a folder of the target's name.
- **`output/packages/<package>/`**: a package's files, `cartridge` when `packaging.yaml` names none.
- **`output/reports/<part>/`**: the part's reports (`*-missing.csv`, `output-check.csv`), a sidecar's draft (`*-new.csv`), and the samples.
- **`output/work/`**: the run's own: each page as Pandoc read it, a target's filtered pages, temporary files, a build in progress, the lock.

**A sample or a draft is moved, not renamed.** A message that writes one gives the path to move it to: `project-sample.yaml` to `project.yaml` at the top, `table-headers-sample.csv` to `sidecars/<part>/table-headers.csv`. Left in `output/reports/`, it's read by nothing.

**A target is built beside its folder and swapped in whole.** A run builds each target under `output/work/`, and puts the finished folder in the earlier one's place when that target's build is done. So a build that fails, or a run you stop, leaves each target's folder either as it was or new, never half-written. A target built before the one that failed has its new folder. The next run clears what a stopped one left, and says so if it had to put a folder back.

**One run at a time.** A run holds a lock while it goes, and a second run started in the same project stops. (There's none on Windows itself, and none for `build-epub.py`, `build-pdf.py`, or `build-cartridge.py` run by hand.)

**An `output/` a run didn't make is left alone.** A run marks the `output/` it makes (`output/.textbookimprover`), and stops at one that holds files and has no mark, since it would otherwise delete folders there.

## Where a run is started

Start `convert.py` in the project's folder, or name the folder with `-d`:

```bash
python3 $T/bin/convert.py -d ~/books/my-book
```

Started inside `src/` or `output/`, a run stops and names the project. A run also refuses a project's folder that is the file system's root, your home folder or a folder holding it, a Windows drive, a folder holding TextbookImprover or the TeX installation, a folder inside another project, or one whose path has a colon in it. It stops, too, when `src/`, `sidecars/`, `output/`, `output/work/`, `upstream/`, `originals/`, or a part's folder is a link.

## Unpacking a part from upstream

The unpackers (`unpack-cartridge.py`, `unpack-cnx.py`, `unpack-epub.py`, `unpack-jekyll.py`, `unpack-site.py`) write a part of a project when given `--part`:

```bash
python3 $T/bin/unpack-epub.py ~/Downloads/book.epub -o ~/books/my-book --part book
```

The sources go to `src/book/`, a drafted sidecar to `sidecars/book/`, and the report to `output/reports/book/`. A file or folder from outside the project is copied into `upstream/` (a folder without its `.git/`, links, or anything that is neither file nor folder), and named in `project.yaml` as the part's `from`. The part's folder has to be missing or empty, and a `project.yaml` already there is never edited: the lines to add are printed.

A run unpacks for you when a part's `from` names a file and `src/<part>/` holds nothing, so a project can be its settings and `upstream/` alone:

```yaml
project:
  parts:
    book:
      kind: book
      from: upstream/book.epub
```

Each later run compares `src/<part>/` with what was unpacked and says how many files were added, changed, and removed; `convert.py --src-status` lists them and ends. `from` with an address to fetch isn't built yet, and stops the run.

`adopt-pages.py --part NAME` writes a target's pages as a part the same way ([Adopting the pages as sources](splitting.md#adopting-the-pages-as-sources)).

## Moving a book kept in one folder

Until the next release, a folder with its sources beside its settings, and each target's folder beside them, still builds as it did. `util/move-to-src.py` moves such a book into the folders above:

```bash
cd /path/to/book
python3 $T/util/move-to-src.py --dry-run     # says what it would do
python3 $T/util/move-to-src.py
```

- **A folder of one kind** goes whole to `src/book/`, or to `src/slides/` for decks alone.
- **A folder holding a book and its decks** is split: a PowerPoint or Impress file is a deck, a Word file the book's, a Markdown or LaTeX file the book's when `contents` names it, and a deck written in Markdown is matched by `--slides 'lecture-*.md'`. If a source is left unplaced, nothing is moved and the unplaced ones are listed. A file both parts' sources name is copied into each.
- **Sidecars** go to `sidecars/<part>/` under their standard names, the `sidecars:` and `reports:` settings taken out.
- **A file a setting names** stays at the top. One that is also a page of the book goes with the book, and the setting is rewritten to say `src/book/…`.

Delete the earlier targets' folders and reports yourself once the first build in the new place looks right: the utility lists what it leaves, and nothing reads the top of a project for them afterward.
