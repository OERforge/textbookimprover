# Metadata: what goes in, what comes out

A book's metadata is the information its files record about the book, as distinct from its text: its title, its contributors, its identifiers, its rights, its subject, and when and how each file was made. This page traces each item of metadata from its source to each output a run writes, states what is removed along the way, and ends with a reference list of the metadata fields the outputs contain, giving each field's meaning, recommended practice, and the settings that populate it.

It doesn't define the settings. [Project settings](project-settings.md), [Conversion settings](conversion-settings.md), and [Packaging settings](packaging-settings.md) are the authoritative lists, and [Configuration](configuration.md) shows how each setting is written; this page links to them.

The statements on this page were verified by inspecting the outputs of a small test book with every project setting given a value, built with Pandoc 3.14 on 2026-11-26: its pages, EPUB, Word files, Markdown, AsciiDoc, and LaTeX targets, its `source` target, its cartridge's manifest, and a deck's PowerPoint file, presentation, and page. No PDF was built for it. The statements about a PDF are taken from the LaTeX that the `latex` target wrote for the same book, which sets the same metadata keys, and from the convert suite's check of a built PDF's XMP ([Testing](testing.md)).

## Where metadata comes from

Metadata has six sources, listed in the order a run encounters them:

1. **What an unpacker reads from an upstream file.** A part unpacked from an EPUB, a cartridge, a saved site, or an OpenStax repository is given a `project.yaml` generated from that file's own metadata ([below](#what-an-unpacker-reads)). After unpacking, `project.yaml` is an ordinary settings file that you edit, and a run reads it alone, never the upstream file's metadata.
2. **The project's settings**, `project.*` in `project.yaml`: the book-level metadata, stated once and applied to every output ([Configuration](configuration.md#the-books-people) and the four sections after it).
3. **A target's settings** in `conversion.yaml`: an EPUB's cover and accessibility summary (`epub.cover_image`, `epub.cover_alt`, `epub.accessibility_summary`), and a PDF's standards and its metadata file (`pdf.standard`, `pdf.metadata`).
4. **A page's own source**: its title, author, date, keywords, and language, as its file gives them ([below](#a-pages-own-metadata)).
5. **Values the run computes**: an EPUB's accessibility claims, derived from what the run found in the book ([What the package document claims](epub.md#what-the-package-document-claims)); the moment of the build; and the program that wrote each file.
6. **Metadata embedded in a source file**: a photograph's camera, position, and owner, or a Word file's last editor. It is never read as the book's metadata, and most of it is removed from the outputs ([What's taken out](#whats-taken-out)). Windows' mark of a download, a small file beside one saved from a browser, is metadata of the same kind stored outside the file: it is never read as the book's and never copied to an output, and a run lists each one in `downloaded-sources.csv` ([A file downloaded on Windows](layout.md#a-file-downloaded-on-windows)).

Book-level metadata is written to the outputs that represent a whole book: the EPUB's package document, the PDF, a `latex` target's master file, and the cartridge's manifest. An output that is one file for each page (an `html`, `docx`, `markdown`, or `asciidoc` target, and a deck's files) contains the page's own metadata and, of the book-level metadata, only the language and the license.

### What an unpacker reads

Each unpacker writes the metadata it finds as settings in `project.yaml`, with the book's page order as `contents`. Read in the unpackers' code; `unpack-epub.py`'s row was also measured, by unpacking the test book's own EPUB, and `unpack-cnx.py`'s on *Introduction to Sociology 3e*.

| Unpacker | From | Settings it writes |
|---|---|---|
| `unpack-epub.py` ([An EPUB as the source](epub-input.md)) | The package document's Dublin Core elements | `identifier`, `title`, `language`, `description`, `publisher`, `authors`, `adapters`, `editors`, `contributors`, and `funding` (each `dc:creator` and `dc:contributor` by its role), and `license`, from the first Creative Commons deed's address in `dc:rights` |
| `unpack-cnx.py` ([OpenStax's CNXML sources](cnx-input.md)) | The collection's file, and the repository's `META-INF/books.xml` | `identifier` (`book-` and the collection's UUID, which OpenStax keeps across a book's versions), `title`, `language` (`en` where the collection names none), and `license` from the deed's address the collection names, a license that isn't Creative Commons' said in `description` instead; and, for an OpenStax book (one `books.xml` gives a style), `publisher` and `authors`, both "OpenStax", which the collection doesn't name |
| `unpack-site.py` ([A saved website](site-input.md)) | The pages, by the site's profile | `identifier` (the site's host and path, where the site names none), `title`, `language`, `authors`, and `description` where the site gives one |
| `unpack-cartridge.py` ([A course cartridge](cartridge-input.md)) | The manifest | `title` and `language` |
| `unpack-jekyll.py` | The site's `_config.yml` | `identifier`, `title`, and `language` |

Review two things in a `project.yaml` that an unpacker generated, because its values come from a file you didn't write:

- **Only the license is taken from the rights statement.** The copyright line isn't read, and neither are the identifiers after the first, the subjects, the date, or the series. Add them as settings if the book's outputs should include them.
- **The values are copied unchanged from the upstream file.** A title or a description is written exactly as the publisher gave it. Check each value before publishing the book.

## What each output records

The table shows where each project setting is written in each book-level output. A dash means that the format has no field for the setting, or that the run doesn't write it to that output. "Title page" is the page an EPUB or a PDF opens with ([Conversion settings](conversion-settings.md), `title_page`).

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

In the test book, a person's affiliation and name's parts were written only to the cartridge's vCard, except that the EPUB's `file-as` value ("family, given") is built from the name's parts. An ORCID iD and a ROR ID were written to the vCard and, as links, to [a colophon](#a-colophon); neither is written to the EPUB's package document or the PDF's XMP.

**Settings not yet written to any output**: `metadata_license`, a subject's `url`, `education.audience`, `resource_type`, `typical_age`, and `time_required`, and a target's `url`. Each is read and validated, and is reserved for the book's own record ([ROADMAP.md](../ROADMAP.md)). `place`, `contact`, a funder's `award`, `isbn.paperback`, and `isbn.hardcover` are not written to any file's metadata either; they appear only on a colophon, in a book that has one.

### An EPUB

In addition to the rows of the table, the package document contains values the run computes: `dcterms:modified`, the moment of the build ([Dates](#dates)); the schema.org accessibility properties (`accessMode`, `accessModeSufficient`, `accessibilityFeature`, `accessibilityHazard`), each asserted only where the run found evidence for it; and `accessibilitySummary`, which is `epub.accessibility_summary` or, where that setting is empty, a sentence the run generates from the same findings. A cover is `epub.cover_image`, described by `epub.cover_alt`. Each content document's head has its page's title and a `<link rel="license">` to the deed of each license its pages have. [EPUB](epub.md) describes the target in full.

### A PDF

A PDF records its metadata in two structures, both of which LaTeX populates from the same keys: the XMP packet, and the older document information dictionary (Title, Author, Keywords), which a viewer displays in its Properties window. The XMP is written only for a tagged PDF, as the default page makes one. A PDF's metadata differs from an EPUB's in three respects:

- **Only the authors are named**, each a `dc:creator`, and as the document's Author with a comma between them. Neither structure has a field for a contributor's role, so adapters, editors, contributors, and funders aren't in it.
- **The rights are recorded in two fields**: the copyright line as `dc:rights`, and the license's deed as `xmpRights:WebStatement`, for a license the run knows a deed for, which is Creative Commons' and CC0. Where some pages have a license of their own, `dc:rights` is the whole statement, as the EPUB's is.
- **A `pdf.metadata` file takes precedence.** A title, subtitle, or author given there is used for the PDF, in its XMP and on its title page, in place of the project's ([The PDF's page](configuration.md#the-pdfs-page)).

`pdf.standard` is the standard the PDF says it meets (PDF/UA-2 by default), written into its XMP as its identification. A LaTeX book's PDF from its own build (`pdf.from: book`) has the title its own files give it ([Required settings](configuration.md#required-settings)).

A `latex` target's master file contains the same metadata, so that a PDF built from it by hand records it too: `\title`, `\subtitle`, `\author`, and `\date`, and the XMP's keys in one `\hypersetup`.

### A cartridge's manifest

The manifest's metadata is IEEE LOM, in the profile Common Cartridge 1.1 allows, and it is what a learning management system or a repository displays about the package. The profile has no field for the contributors, the funders, or the ISBNs, so they are not written. Where every license the book names is Creative Commons' or CC0, `cost` is "no" and `copyrightAndOtherRestrictions` is "yes", or "no" where every one is CC0; with any other license neither is said, and the description alone gives the rights. The description's "(version 1.0)" is the package's own `version` ([Packaging settings](packaging-settings.md)). A page's own license is not written to the manifest, because the profile gives a resource no rights element; it is stated in the page's text.

### A colophon

A book whose `contents` asks for one (`generate: colophon`, [Contents](configuration.md#contents)) is given a page of credits in its HTML target, its EPUB, its PDF, and its Word target, where the colophon is a file of its own; a target whose `colophon` setting is `off` has none. A colophon is text for a reader, not machine-readable metadata, but it is the only output in which some settings appear. The test book's colophon contained: the title and subtitle; the authors, the adapters, the editors, and the illustrator, each named in a role, a name linked to its ORCID iD; the publisher, linked to its ROR ID, with its place; the series; the copyright line and the license, linked to its deed; each ISBN with its format, the paperback's among them, hyphenated where its setting is (the EPUB and the PDF record an ISBN as its 13 digits); the DOI as its full address; the book's address; where to report a mistake (`contact`); the funders, one linked to its ROR ID, with its award; the credit a reuser should give, its title linked to the book's address, or to its DOI where there is no address; and a final line naming the versions of TextbookImprover and Pandoc that produced the copy and the date of the build ([Dates](#dates)).

## A page's own metadata

A page's title, author, date, keywords, and language are taken from its source file, as Pandoc reads them: a Markdown file's YAML block, a Word file's paragraphs styled Title, Author, and Date, an HTML page's `<title>` and `<meta>` elements, an AsciiDoc file's header, or a LaTeX file's `\title`, `\author`, and `\date` commands. Of these, only a Markdown file and a Word file were tested for this page. A Word file's own properties (`docProps/core.xml`: its title, creator, and keywords as Word's Properties window shows them) are not read: the test book's Word source had a title property that appeared in no output, and the page's title was taken from its heading.

The table shows how each target recorded a Markdown page whose YAML block set `title`, `author`, `date`, `keywords`, and `lang`:

| Target | Title | Author | Date | Keywords | Language |
|---|---|---|---|---|---|
| `html` | `<title>` and the page's heading | `<meta name="author">` | `<meta name="dcterms.date">`, and under the title | `<meta name="keywords">` | `lang` on `<html>` |
| `epub3` | the content document's `<title>` and heading | — | — | — | `lang` on `<html>` |
| `docx` | `dc:title` | `dc:creator` | a custom property, `date` | `cp:keywords` | `dc:language` |
| `markdown` | `title` | `author` | `date` | `keywords` | `lang` |
| `asciidoc` | the `=` line | the author line, after the `=` line | the revision line after it, or `:revdate:` where there is no author | `:keywords:` | `:lang:` |
| `source` | the file's own block, as written | as written | as written | as written | as written |

The Author column is determined by the `author_byline` setting. At its default value, `meta`, a page's author is written to each target's metadata, and the targets that Pandoc's templates would display it in do not display it: an HTML page has a `<meta name="author">` element for each author and no byline under its title, and a `docx` target's `dc:creator` holds the authors' names, separated by semicolons, with no paragraph styled Author in the document. A `markdown` target's `author` field and an `asciidoc` target's author line are those formats' own metadata, so a run that reads the file back takes them for the page's author. An AsciiDoc processor such as Asciidoctor displays the author line in the document's header. With `author_byline: visible`, the author is also displayed under the title on the HTML page, and in a paragraph styled Author for each author at the start of the `docx` target's document. With `author_byline: drop`, no target records the author. These results were measured with Pandoc 3.14.

Four settings change the results in this table, each defined in [Conversion settings](conversion-settings.md): `author_byline`, `title_block` (whether a page's own subtitle and date show on it), `promote_h1_to_title` (which title a page has when its heading says something else), and `title_page`. A page's language is taken from its row in `languages.csv` where it has one, and otherwise from its own file ([A page's language](sidecars.md#a-pages-language)).

Every HTML page also records the version of Pandoc that wrote it (`<meta name="generator">`) and links to the deed of its license (`<link rel="license">`): the book's license, or the page's own where `project.licenses` assigns one. No other book-level metadata is written to a page's head: the book's title, authors, and copyright line are absent. To display them on each page, use the `header` or `footer` setting ([Header and footer](configuration.md#header-and-footer)).

### A deck

A deck's outputs record the metadata in the deck's own source file, not the project's settings ([Decks written in Markdown](slides.md#decks-written-in-markdown)). The following was observed for a Markdown deck that set `title`, `subtitle`, `author` (two names), and `date`, in a project whose settings named a different author and a keyword:

- **Its PowerPoint file**: `dc:title` contained the deck's title and `dc:creator` its two authors, separated by a semicolon. `dc:language` and `cp:keywords` were empty; the language is recorded on the text of each slide instead. The project's author and keyword were not written to the file.
- **Its reveal.js presentation and its page**: a `<meta name="author">` for each author, `<meta name="dcterms.date">`, and the title as `<title>`. The page linked to the license's deed; the presentation did not.

A PowerPoint deck remediated as a `source` target retains its existing properties, and is given a title if it has none ([The copy](slides.md#the-copy)).

## What's taken out

A run removes embedded private metadata from every file it writes, at the level set by `project.strip_metadata`. [What a picture's file says about its people](configuration.md#what-a-pictures-file-says-about-its-people) is the full description: each level, what `keep_metadata` adds, each file type, and the report. The table summarizes the result for the two file types in the test book, a JPEG photograph and a Word file:

| | `private` (the default) | `bare` | `report` |
|---|---|---|---|
| A photograph keeps | its orientation, description, creator, and copyright notice, and its color profile and resolution where it has them | its orientation, and its color profile | everything |
| A photograph loses | its camera's make and model, serial number, owner, software, both dates, and position | those, and its description, creator, and copyright notice | nothing |
| A Word file copied from the sources keeps | its title, subject, creator, keywords, and description | its title, and its language | everything |
| A Word file copied from the sources loses | its last editor, revision count, dates created and modified, template, editing time, and application; and the same from the pictures inside it, its thumbnail among them | those, and its creator, keywords, and description | nothing |

"A Word file copied from the sources" means a `source` target's copy, or a file that a page links to. A Word file that a `docx` target generates, and a deck's PowerPoint file, retain their created and modified dates, because those dates are the time of the build and not of anyone's editing ([Dates](#dates)).

The test book contained no other file types. For those, the [configuration page](configuration.md#what-a-pictures-file-says-about-its-people) states the following, which was not tested for this page: a PNG, GIF, or WebP picture is treated as a JPEG is; an OpenDocument file loses its last editor, printer, editing count and time, template, dates, and the program that saved it, and keeps its author; a PDF copied from the sources keeps its title, subject, keywords, and author, and of its XMP its title, language, rights, and PDF/UA and PDF/A identification; and a PDF that the run builds keeps the metadata the run gave it.

Each item removed is recorded as a row of `metadata-stripped.csv` in `output/reports/<part>/`, identified by target and file. At `report`, the rows list what `private` would remove.

Two consequences follow:

- **A creator's name is retained at `private`**, in a picture and in an Office file, because attribution requires it. The name is also personal information. If a file's creator must not be published, use `bare`, or clear the field in the source file.
- **Only the outputs are changed, not the sources.** A `source` target's copy of an author's Word file has its editing history removed; the file in `src/` is unchanged.

`convert.py --strip-sources` applies the same removal to the part's own files in `src/<part>/`, as a one-time operation that runs only when the option is given: at `private` with the project's `keep_metadata`, or with `--strip-sources=bare` at `bare`. It keeps each original in `originals/<part>/` and records each change in `strip-record.csv` there, with the file's SHA-256 before and after. In the test book it changed the photograph and the Word file, and a subsequent build reported nothing further to remove from the outputs. When the option's level is the same as the project's, it doesn't change what a run writes, because the outputs already had the same metadata removed; its effect is on the project folder itself, which matters when the project is shared. When the levels differ, the outputs change too: with `--strip-sources=bare` in a project set to `private`, the outputs no longer contain what `bare` removed from the sources, including a picture's creator and description; and in a project set to `report`, the sources are still stripped at `private`. The option also updates the keys of a deck's sidecar rows, which identify a picture by a hash of its content, to match each stripped picture, and moves Windows' download marks out of the part. It refuses to run on a part unpacked from an upstream file.

The following are never changed: a file's comments and tracked changes; an Office file's custom properties; a TIFF file, which the report lists together with the camera metadata it contains; an encrypted or signed PDF, which the report lists; and a page's own YAML block, which a `source` target copies exactly as written, including its `author`.

## Dates

An output can record three different dates:

- **The day this version was published**, `project.published`, is a setting you supply. It is written as the EPUB's `dc:date`, the `dc:date` of the PDF's XMP, the date on both title pages, and the date of the cartridge's publisher.
- **The time of the build** is determined by the run. It is written as the EPUB's `dcterms:modified`, a Word or PowerPoint file's created and modified dates, the date of each file inside an EPUB or another archive the run writes, and the date in a colophon's final line. It is also a PDF's creation and modification dates, in both its XMP and its document information, regardless of `project.published`. Where `project.published` is not set, it is the EPUB's `dc:date` as well.
- **The dates embedded in a source file**, such as a photograph's or a Word file's, record when someone created or edited that file, and are removed ([above](#whats-taken-out)).

The time of the build is the time the run started, unless the environment variable [`SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/) specifies a time, in seconds since 1970: two builds of a book with the same value record identical dates. Measured with `SOURCE_DATE_EPOCH=1700000000`: the EPUB's `dcterms:modified`, its files' dates, and a Word file's created and modified dates were all 2023-11-14T22:13:20Z.

`output/ti-build.yaml`, the build record, is not metadata of the book. It records how the run was performed (the time, the command, the programs and their versions, and each target's stamp), can name folders on the machine that built the book, and is not included in any output ([What a run writes](layout.md#what-a-run-writes)).

## Field reference

Each entry gives a field's meaning to the software that reads it, the recommended practice, and the settings that populate it. The recommendations are those of the standards and registries cited; where a recommendation is this documentation's own, the entry says so.

**Identifier** (`dc:identifier`, the manifest's `identifier`). A persistent, unique name for the book. A reading system uses it to recognize a rebuilt EPUB as the same book, and Brightspace matches a re-imported course by it ([Required settings](configuration.md#required-settings)). Recommended practice: keep the identifier unchanged across versions, and change it only for a different book. A reverse domain name that you control (`edu.example.econ101`) is a common form; that suggestion is this documentation's own. Populated by `project.identifier`, or by a part's own `identifier`.

**DOI and ISBN** (`dc:identifier` with a type, `prism:doi`, `urn:isbn:`). Identifiers assigned by a registration agency. A DOI identifies the work independently of where it is hosted. [Crossref](https://www.crossref.org/display-guidelines/) asks that a DOI be displayed as a full `https://doi.org/` address; the files record it without that prefix, as their formats specify. An ISBN identifies one format of one edition, so an EPUB and a PDF of the same book have different ISBNs, which is why `isbn` has a key for each format. Populated by `project.doi` and `project.isbn`.

**Title and subtitle** (`dc:title`, `prism:subtitle`, the manifest's `title`). The title as a catalog should list it. Recommended practice: give the subtitle in its own setting, not in the title, since the [EPUB specification](https://www.w3.org/TR/epub-33/#sec-pkg-metadata) distinguishes the two by type so that a reading system can display either; and don't include an edition or a version number in the title. Populated by `project.title` and `project.subtitle`; for a PDF, by its `pdf.metadata` file where that gives a title; and by a master file's own title where the project gives none.

**Language** (`dc:language`, `lang`). A [BCP 47](https://www.rfc-editor.org/info/bcp47) language tag (`en`, `es`, `fr-CA`). A screen reader selects its voice from this value, so an incorrect tag is an accessibility defect and not only a cataloging error. Recommended practice: set the book's main language, and declare the language of any page or passage in a different one ([A page's language](sidecars.md#a-pages-language)). Populated by `project.language`; for a page, by its row in `languages.csv`, and otherwise by the page's own file.

**Creator and contributor** (`dc:creator`, `dc:contributor`, the manifest's `contribute`). The people and organizations responsible for the book, each with a role. Recommended practice: write each name as the person writes it, and supply `given` and `family` explicitly where a catalog should sort by family name, because a name can't be split reliably by software. An [ORCID iD](https://orcid.org/) distinguishes two people with the same name, and a [ROR ID](https://ror.org/) does the same for an institution; supply them where they exist, although at present only the cartridge's manifest and a colophon record them. Roles are [MARC relators](https://www.loc.gov/marc/relators/relaterm.html). Populated by `project.authors`, `adapters`, `editors`, `contributors`, and `funding`.

**Publisher** (`dc:publisher`). The organization that issues this version of the book. For an open textbook this is often a university or its library, and is usually not the author. Populated by `project.publisher`.

**Date** (`dc:date`, `dcterms:modified`). `dc:date` is the date the book was published, and `dcterms:modified` is the time the file was last changed. The [EPUB specification](https://www.w3.org/TR/epub-33/#sec-pkg-metadata) requires `dcterms:modified`, which lets a reading system distinguish two builds of the same book. Recommended practice: set `project.published` for each release, in the form YYYY-MM-DD, so that `dc:date` doesn't change with the time of the build ([Dates](#dates)). Populated by `project.published` and by the time of the build.

**Rights** (`dc:rights`, `xmpRights:WebStatement`, `<link rel="license">`, the manifest's `rights`). The copyright holder, and the terms under which the book may be used. Creative Commons recommends both a notice that a person can read and a license reference that software can read ([Marking works](https://wiki.creativecommons.org/wiki/Marking_works)): the rights statement is the first, and the address of the license's deed is the second. Recommended practice: give the license as its [SPDX identifier](https://spdx.org/licenses/), the form that repositories match; and for adapted material, give the title, author, source, and license of the original, the four elements of attribution that Creative Commons [recommends](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution), together with a statement of the changes. Populated by `project.copyright`, `license`, and `licenses`, or by a part's own.

**Description** (`dc:description`, the manifest's `description`). A summary that a catalog displays with the title. Recommended practice: state what the book covers and its intended audience, in plain text, since most systems don't render formatting. Populated by `project.description`.

**Subject and keyword** (`dc:subject`, the manifest's `keyword` and `classification`). The topics the book covers. A keyword is a term of your own choosing. A subject with a scheme and a code is a term from a controlled vocabulary, which a catalog can match across books; supply one where a repository requires a particular scheme. Populated by `project.keywords` and `education.subjects`.

**Coverage** (`dc:coverage`). The place and the period that the book's content concerns, not the place or date of its publication. Omit it unless the book has a defined geographic or historical scope. Populated by `project.coverage`.

**Series** (`belongs-to-collection`, the manifest's relation). The series the book belongs to, and its position in that series. Populated by `project.series`.

**Educational metadata** (the manifest's `educational` and `classification`). The level, the context, the learning objectives, and the prerequisites, for systems that let users browse by them. Only `context` is validated against a fixed list; for the others, this documentation suggests the terms your institution's own catalog uses. Populated by `project.education`.

**Accessibility** (the EPUB's `schema:` properties). The access modes the book requires and the accessibility features it provides. The run asserts only what it found in the book; [the vocabulary](https://www.w3.org/2021/a11y-discov-vocab/latest/) and [EPUB Accessibility](https://www.w3.org/TR/epub-a11y-11/) define each term. Recommended practice: write `epub.accessibility_summary` yourself, in plain language, and state any known limitations; the generated sentence is a fallback. Populated by the run, and by `epub.accessibility_summary`.

**Type of work** (`prism:aggregationType`). The kind of work, as a repository classifies deposits. Populated by `project.work_type`, or otherwise derived from the part's kind.

**Generator** (`<meta name="generator">`, an Office file's application property). The program that wrote the file. Pages written by Pandoc retain Pandoc's name; the name of an editing application is removed from an Office file at `private`.

**A picture's embedded fields** (EXIF, IPTC, and XMP inside the file). A picture's description, creator, and copyright notice remain in the file when a reader saves it from the book, which is why `private` retains them, as the [IPTC](https://iptc.org/standards/photo-metadata/iptc-standard/) recommends. They don't replace alt text in the book: reading systems don't take a picture's text alternative from its file ([Sidecars and reports](sidecars.md)).
