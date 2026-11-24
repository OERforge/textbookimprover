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
    slides/               a part's decks swapped for their PowerPoint files
  originals/              what a tool changed in the sources, as it was
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

**`upstream/`** holds a file or folder as a publisher sent it: a cartridge, an EPUB, a WARC, a CNXML repository. A part whose `from` names one is unpacked from it ([Unpacking](#unpacking-a-part-from-upstream)). `upstream/<part>/` holds a part's decks in ODP or `.ppt` once `util/swap-in-pptx.py` has made each one's PowerPoint file the deck, with a record of each ([Decks in other formats](slides.md#editing-such-a-deck-in-powerpoint)); a run doesn't read it.

**`originals/<part>/`** keeps what a tool changed in a part's sources, as it was, with a record of each change: `util/import-files.py`'s pages and pictures ([below](#bringing-files-into-a-part)). A run doesn't read it.

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
- **`output/ti-build.yaml`**: the build record, below.

**A sample or a draft is moved, not renamed.** A message that writes one gives the path to move it to: `project-sample.yaml` to `project.yaml` at the top, `table-headers-sample.csv` to `sidecars/<part>/table-headers.csv`. Left in `output/reports/`, it's read by nothing.

**A target is built beside its folder and swapped in whole.** A run builds each target under `output/work/`, and puts the finished folder in the earlier one's place when that target's build is done. So a build that fails, or a run you stop, leaves each target's folder either as it was or new, never half-written. A target built before the one that failed has its new folder. The next run clears what a stopped one left, and says so if it had to put a folder back.

**A target is built again only when what it's built from has changed.** A run records each target's stamp when it's built: a digest of five things, by their content and not by when a file was saved.

- **Its settings,** as they resolve for it, but for the sections of another format's (`html.*` for an EPUB). So a change to one target's settings rebuilds that target, `html.css` rebuilds the pages and a deck's page and not the EPUB or the PDF, a default every target reads rebuilds them all, and a comment rebuilds nothing. `SOURCE_DATE_EPOCH` counts when you set it, and so do `OER_PDF_VIA` and `OER_MEASURES` for a PDF and `REVEALJS_DIR` for a presentation, when they're set. Without it, a run gives every program it starts one moment of its own, its start, as `SOURCE_DATE_EPOCH`, so the EPUB, the Word files, the PDF, and the zips a run writes are dated alike; that moment isn't counted, or every run would build every target again. Under your `SOURCE_DATE_EPOCH` alone, the `latex` target's master names the PDF's ID, as Pandoc's template does, in conditionals that keep Pandoc's LaTeX reader from reading the master back.
- **Its part's sources:** every file under `src/<part>/` but backups (`name~`, `#name#`), Windows' own files, and dot files, which aren't read ([What a part reads](#what-a-part-reads)), but a LaTeX book's `.latexmkrc` with `--latexmkrc`.
- **Its sidecars and the files its settings name:** `sidecars/<part>/`, and a stylesheet, template, reference document, header or footer, or `latex.macros` file. Nothing else at the top counts, so notes or a `.git/` there rebuild nothing, and neither does another part's sidecar.
- **The software:** TextbookImprover itself, Pandoc, and the programs and Python packages that write the target, by version; for a PDF, and every target of a LaTeX book, TeX Live as well.
- **The options that change it:** `--latexmkrc` for a LaTeX book's own PDF; a package's are below.

A run says which targets are up to date, and for each one it builds, what changed ("html: built, since its part's sources changed."). A part with a target to build is read for all its targets, so its reports cover every one, and only the targets that changed are built (a PowerPoint deck's copies are made whenever the part's other targets are, being made as the decks are read). A part whose targets are all up to date isn't read, so its reports aren't written again, but for the output check's when it's asked for with other options (`--wcag` after a run without): its targets' folders are checked as they are. The stamps are in `output/work/stamps/`, recorded once a part's run ends well, so a target whose build failed, and any the run built before it failed, are built again next time. A project copied or checked out elsewhere has the same stamps, and builds nothing.

**A package likewise.** Its stamp is its packaging settings, the stamp of the `html` target it's made from, and the packager's options that change it: `--zip`, `--include-all-html`, `--no-validate`, and `--toc`, by the file's outline (each entry's level and title) rather than its bytes. So a PDF built again with the same bookmarks doesn't make the cartridge again. `build-cartridge.py` run by hand builds the package whatever its stamp, and deletes the stamp, so the next run builds it too.

**`--rebuild`** builds every target and package whatever its stamp, each beside its folder as always, and keeps what's cached under `output/work/` (the pages Pandoc read, rendered drawings). It's for what a stamp can't see: a font installed, or a program the stamp doesn't ask, updated.

**`--clean`** empties `output/` first, its caches too, and then builds everything. It empties only an `output/` a run made, and never through a link: a link in `output/` is deleted, not what it leads to, and a run refuses an `output/` that is a link or holds files without the mark, as it always does.

**The build record, `output/ti-build.yaml`, says how the run made what's there.** A run writes it when it ends, whether it built anything or not, and the next run writes it again; a check-only run (`--check-only`, `--src-status`) leaves it alone. It's for explaining a difference when a book built again doesn't come out the same, and for building it again as it was: the run's moment and where it came from (your `SOURCE_DATE_EPOCH` or the run's start), its exit status and command line; the project's identifier, version, and title; TextbookImprover's version, its commit where it's a checkout and whether that had changes, and its files' digest; Python's version and its packages', and whether html5lib or lxml read the saved web pages; the versions of the programs a target is built with, LaTeX's helpers (`bibtex`, `epstopdf`, `kpsewhich`, `pdfseparate`) among them; whether Pandoc's data folders hold anything (a run reads neither); the platform, and whether it's WSL; the variables that stand for a setting; for each part, which targets it built and which were up to date, the sandbox it ran in, its limits, and the folders `--allow-read` and `--sandbox-read` let it see; every target's and package's stamp; and the SHA-256 of every file under `output/` but `output/work/`. Every value is quoted, so a version is never read as a number. A path inside the project is written from its folder, but the folders `--allow-read` and `--sandbox-read` name are written as you gave them, as the stamps write them, so the record is for your own machine; nothing packs it yet. For each PDF that LaTeX builds (the PDF target, and a LaTeX book's own PDF), it names the LaTeX release; the TeX Live packages holding the files LaTeX read, with their revisions, from TeX Live's own package database (where there's none, as with Debian's and Ubuntu's TeX packages, the files instead), and the files in TeX's tree no package holds, such as luaotfload's cache; each face the PDF embeds, with its package or its file and SHA-256; and every other file LaTeX read outside TeX's tree and the project, by its full path and SHA-256: the system's fonts, fontconfig's settings, a file under `--allow-read`. A PDF up to date keeps what was said of the build that made it. For each package, it says how the pages `contents` doesn't name were placed: with `--include-all-html`, how many joined a chapter, made new chapters, or went under the unsorted group; with `--toc`, the outline's file by its path and SHA-256, how many pages it ordered, how many it doesn't mention, and how many of its entries matched no page; and without either, how many were left out. A package up to date keeps what its build said. It doesn't yet name a deck's PDF's or a drawing's LaTeX, a PDF Pandoc builds itself (`OER_PDF_VIA=pandoc`), or the checkers' versions.

**One run at a time.** A run holds a lock while it goes, and a second run started in the same project stops. `build-epub.py`, `build-pdf.py`, and `build-cartridge.py` run by hand hold the same lock, so none of them writes while a run goes, and each makes the run's checks of the folder first. (There's no lock on Windows itself.)

**An `output/` a run didn't make is left alone.** A run marks the `output/` it makes (`output/.textbookimprover`), and stops at one that holds files and has no mark, since it would otherwise delete folders there.

## What a part reads

A part reads its own sources, in `src/<part>/`, and what a run extracted or rendered for it, and nothing else: not another part, not `sidecars/` or the top by a page's path, not `output/` or `originals/`, not a dot file or folder (a `.git/` among them), and nothing outside the project. A project is read on other people's machines too, and a page that named `../../.ssh/id_rsa` as a picture would otherwise carry that file into its EPUB.

- **A page naming a file outside its part stops the run,** naming each: a picture, a file a link names, and what raw HTML names in `src`, `href`, `srcset`, `data`, and `poster`, or a stylesheet's `url()`. A full path, a `file:` URL, `../` out of the part, a link that leads out, and a dot name are all outside. Every page is checked once Pandoc has read it, before any filter, builder, or writer opens what it names, a variant's and a page finished by hand too.
- **A link among a part's sources or sidecars that leads out of them stops the run** before anything is read, naming the link and what it says it leads to. A link inside the part's own folder is the book's own.
- **An AsciiDoc `include::` and a LaTeX book's `\input`, `\include`, picture, and bibliography database** are checked the same way before they're read; an `include::` of a name made from an attribute stops the run too, since it can't be checked before Pandoc reads it.
- **A LaTeX book's `.latexmkrc`** isn't read unless `--latexmkrc` is given, since latexmk runs it as Perl; give it only for a book of your own.
- **A Word file's picture linked to a file outside it,** a relationship the file marks as external, isn't read, and is left out of the page, which the run says, naming each.
- **A file that isn't what its name says stops the run,** before any program opens it: a picture, a medium, or a source whose first bytes are another kind of file (a web page saved under a picture's name, a PDF or PostScript named `.png`, an archive, a program, or bytes no kind matches), whether a page names it or not, and a Word file's own picture as the run extracts it. The programs that open a file trust its name, and some act on what's inside. A picture of another kind of picture, a PNG named `.jpg`, is a naming slip instead (below). A deck is left to its own reading, which names one that isn't a deck of its kind, saying what it is, and converts the rest.
- **A name that doesn't name its file as every reader would stops the run,** once every source is read: a path with a backslash (`assets\figure.png`), which only Windows resolves; a name in another case than its file's (`assets/Figure.PNG` for `assets/figure.png`), which macOS and Windows find and Pandoc doesn't; and a picture of another kind under its name (a PNG named `.jpg`), which a page and an EPUB declare by its name. Each is named with the source and the path. Changing the source is the fix, which `util/import-files.py` makes ([below](#bringing-files-into-a-part)). Or `media.fix_names: true` under `defaults:` has the run read each as its file, with forward slashes, in its file's case, or copied into `output/work/parts/<part>/` under its own kind's extension, and name its copies so, warning of each; the source is left as it is. It's a book's setting, not a target's, since every target reads the same files.
- **A picture or a medium a page names by URL stops the run** (`https://`, `http://`, `ftp://`, or `//` alone), whether Markdown or raw HTML names it, since a Word, PDF, or PowerPoint target fetches it as it builds, from wherever it names, a server on your own network too, and a page keeps it for each reader's browser to fetch (an EPUB links to it). An `<iframe>`'s page and a style's `url()`, which no target fetches, aren't stopped. A link by URL is a link, and isn't stopped. `util/import-files.py --fetch` saves each into the part ([below](#bringing-files-into-a-part)); `--allow-remote-pictures`, on the command line alone, leaves them as they are for that run, warning, and a target built so is built again by a run without it.

No setting or option lets a page read outside its part; copy the file into `src/<part>/` and name it there. A file a setting names is read from the top, as [What you keep](#what-you-keep) says.

### Bringing files into a part

`util/import-files.py` makes the changes the stops above ask for in a part's Markdown, HTML, and AsciiDoc pages, where each page writes the name, code and comments passed over:

```bash
cd /path/to/project
python3 $T/util/import-files.py --dry-run                   # says what it would do
python3 $T/util/import-files.py --from ../shared --fetch    # --part slides for another part
```

- **A naming slip** is mended in the page: a backslash written as a slash, a name in its file's case, and a picture of another kind renamed to its own kind's extension, each page naming it so.
- **A file outside the part** (a full path, a `file:` URL, `../` out of `src/<part>/`, another part's) is copied into `src/<part>/imported/` when it's in a folder `--from` names, and the page names the copy. It must be a kind of file TextbookImprover knows by its name and is what its name says, and no dot name may lead to it below the folder, so `--from` never takes a key or a settings file; `--from` the root, or a folder that holds your home folder, is refused.
- **A picture named by URL** is fetched with `--fetch` into `src/<part>/remote/`, named by the start of its SHA-256 and its own kind's extension, and the page names the copy; a link by URL is left. A fetch is `http:` or `https:` alone, sends no cookie or password, follows up to five redirects, takes no more than 50 MB, waits no more than a minute for each answer, and must be a picture. An address that isn't on the public internet (this machine, its network, a link-local one) is refused, before it connects and again of the address it connected to; through a proxy, the proxy connects, so only the first check is made. A picture fetched over `http:`, at its own address or at a redirect's, is warned of, since anyone on the way could have answered for the server: its kind is checked, and what it shows can't be.
- **What changes is kept first** in `originals/<part>/`, by its path in the part: each page as it was and each picture renamed. Each change is a row of `originals/<part>/import-record.csv`: the page, the name as it was and as it is, what was done, where a copy came from, and its SHA-256. A sidecar row keyed by a name that changed is named, to be keyed by the new one.

What it can't bring in is named and left, and it exits 1. A LaTeX book's names and a Word file's pictures aren't read.

### The LaTeX a book supplies

LaTeX opens whatever file it's told to, and LuaTeX's Lua whatever file you can. So the LaTeX that comes with a book is checked twice: read before LaTeX runs, and LaTeX's own list of the files it opened read after.

- **Before LaTeX runs,** the run reads the LaTeX the book supplies for the commands that read a file (`\input`, `\include`, `\usepackage`, `\documentclass`, `\includegraphics`, `\bibliography`, `\addbibresource`, `\lstinputlisting`, `\openin`, `\graphicspath`, `\import`, expl3's file functions, and their kin). That LaTeX is a page's raw LaTeX and its front matter (`header-includes`), the file `pdf.metadata` names, the book's own `pdf.template` and the partials beside it, a deck's raw LaTeX, and, for a LaTeX book, its masters, every file they reach, its packages and classes, and the `latex.macros` file. A name written out is found as LaTeX finds it, from the folder LaTeX runs in (for a LaTeX book, its master's), and one outside what the part reads stops the run, naming the file, its line, and the name. A comment, `\verb`, and a verbatim environment are passed over.
- **What it can't follow, it warns of:** a name made by a macro or a template's variable, Lua (`\directlua`, `luacode`), shell escape (`\write18`), and `\openout`.
- **After LaTeX runs,** before a PDF is put in place, the list of every file LaTeX opened (LuaLaTeX's `-recorder`) is checked: a file outside the part, TeX's own trees, the system's fonts and fontconfig's settings, and TextbookImprover's own folder stops the build, naming it, and the last good PDF is kept. It catches `\input`, `\openin`, pictures, and Lua's `io.open`, but not every way Lua has to read a file (`io.lines` and `loadfile` aren't listed), so it's a second check, not a wall. It covers a PDF built from the pages, a LaTeX book's own PDF, its drawings, and a deck's PDF; not a PDF Pandoc builds itself (for a picture named by its web address, or with `OER_PDF_VIA=pandoc`), where the first check alone applies.

**`--allow-read FOLDER`,** given to `convert.py` (or `build-pdf.py`) for one run, and again for each folder, lets both checks accept LaTeX's own files in `FOLDER`: a package, a class, or a bibliography you keep outside the project, or a file a page's raw LaTeX inputs. It never lets in a picture, nor a LaTeX book's `\input` files as the pages' text, which the conversion reads from the part alone, nor a file behind a dot name inside `FOLDER`. Some folders are refused outright, since a book's files don't belong in them: the whole file system; the system's own folders and anything in them (`/bin`, `/boot`, `/dev`, `/etc`, `/lib` and its kin, `/proc`, `/run`, `/sbin`, `/snap`, `/sys`, `/usr`, `/var`), whose TeX trees are read without it (`/usr/share/texlive`, `/usr/local/share/texmf`, `/var/lib/texmf`); `/mnt` and `/media` and a drive's top in them (`/mnt/c`), and a Windows drive's `Windows`, `Program Files`, and `ProgramData`; your home folder and any folder holding it, and `/root`, whoever runs the build; and a folder reached through a dot name (`~/.ssh`, `~/.config`). Name the folder the files are in, `~/shared/macros` or `/mnt/c/Users/you/shared` say: a folder under your home folder or `/root` is taken. Where a book's files really are in one of those folders, `--allow-read-anyway FOLDER` takes it, for that run, and the run warns of the rule it overrides; it still refuses the whole file system, your home folder or one holding it, and `/root`, and a file behind a dot name inside `FOLDER`. It's for your own files on your own machine: a project built with it doesn't hold what it read, so the run warns, and a target whose build runs LaTeX (a PDF, a `latex` target, and every target of a LaTeX book, whose drawings LaTeX sets with the book's preamble) can't be packaged until it's built again without it. A package made from such a target's pages isn't built, the run saying why and going on, and `build-cartridge.py` refuses it. The pages of a book in Markdown or Word, whose build runs no LaTeX, are packaged as ever. To package the rest, put what LaTeX read into the project, or a package or class of yours into your own TeX tree (`TEXMFHOME`), which LaTeX reads without `--allow-read`, and run again without it. The same holds after `--allow-read-anyway`. No setting can give either.

Neither check reaches everything Lua can do: Lua's `io.lines` opens a file without LaTeX's list showing it. What stops that is the sandbox, below.

### The sandbox

`convert.py` converts in a sandbox. Once it has unpacked the part and checked it, it starts itself again inside one and waits, so everything the run starts from there runs inside: Pandoc and its filters, LaTeX and its Lua, LibreOffice, `rsvg-convert`, the checks. What they see:

- **The project, read-only, and `output/`, which they write.** Nothing else of the project's can be changed, so the sidecars are made UTF-8 before the sandbox ([Sidecars](sidecars.md)), and a deck in another format is saved as PowerPoint into `output/work/` ([Slides](slides.md#decks-in-other-formats)).
- **The system's programs and libraries** (`/usr` and its links), what of `/etc` they read (fonts, TeX's and Java's settings, certificates, time zones, and a few more), TeX's trees, the fonts fontconfig knows, Python's folders, the tools a variable names (`VNU_JAR`, `EPUBCHECK_JAR`, `LIBREOFFICE`, and the rest), and TextbookImprover's own, read-only. A folder on the path that's on another drive isn't shown, and leaves the path inside: under WSL, Windows' own folders (`/mnt/c/Windows/System32` and the rest, which WSL puts on the path), and anything under `/mnt` or `/media` or on another machine's drive (a `9p` or `drvfs` mount). Name a tool there with its variable or `--sandbox-read` to have it shown. `/etc/passwd` and `/etc/hosts` are written for the sandbox, with you alone in one and `localhost` alone in the other.
- **An empty home folder in place of yours,** with your fonts and fontconfig's settings in it, read-only, and nothing else. `/tmp` is empty too, and the run's temporary files are in `output/work/tmp/`, TeX's variable tree (`TEXMFVAR`) and caches in `output/work/`.
- **No network,** neither the internet nor a server on your own machine.
- **Only the environment variables the tools read,** such as `PATH`, the locale, and TeX's, Pandoc's, and TextbookImprover's own. A token or a password in another variable isn't there.

Measured with LuaTeX 1.24 (TeX Live 2026) and bubblewrap 0.9: a page's Lua that read a file outside the project with `io.lines` printed its text into the PDF with `--no-sandbox`, and couldn't open it in the sandbox. LuaTeX itself refused to write a file by a full path or delete one (`os.remove`) either way, as TeX Live's default `openout_any = p` and its restricted shell escape have it.

What's inside runs in a session of its own, so a program a book starts can't type into your terminal; a run stopped with Ctrl-C, or told to end, ends what's inside it first.

**bubblewrap is the sandbox** where it works (`sudo apt install bubblewrap`), and the run says so. Where it doesn't, the run uses Landlock, the kernel's own (Linux 5.13 on), and warns that it's weaker: a file outside what it shows can't be opened, but its name and size can be seen; TCP is refused only from Landlock's version 4 (Linux 6.7), and UDP, a DNS lookup among it, not at all; and a connection to a socket file on the machine isn't refused, WSL's own among them, which WSL uses to start Windows programs. So under Landlock nothing a run writes, and nothing among the project's files, can be run, and a folder on another drive isn't shown, which keeps a Windows program from being started from either. A run whose part holds a deck in another format may also make and remove a socket in `/tmp`, and nothing else there, since LibreOffice makes its own there and can't be told another place. Under WSL, install bubblewrap. With neither, the run stops, saying how to install bubblewrap ([Installation](installation.md#requirements)).

Three options change what's shown, each on the command line alone, for one run, and each warned of:

- **`--sandbox-env NAME`** keeps a variable of yours inside, for a tool that needs one the run doesn't keep; give it again for each.
- **`--sandbox-read PATH`** shows a file or a folder inside, read-only, for a program that reads it. It refuses the whole file system, your home folder, and a folder holding it.
- **`--no-sandbox`** converts without one. Give it only for a book you trust, since a book's LaTeX, Lua, and pictures can then make the programs the run starts read any file you can, and fetch from the network.

A folder `--allow-read` or `--allow-read-anyway` takes is shown too. The other scripts don't sandbox themselves yet, so a script other than `convert.py` that builds a book (`build-pdf.py` run by hand, say) is as safe as the book it's given.

### What a run may use

Each program a run starts is held to limits you give on the command line, never in a project's settings, since a book from elsewhere would raise its own. They're a net under a runaway or hostile file, set well above what a real book needs, and they change nothing a run builds, so a target isn't built again for them.

- **`--max-memory SIZE`** (`6G`, `6000M`; `0` for none): the memory each program may use, by default three quarters of the machine's, which is what Linux reports (`MemTotal`, or the limit of the cgroup the run is in, where that's lower). Pandoc is given a heap of two thirds of it, so it stops with its own message (`Heap exhausted`), which the run follows with the limit it ran into, and a validator's Java half.
- **`--max-time TIME`** (`7200`, `90m`, `2h`; `0` for none): the processor time each program may use, by default two hours. It stops a loop such as TeX's `\def\a{\a}\a`, which runs forever without growing, and the run says the program spent its time.
- **`--jobs N`**: how many LaTeX builds (a LaTeX book's parts, a deck's PDFs), or Pandoc conversions (decks), run side by side. By default, as many as fit in three quarters of the memory at 4 GB a LaTeX build and 2 GB a conversion, at least one, and at most the processors and four.

What a real book needs, as measured: a whole book's LuaLaTeX run took up to 3.2 GB, and two at once ran out of a machine of 5.8 GB; a 15 MB Markdown page of one word repeated made Pandoc 3.14 use 2.1 GB. Below 4 GB the run warns that a long book's PDF may not build. Under WSL the memory is the Linux machine's, which WSL makes half of Windows' by default; `memory=` in `.wslconfig` gives it more ([WSL's settings](https://learn.microsoft.com/windows/wsl/wsl-config)).

The memory limit is the kernel's `RLIMIT_DATA`, which counts what a program writes, not the address space it reserves, which Pandoc's runtime, Java, and Chromium reserve far beyond what they use. The time limit is `RLIMIT_CPU`, processor time, not the clock: a program that waits uses none, and none of the programs a run starts waits on anything but the others.

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
