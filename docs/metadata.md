# Metadata: what goes in, what comes out

A book's metadata is what its files say about it apart from its text: its title and its people, its identifiers, its rights, what it's about, and when and how each file was made. This page follows it from each place it comes from to each output a run writes, says what's taken out on the way, and ends with a list of the fields the outputs carry, each with what it's for and what fills it.

It doesn't describe the settings. [Project settings](project-settings.md), [Conversion settings](conversion-settings.md), and [Packaging settings](packaging-settings.md) are the only lists of those, and [Configuration](configuration.md) shows how each is written; this page links to them.

What's here was read back from the outputs of a small book with every project setting filled in, built with Pandoc 3.14 on 2026-11-26: its pages, EPUB, Word files, Markdown, AsciiDoc, and LaTeX targets, its `source` target, its cartridge's manifest, and a deck's PowerPoint file, presentation, and page. A PDF wasn't built for it. What's said of a PDF is read from the LaTeX the `latex` target wrote for the same book, which sets the same keys, and from the convert suite's check of a built PDF's XMP ([Testing](testing.md)).

## Where metadata comes from

Six places, in the order a run meets them:

1. **What an unpacker reads from an upstream file.** A part unpacked from an EPUB, a cartridge, a saved site, or an OpenStax repository gets a `project.yaml` written from what that file says of itself ([below](#what-an-unpacker-reads)). It's yours to edit from then on, and a run reads only your file.
2. **The project's settings**, `project.*` in `project.yaml`: the book's facts, said once for every output ([Configuration](configuration.md#the-books-people) and the four sections after it).
3. **A target's settings** in `conversion.yaml`: an EPUB's cover and accessibility summary (`epub.cover_image`, `epub.cover_alt`, `epub.accessibility_summary`), and a PDF's standards and its metadata file (`pdf.standard`, `pdf.metadata`).
4. **A page's own source**: its title, author, date, keywords, and language, as its file gives them ([below](#a-pages-own-metadata)).
5. **What the run works out**: an EPUB's accessibility claims, from what it found in the book ([What the package document claims](epub.md#what-the-package-document-claims)); the moment of the build; and the program that wrote each file.
6. **What a file carries inside it**: a photograph's camera, position, and owner, a Word file's last editor. None of it is read as the book's metadata, and most of it is taken out of the outputs ([What's taken out](#whats-taken-out)). Windows' mark of a download, a small file beside one saved from a browser, is the same kind of thing kept outside the file: it's never read as the book's and never reaches an output, and a run lists each in `downloaded-sources.csv` ([A file downloaded on Windows](layout.md#a-file-downloaded-on-windows)).

The book's facts reach the outputs that describe a whole book: the EPUB's package document, the PDF, a `latex` target's master file, and the cartridge's manifest. An output that is one file for each page (an `html`, `docx`, `markdown`, or `asciidoc` target, and a deck's files) carries the page's own metadata, and of the book's only its language and its license.

### What an unpacker reads

Each writes what it finds as settings in `project.yaml`, with the book's order as `contents`. Read in the unpackers' code; `unpack-epub.py`'s row was also measured, by unpacking the measured book's own EPUB, and `unpack-cnx.py`'s on *Introduction to Sociology 3e*.

| Unpacker | From | Settings it writes |
|---|---|---|
| `unpack-epub.py` ([An EPUB as the source](epub-input.md)) | The package document's Dublin Core elements | `identifier`, `title`, `language`, `description`, `publisher`, `authors` (every `dc:creator`), and `license`, from the first Creative Commons deed's address in `dc:rights` |
| `unpack-cnx.py` ([OpenStax's CNXML sources](cnx-input.md)) | The collection's file, and the repository's `META-INF/books.xml` | `identifier` (`book-` and the collection's UUID, which OpenStax keeps across a book's versions), `title`, `language` (`en` where the collection names none), and `license` from the deed's address the collection names, a license that isn't Creative Commons' said in `description` instead; and, for an OpenStax book (one `books.xml` gives a style), `publisher` and `authors`, both "OpenStax", which the collection doesn't name |
| `unpack-site.py` ([A saved website](site-input.md)) | The pages, by the site's profile | `identifier` (the site's host and path, where the site names none), `title`, `language`, `authors`, and `description` where the site gives one |
| `unpack-cartridge.py` ([A course cartridge](cartridge-input.md)) | The manifest | `title` and `language` |
| `unpack-jekyll.py` | The site's `_config.yml` | `identifier`, `title`, and `language` |

Three things to check in a `project.yaml` an unpacker wrote, since the upstream file is someone else's:

- **Every creator of an EPUB becomes an author.** The measured book's EPUB named two authors, an adapter, and an editor, each in its role; unpacked again, all four were `authors`. Move the others to `adapters`, `editors`, or `contributors`.
- **The rights are reduced to a license.** The copyright line isn't read, and neither are the identifiers beyond the first, the subjects, the date, or the series. Add them as settings if the book should carry them.
- **The values are the publisher's words.** A title or a description is copied as it stands. Read them before you publish them under your name.

## What each output records

The project's settings, and where each one lands. A dash means the output has no place for it, or the run doesn't write it there. "Title page" is the page an EPUB or a PDF opens with ([Conversion settings](conversion-settings.md), `title_page`).

| Setting (`project.`) | EPUB package document | PDF | Cartridge manifest |
|---|---|---|---|
| `identifier` | `dc:identifier`, the package's unique one | — | the manifest's `identifier` |
| `title` | `dc:title`, typed `main` where there's a subtitle; title page | `dc:title` and the document's Title; title page | `title` |
| `subtitle` | a second `dc:title`, typed `subtitle`; title page | `prism:subtitle`; title page | after the title and a colon |
| `language` | `dc:language`, and each file's `lang` | the document's language | `language` |
| `description` | `dc:description` | — | `description`, with the package's version after it |
| `doi` | `dc:identifier`, ONIX type 06 | `prism:doi` | `identifier`, catalog DOI |
| `isbn.epub` | `dc:identifier`, ONIX type 15, as 13 digits | — | — |
| `isbn.pdf` | — | `dc:identifier`, as `urn:isbn:` | — |
| `series` | `belongs-to-collection`, a series, with `group-position` | — | a relation, `ispartof`, "name, position" |
| `url` | — | `prism:url` | `identifier`, catalog URI |
| `keywords` | a `dc:subject` each | the document's keywords | a `keyword` each |
| `authors` | `dc:creator`, role `aut`, filed under "family, given" where both are given; title page | `dc:creator` each, and the document's Author; title page | a `contribute`, role `author`, each person a vCard |
| `adapters`, `editors` | `dc:creator`, roles `adp` and `edt`; title page | — | a `contribute` each, role `editor` |
| `contributors` | `dc:contributor`, each in its MARC role | — | — |
| `funding` | `dc:contributor`, role `fnd`, the funder's name | — | — |
| `publisher` | `dc:publisher`; title page | `dc:publisher` | a `contribute`, role `publisher`, a vCard with the ROR ID's address |
| `published` | `dc:date`; title page | `dc:date`; title page | the publisher's `date` |
| `copyright`, `license` | `dc:rights`, the copyright line and then the license by name and deed; title page | `dc:rights`, the copyright line; `xmpRights:WebStatement`, the deed's address | `rights`: the same statement as its description, with `cost` and `copyrightAndOtherRestrictions` |
| `licenses` | "Except where otherwise noted" in `dc:rights`; each page's own deed in its file's head | "Except where otherwise noted" and the license in `dc:rights` | "Except where otherwise noted" in the rights' description |
| `coverage` | `dc:coverage`, "place; time" | — | a `coverage` each |
| `education.subjects` | `dc:subject`, the scheme its authority and the code its term | — | a `classification`, purpose `discipline`, described by its scheme |
| `education.level`, `objectives`, `prerequisites` | — | — | a `classification` each: `educational level`, `educational objective`, `prerequisite` |
| `education.context` | — | — | the educational `context` |
| `work_type` | — | `prism:aggregationType`: `book` for a Book, `other` for the rest | — |

In the measured book, a person's affiliation and name's parts reached the cartridge's vCard and nowhere else, but for the EPUB's "family, given". An ORCID iD and a ROR ID reached the vCard and, as links, [a colophon](#a-colophon); neither is in the EPUB's package document or the PDF's XMP.

**Settings that reach no output yet**: `metadata_license`, a subject's `url`, `education.audience`, `resource_type`, `typical_age`, and `time_required`, and a target's `url`. Each is read and checked, and kept for the book's own record ([ROADMAP.md](../ROADMAP.md)). `place`, `contact`, a funder's `award`, and `isbn.paperback` and `isbn.hardcover` are in no file's metadata either, and are read only on a colophon, where a book has one.

### An EPUB

Besides the table's rows, the package document has what the run works out: `dcterms:modified`, the moment of the build ([Dates](#dates)); the schema.org accessibility properties (`accessMode`, `accessModeSufficient`, `accessibilityFeature`, `accessibilityHazard`), claimed from what the run found; and `accessibilitySummary`, which is `epub.accessibility_summary` or, without one, a sentence the run writes from the same findings. A cover is `epub.cover_image`, described by `epub.cover_alt`. Each content document's head has its page's title and a `<link rel="license">` to the deed of each license its pages have. [EPUB](epub.md) has the rest.

### A PDF

A PDF's facts are in two places, which LaTeX fills from the same keys: its XMP packet, and the older document information (Title, Author, Keywords) that a viewer's Properties window shows. The XMP is written only for a tagged PDF, as the default page makes one. Three things differ from an EPUB:

- **Only the authors are named**, each a `dc:creator`, and as the document's Author with a comma between them. A PDF has no place for a role, so adapters, editors, contributors, and funders aren't in it.
- **The rights are split**: the copyright line as `dc:rights`, and the license's deed as `xmpRights:WebStatement`, for a license the run knows a deed for, which is Creative Commons' and CC0. Where some pages have a license of their own, `dc:rights` is the whole statement, as the EPUB's is.
- **A `pdf.metadata` file wins.** A title, subtitle, or author it gives is the PDF's, in its XMP and on its title page, in place of the project's ([The PDF's page](configuration.md#the-pdfs-page)).

`pdf.standard` is the standard the PDF says it meets (PDF/UA-2 by default), written into its XMP as its identification. A LaTeX book's PDF from its own build (`pdf.from: book`) has the title its own files give it ([Required settings](configuration.md#required-settings)).

A `latex` target's master file carries the same facts for whoever builds it: `\title`, `\subtitle`, `\author`, and `\date`, and the XMP's keys in one `\hypersetup`.

### A cartridge's manifest

The manifest's metadata is IEEE LOM, in the profile Common Cartridge 1.1 allows, and it's what a learning management system or a repository shows of the package. The contributors, the funders, and the ISBNs have no place in it. Where every license the book names is Creative Commons' or CC0, `cost` is "no" and `copyrightAndOtherRestrictions` is "yes", or "no" where every one is CC0; with any other license neither is said, and the description alone gives the rights. The description's "(version 1.0)" is the package's own `version` ([Packaging settings](packaging-settings.md)). A page's license isn't in the manifest, which gives a resource no rights of its own; it's in the page.

### A colophon

A book whose `contents` asks for one (`generate: colophon`, [Contents](configuration.md#contents)) gets a page of credits a person reads, in its HTML target, its EPUB, and its PDF. It isn't metadata a program reads, but it's the one place some settings show. On the measured book's page: the title and subtitle; the authors, the adapters, the editors, and the illustrator, each named in a role, a name linked to its ORCID iD; the publisher, linked to its ROR ID, with its place; the series; the copyright line and the license, linked to its deed; each ISBN with its format, the paperback's among them; the DOI as its full address; the book's address; where to report a mistake (`contact`); the funders, one linked to its ROR ID, with its award; the credit a reuser should give; and a last line saying which TextbookImprover and Pandoc made the copy, and on what day, which is the build's ([Dates](#dates)).

## A page's own metadata

A page's title, author, date, keywords, and language are its source's, as Pandoc reads them: a Markdown file's YAML block, a Word file's paragraphs styled Title, Author, and Date, an HTML page's `<title>` and `<meta>` elements, an AsciiDoc file's header, a LaTeX file's `\title` and its kin (of these, a Markdown file and a Word file were measured for this page). A Word file's own properties (`docProps/core.xml`: its title, creator, and keywords as Word's Properties window shows them) aren't read: the measured book's Word source had a title there that no output used, the page taking its heading's.

What each target made of a Markdown page with `title`, `author`, `date`, `keywords`, and `lang` in its YAML block:

| Target | Title | Author | Date | Keywords | Language |
|---|---|---|---|---|---|
| `html` | `<title>` and the page's heading | `<meta name="author">` | `<meta name="dcterms.date">`, and under the title | `<meta name="keywords">` | `lang` on `<html>` |
| `epub3` | the content document's `<title>` and heading | — | — | — | `lang` on `<html>` |
| `docx` | `dc:title` | — (`dc:creator` was empty) | a custom property, `date` | `cp:keywords` | `dc:language` |
| `markdown` | `title` | — | `date` | `keywords` | `lang` |
| `asciidoc` | the `=` line | — | `:revdate:` | `:keywords:` | `:lang:` |
| `source` | the file's own block, as written | as written | as written | as written | as written |

The author's column is `author_byline`'s doing. At its default, `meta`, a page's author is kept as an HTML page's `<meta name="author">` and nowhere else, so the other targets have none. With `author_byline: visible`, the same page's author was also under its title on the HTML page, the `docx` target's `dc:creator`, the `markdown` target's `author`, and the line under the title in the `asciidoc` target's.

Four settings change this table, each described in [Conversion settings](conversion-settings.md): `author_byline`, `title_block` (whether a page's own subtitle and date show on it), `promote_h1_to_title` (which title a page has when its heading says something else), and `title_page`. A page's language is its row in `languages.csv` before its file's own ([A page's language](sidecars.md#a-pages-language)).

Every HTML page also says which Pandoc wrote it (`<meta name="generator">`), and links to its license's deed (`<link rel="license">`): the book's, or its own where `project.licenses` gives it one. Nothing else of the book's is in a page's head: not its title, its authors, or its copyright line. A page that should show those needs a `header` or `footer` ([Header and footer](configuration.md#header-and-footer)).

### A deck

A deck's metadata is its own file's, not the project's ([Decks written in Markdown](slides.md#decks-written-in-markdown)). Measured on a Markdown deck with `title`, `subtitle`, `author` (two names), and `date`, in a project that named another author and a keyword:

- **Its PowerPoint file**: `dc:title` the deck's title and `dc:creator` its authors, a semicolon apart. Its `dc:language` and `cp:keywords` were empty; a slide's text carries its language itself. The project's author and keyword weren't in it.
- **Its reveal.js presentation and its page**: a `<meta name="author">` for each author, `<meta name="dcterms.date">`, and the title as `<title>`. The page links to the license's deed; the presentation measured here didn't.

A PowerPoint deck remediated as a `source` target keeps its own properties, and is given a title where it has none ([The copy](slides.md#the-copy)).

## What's taken out

The run takes a file's private metadata out of everything it writes, at `project.strip_metadata`, and [What a picture's file says about its people](configuration.md#what-a-pictures-file-says-about-its-people) has the whole account: each level, what `keep_metadata` adds, each kind of file, and the report. In short, as measured on a JPEG photograph and a Word file among the book's sources:

| | `private` (the default) | `bare` | `report` |
|---|---|---|---|
| A photograph keeps | its orientation, description, creator, and copyright notice, and its color profile and resolution where it has them | its orientation, and its color profile | everything |
| A photograph loses | its camera's make and model, serial number, owner, software, both dates, and position | those, and its description, creator, and copyright notice | nothing |
| A Word file copied from the sources keeps | its title, subject, creator, keywords, and description | its title, and its language | everything |
| A Word file copied from the sources loses | its last editor, revision count, dates created and modified, template, editing time, and application; and the same from the pictures inside it, its thumbnail among them | those, and its creator, keywords, and description | nothing |

A Word file copied from the sources is a `source` target's copy, or a file a page links to. A Word file a `docx` target writes itself, and a deck's PowerPoint file, keep their created and modified dates, which are the run's moment and no editor's ([Dates](#dates)).

The measured book had no other kind of file, and the rest is as [the configuration page](configuration.md#what-a-pictures-file-says-about-its-people) has it: a PNG, GIF, or WebP picture is stripped as a JPEG is; an OpenDocument file loses its last editor, printer, editing count and time, template, dates, and the program that saved it, its author kept; a PDF copied from the sources keeps its title, subject, keywords, and author, and of its XMP its title, language, rights, and PDF/UA and PDF/A identification; and a PDF the run makes keeps its own.

Each thing taken out is a row of `metadata-stripped.csv` in `output/reports/<part>/`, by target and file; at `report` the rows say what `private` would take.

Two consequences worth knowing:

- **A creator's name is kept at `private`**, in a picture and in an Office file, because an attribution needs it. It's also a person's name. If a file's creator shouldn't be published, use `bare`, or clear the field in the source.
- **The outputs are stripped, not the sources.** A `source` target's copy of an author's Word file loses its editors' traces; the file in `src/` keeps them.

`convert.py --strip-sources` does the same to the part's own files in `src/<part>/`, once, when you ask: at `private` with the project's `keep_metadata`, or with `--strip-sources=bare` at `bare`. It keeps each original in `originals/<part>/` and records each change in `strip-record.csv` there, with the file's SHA-256 before and after. In the measured book it changed the photograph and the Word file, and the outputs built from them afterward were stripped of nothing more. At the project's own level it changes nothing in what a run writes, since the outputs were stripped of the same already; what it changes is what's in the project, for whoever you next give the project to. At another level it does: with `--strip-sources=bare` in a project at `private`, the outputs lose what `bare` took from the sources, a picture's creator and description among it; and in a project at `report` the sources are stripped at `private` all the same. It also gives a deck's sidecar rows, which key a picture by its content, the stripped picture's key, and moves Windows' marks of a download out of the part. It refuses a part unpacked from an upstream file.

What the strip doesn't touch: a file's comments and tracked changes; an Office file's custom properties; a TIFF, which the report names with what it says of its camera; a PDF that's encrypted or signed, which is listed and left; and a page's own YAML block, which a `source` target copies as you wrote it, author and all.

## Dates

Three dates, which are easy to confuse:

- **The day this version was published**, `project.published`, is yours to say. It's the EPUB's `dc:date`, the `dc:date` of the PDF's XMP, the date on both title pages, and the date of the cartridge's publisher.
- **The moment of the build** is the run's own. It's the EPUB's `dcterms:modified`, a Word or PowerPoint file's created and modified dates, the date of each file inside an EPUB or another archive the run writes, and the day a colophon says the copy was made. It's a PDF's creation and modification dates as well, in its XMP and its document information, whatever `project.published` says. Without `project.published`, it's the EPUB's `dc:date` too.
- **The dates inside a source's files**, a photograph's or a Word file's, are an editor's, and are taken out ([above](#whats-taken-out)).

The moment of the build is the run's start, unless the environment variable [`SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/) names one, in seconds: a book built twice with the same value has the same dates both times. Measured with `SOURCE_DATE_EPOCH=1700000000`: the EPUB's `dcterms:modified`, its files' dates, and a Word file's created and modified dates were all 2023-11-14T22:13:20Z.

`output/ti-build.yaml`, the build record, isn't the book's metadata. It says how the run was made (the moment, the command, the programs and their versions, each target's stamp), names the machine's own folders where a run was shown one, and goes into no output ([What a run writes](layout.md#what-a-run-writes)).

## The fields, one by one

For each kind of fact the outputs carry: what it means to the programs that read it, what's good practice, and what fills it. The practice here is what the standards and the registries themselves ask; where it's this page's own advice, it says so.

**Identifier** (`dc:identifier`, the manifest's `identifier`). A name for the book that never changes and that nothing else has. A reading system knows a rebuilt EPUB as the same book by it, and Brightspace matches a re-imported course on it ([Required settings](configuration.md#required-settings)). Keep it across versions; change it only for a different book. A reverse domain name of your own (`edu.example.econ101`) is a common choice, and this page's suggestion. Filled by `project.identifier`, or a part's own.

**DOI and ISBN** (`dc:identifier` with a type, `prism:doi`, `urn:isbn:`). Identifiers someone else registers. A DOI names the work wherever it lives, and [Crossref](https://www.crossref.org/display-guidelines/) asks that it be shown as a full `https://doi.org/` address; the files hold it bare, as the formats want. An ISBN names one format of one edition, so an EPUB and a PDF of the same book have different ones, which is why `isbn` has a key for each. Filled by `project.doi` and `project.isbn`.

**Title and subtitle** (`dc:title`, `prism:subtitle`, the manifest's `title`). The title as a catalog should list it, without the subtitle, which has its own setting; the [EPUB specification](https://www.w3.org/TR/epub-33/#sec-pkg-metadata) types the two apart so a reading system can show either. Don't put an edition or a version in the title. Filled by `project.title` and `subtitle`; for a PDF, by its `pdf.metadata` file first; and by a master file's own title where the project gives none.

**Language** (`dc:language`, `lang`). A [BCP 47](https://www.rfc-editor.org/info/bcp47) tag (`en`, `es`, `fr-CA`). It's what tells a screen reader which voice to read in, so a wrong one is an accessibility fault, not a cataloging one. Give the book's main language, and mark a page or a passage in another ([A page's language](sidecars.md#a-pages-language)). Filled by `project.language`, then a page's row in `languages.csv`, then the page's own file.

**Creator and contributor** (`dc:creator`, `dc:contributor`, the manifest's `contribute`). Who made the book, each in a role. Write a name as its owner writes it, and give `given` and `family` yourself where a catalog should file it, since a program can't split a name safely. An [ORCID iD](https://orcid.org/) tells two people of one name apart, and a [ROR ID](https://ror.org/) does the same for an institution; give them where you have them, though today only the cartridge carries them. Roles are [MARC relators](https://www.loc.gov/marc/relators/relaterm.html). Filled by `project.authors`, `adapters`, `editors`, `contributors`, and `funding`.

**Publisher** (`dc:publisher`). The organization that issues this version, which for an open textbook is often a university or its library and isn't the author. Filled by `project.publisher`.

**Date** (`dc:date`, `dcterms:modified`). `dc:date` is when the book was published, and `dcterms:modified` when the file was last changed; the [EPUB specification](https://www.w3.org/TR/epub-33/#sec-pkg-metadata) requires the second, which lets a reading system tell two builds of one book apart by it. Set `project.published` when you release, as YYYY-MM-DD, so the first doesn't follow the build's clock ([Dates](#dates)).

**Rights** (`dc:rights`, `xmpRights:WebStatement`, `<link rel="license">`, the manifest's `rights`). Who holds the copyright, and what a reader may do. Creative Commons asks for both a notice a person can read and a license a program can ([Marking works](https://wiki.creativecommons.org/wiki/Marking_works)): the statement is the first, and the deed's address the second. Give the license as its [SPDX identifier](https://spdx.org/licenses/), which is what repositories match on. For anything you adapted, give its title, author, source, and license, the four parts of the credit Creative Commons [recommends](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution), with what you changed. Filled by `project.copyright`, `license`, and `licenses`, or a part's own.

**Description** (`dc:description`, the manifest's `description`). A paragraph a catalog shows under the title. Write it for someone deciding whether to open the book: what it covers and who it's for, in plain text, since most systems show no formatting. Filled by `project.description`.

**Subject and keyword** (`dc:subject`, the manifest's `keyword` and `classification`). What the book is about. A keyword is your own word; a subject with a scheme and a code is one a catalog can match across books, which is worth the trouble where a repository asks for a scheme by name. Filled by `project.keywords` and `education.subjects`.

**Coverage** (`dc:coverage`). The place and the time the book is about, not where or when it was published. Leave it out unless the book has one. Filled by `project.coverage`.

**Series** (`belongs-to-collection`, the manifest's relation). The set the book belongs to, with its place in it. Filled by `project.series`.

**Educational facts** (the manifest's `educational` and `classification`). The level, the context, the objectives, and the prerequisites, for the systems that browse by them. Use the words your own institution's catalog uses, since nothing checks them against a list but `context`. Filled by `project.education`.

**Accessibility** (the EPUB's `schema:` properties). What a reader can rely on: which senses the book needs, and which features it has. The run claims only what it found, and [the vocabulary](https://www.w3.org/2021/a11y-discov-vocab/latest/) and [EPUB Accessibility](https://www.w3.org/TR/epub-a11y-11/) say what each claim means. Write `epub.accessibility_summary` yourself where you can, in plain language, and say what's known not to work; the run's own sentence is a fallback. Filled by the run, and by `epub.accessibility_summary`.

**Type of work** (`prism:aggregationType`). What kind of thing this is, for a deposit. Filled by `project.work_type`, or the part's kind.

**Generator** (`<meta name="generator">`, an Office file's application). The program that wrote the file. Pandoc's name stays on the pages it writes; an editor's application is taken out of an Office file at `private`.

**A picture's own fields** (EXIF, IPTC, and XMP inside the file). Its description, creator, and copyright notice travel with it when someone saves it out of the book, which is why `private` keeps them, as the [IPTC](https://iptc.org/standards/photo-metadata/iptc-standard/) asks publishers to. They're no substitute for alt text in the book, which no reading system takes from a picture's file ([Sidecars and reports](sidecars.md)).
