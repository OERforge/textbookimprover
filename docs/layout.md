# A project's folders

A project is one folder: the settings at its top, what you write in `src/` and `sidecars/`, and everything a run writes in `output/`. This page says what goes where, what a run does to each folder, and how to bring a book kept the way earlier versions kept it into it.

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

**A part's sources** are in `src/<part>/`, with the pictures and other files they name, at the paths the sources give. Nothing else belongs in `src/`: a file at its top, beside the parts' folders, stops a run, since a folder with one isn't a project. A page finished by hand goes in the part's `_pt/` ([HTML sources](html.md)).

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

**A target is built again only when what it's built from has changed.** A run records each target's stamp when it's built: a digest of five things, by their content and not by when a file was saved.

- **Its settings,** as they resolve for it, but for the sections of another format's (`html.*` for an EPUB). So a change to one target's settings rebuilds that target, `html.css` rebuilds the pages and a deck's page and not the EPUB or the PDF, a default every target reads rebuilds them all, and a comment rebuilds nothing. `SOURCE_DATE_EPOCH` counts, and so do `OER_PDF_VIA` and `OER_MEASURES` for a PDF and `REVEALJS_DIR` for a presentation, when they're set.
- **Its part's sources:** every file under `src/<part>/` but backups (`name~`, `#name#`), Windows' own files, and dot files, which aren't read ([What a part reads](#what-a-part-reads)), but a LaTeX book's `.latexmkrc` with `--latexmkrc`.
- **Its sidecars and the files its settings name:** `sidecars/<part>/`, and a stylesheet, template, reference document, header or footer, or `latex.macros` file. Nothing else at the top counts, so notes or a `.git/` there rebuild nothing, and neither does another part's sidecar.
- **The software:** TextbookImprover itself, Pandoc, and the programs and Python packages that write the target, by version; for a PDF, and every target of a LaTeX book, TeX Live as well.
- **The options that change it:** `--latexmkrc` for a LaTeX book's own PDF; a package's are below.

A run says which targets are up to date, and for each one it builds, what changed ("html: built, since its part's sources changed."). A part with a target to build is read for all its targets, so its reports cover every one, and only the targets that changed are built (a PowerPoint deck's copies are made whenever the part's other targets are, being made as the decks are read). A part whose targets are all up to date isn't read, so its reports aren't written again, but for the output check's when it's asked for with other options (`--wcag` after a run without): its targets' folders are checked as they are. The stamps are in `output/work/stamps/`, recorded once a part's run ends well, so a target whose build failed, and any the run built before it failed, are built again next time. A project copied or checked out elsewhere has the same stamps, and builds nothing.

**A package likewise.** Its stamp is its packaging settings, the stamp of the `html` target it's made from, and the packager's options that change it: `--zip`, `--include-all-html`, `--no-validate`, and `--toc`, by the file's outline (each entry's level and title) rather than its bytes. So a PDF built again with the same bookmarks doesn't make the cartridge again. `build-cartridge.py` run by hand builds the package whatever its stamp, and deletes the stamp, so the next run builds it too.

**`--rebuild`** builds every target and package whatever its stamp, each beside its folder as always, and keeps what's cached under `output/work/` (the pages Pandoc read, rendered drawings). It's for what a stamp can't see: a font installed, or a program the stamp doesn't ask, updated.

**`--clean`** empties `output/` first, its caches too, and then builds everything. It empties only an `output/` a run made, and never through a link: a link in `output/` is deleted, not what it leads to, and a run refuses an `output/` that is a link or holds files without the mark, as it always does.

**One run at a time.** A run holds a lock while it goes, and a second run started in the same project stops. `build-epub.py`, `build-pdf.py`, and `build-cartridge.py` run by hand hold the same lock, so none of them writes while a run goes, and each makes the run's checks of the folder first. (There's no lock on Windows itself.)

**An `output/` a run didn't make is left alone.** A run marks the `output/` it makes (`output/.textbookimprover`), and stops at one that holds files and has no mark, since it would otherwise delete folders there.

## What a part reads

A part reads its own sources, in `src/<part>/`, and what a run extracted or rendered for it, and nothing else: not another part, not `sidecars/` or the top by a page's path, not `output/` or `originals/`, not a dot file or folder (a `.git/` among them), and nothing outside the project. A project is read on other people's machines too, and a page that named `../../.ssh/id_rsa` as a picture would otherwise carry that file into its EPUB.

- **A page naming a file outside its part stops the run,** naming each: a picture, a file a link names, and what raw HTML names in `src`, `href`, `srcset`, `data`, and `poster`, or a stylesheet's `url()`. A full path, `../` out of the part, a link that leads out, and a dot name are all outside. Every page is checked once Pandoc has read it, before any filter, builder, or writer opens what it names, a variant's and a page finished by hand too.
- **A link among a part's sources or sidecars that leads out of them stops the run** before anything is read, naming the link and what it says it leads to. A link inside the part's own folder is the book's own.
- **An AsciiDoc `include::` and a LaTeX book's `\input`, `\include`, picture, and bibliography database** are checked the same way before they're read; an `include::` of a name made from an attribute stops the run too, since it can't be checked before Pandoc reads it.
- **A LaTeX book's `.latexmkrc`** isn't read unless `--latexmkrc` is given, since latexmk runs it as Perl; give it only for a book of your own.
- **A Word file's picture linked to a file outside it,** a relationship the file marks as external, isn't read, and is left out of the page, which the run says, naming each.

No setting or option lets a page read outside its part; copy the file into `src/<part>/` and name it there. A file a setting names is read from the top, as [What you keep](#what-you-keep) says. What a book's own LaTeX can read as it runs is another matter: LuaTeX's Lua can open any file you can, so until TextbookImprover runs LaTeX in a sandbox, don't build a LaTeX book you don't trust.

## Where a run is started

Start `convert.py` in the project's folder, or name the folder with `-d`:

```bash
python3 $T/bin/convert.py -d ~/books/my-book
```

Either way, what the run says names a file of the project's from the project's folder (`Wrote output/reports/book/image-alt-missing.csv`), not by its whole path, and so do the tools it starts and those you run by hand with the project's folder. A command it echoes (`+ pandoc ...`) keeps its whole paths, since it runs in a folder of the run's own.

Started inside `src/` or `output/`, a run stops and names the project. A run also refuses a project's folder that is the file system's root, your home folder or a folder holding it, a Windows drive, a folder holding TextbookImprover or the TeX installation, a folder inside another project, or one whose path has a colon in it. It stops, too, when `src/`, `sidecars/`, `output/`, `output/work/`, `upstream/`, `originals/`, or a part's folder is a link.

## Unpacking a part from upstream

The unpackers (`unpack-cartridge.py`, `unpack-cnx.py`, `unpack-epub.py`, `unpack-jekyll.py`, `unpack-site.py`) write a part of a project, `book` unless `--part` names another:

```bash
python3 $T/bin/unpack-epub.py ~/Downloads/book.epub -o ~/books/my-book
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

`adopt-pages.py` writes a target's pages as a part the same way ([Adopting the pages as sources](splitting.md#adopting-the-pages-as-sources)).

## Moving a book kept in one folder

Versions through 0.10 kept a book in one folder: its sources beside its settings, and each target's folder beside them. A run in such a folder stops, saying it isn't a project, and so does each builder and unpacker. `util/move-to-src.py` moves the book into the folders above:

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
