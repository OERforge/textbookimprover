# Project settings

Settings that describe the book rather than any one rendering or package of it, under `project:` in `project.yaml`, which both halves of the pipeline read. A run writes `project-sample.yaml` with every one and its description when nothing names the book, and so does `python3 $T/bin/build-cartridge.py -d . --pages html --init` when nothing names the book and no run has written one: edit it and rename it to `project.yaml` (`T` is the directory you cloned the tools into). [Configuration](configuration.md#samples) has the other two samples. Generated from `lib/schema-project.yaml` by `util/settings-reference.py`; edit the schema, not this page.

Facts about the book itself, true of every rendering of it.

**`identifier`**—`ncname`; default `book`

A name for this book that no other book anywhere will use. It is what an LMS matches on to recognize a re-import as the same course, it's what the content folder inside a package is named after, and two books sharing one are two books the LMS will treat as one. The IMS schema only requires it to be unique within the package; uniqueness beyond that's your responsibility and nothing will warn you. It also has to be a valid XML name, because IMS types it as xs:ID: start with a letter, then letters, digits, and . - _ only. No colons, and it may not start with a digit—which rules out both obvious ways of generating a unique one, since a bare UUID usually starts with a digit and urn:uuid: has colons. Reverse-DNS is the least error-prone form and reads well as a folder name: org.example.dept.course-code. A UUID works with a letter in front, which you can generate with python3 -c "import uuid; print('i' + uuid.uuid4().hex)". Whichever you choose, keep it for the life of the book. Changing it makes every future import a new course rather than an update.

**`kind`**—one of `book`, `slides`; default `book`

What the folder holds: a book, whose files are its pages, or slides, a set of decks, each a document of its own: PowerPoint decks, each checked and remediated on its own, or decks written in Markdown, in Pandoc's slide Markdown, which only this setting says are decks. A folder of PowerPoint decks with nothing a book is read from (a README.md aside) is slides without saying so here, and the run says so as it starts. PowerPoint decks take format: source targets, which write each deck's decisions into a copy of it, and imply one, remediated, when none is named; html, pdf, revealjs, and markdown targets, which convert each deck; and a pptx target on a template (slides.reference_doc), which rebuilds it. Decks written in Markdown take html (implied when none is named), pdf, pptx, revealjs, markdown, and source targets. A slides folder holding both kinds stops the run; in a book's folder, PowerPoint decks are left out, and the run says so.

**`title`**—`string`; default `Untitled`

The book's title, as it should appear to a reader.

**`subtitle`**—`string`; default `""` (empty)

The book's subtitle, as a reader should see it after the title. An EPUB records it as a second title, typed subtitle; a PDF sets it on its title page, and has it in its XMP; a cartridge's title has it after a colon.

**`language`**—`language`; default `en`

BCP 47 language tag for the book's text. Sets the lang attribute on every page in it (WCAG 3.1.1) and the language declared in any package built from those pages; a page in another language, as its row in the languages sidecar or its own file says, is marked in its own (WCAG 3.1.2; docs/sidecars.md). Quote it: unquoted no, yes, and on are read as booleans by YAML. A PDF of a book in a language other than English needs TeX's support for the language installed, which docs/installation.md says how to add, Spanish's for one.

**`description`**—`text`; default `""` (empty)

A sentence or two about the book, used wherever a package format asks for one.

**`doi`**—`doi`; default `""` (empty)

The book's DOI, bare (10.5281/zenodo.1234567) or as its address, checked for its form and kept bare. An EPUB records it as an identifier typed DOI, after the book's own; a PDF in its XMP; a cartridge's manifest as an identifier in the DOI catalog.

## isbn

The book's ISBNs, one for each format that has its own: each an ISBN-13 or an ISBN-10, its hyphens as you like, checked for its check digit and kept as its 13 digits, an ISBN-10 as the ISBN-13 it becomes. The EPUB records its own, epub, as an identifier typed ISBN-13, and the PDF its own, pdf, in its XMP; the others are kept for the formats TextbookImprover doesn't make, and for the book's records.

**`isbn.epub`**—`isbn`; default `""` (empty)

The EPUB's ISBN.

**`isbn.pdf`**—`isbn`; default `""` (empty)

The PDF's ISBN, which its XMP gives as its identifier.

**`isbn.paperback`**—`isbn`; default `""` (empty)

A paperback's ISBN, where the book is printed as one.

**`isbn.hardcover`**—`isbn`; default `""` (empty)

A hardcover's ISBN, where the book is printed as one.

## series

A series the book is part of, and its place in it. An EPUB records them as the collection it belongs to, a series, and its position; a cartridge's manifest as what it's part of.

**`series.name`**—`string`; default `""` (empty)

The series' name.

**`series.position`**—`string`; default `""` (empty)

The book's place in the series, as a number (3, or 3.5); quote it.

**`url`**—`url`; default `""` (empty)

The book's own address, where readers find it, as an http or https URL. A PDF has it in its XMP, and a cartridge's manifest records it as an identifier in the URI catalog.

**`keywords`**—`list`; default `[]`

Words a catalog can find the book by. An EPUB records each as a subject, a PDF as its keywords, and a cartridge's manifest each as a keyword. Where they're unset, a package's packaging.yaml keywords are its cartridge's, as they were, and the run says to move them here.

**`publisher`**—`organization`; default `""` (empty)

Who published the book: a name, or a mapping with name and ror, the organization's ROR ID (https://ror.org/05dxps055 or 05dxps055), checked for its checksum. An EPUB records the name as its publisher, as a PDF's XMP does, and a cartridge's manifest the publisher, with the date.

## place

Where the book is published, where that says something of it. Read and checked; for the book's records (see ROADMAP.md).

**`place.city`**—`string`; default `""` (empty)

The city it's published in.

**`place.country`**—`string`; default `""` (empty)

The country it's published in.

**`funding`**—`list`; default `[]`

Who paid for the book, one entry each: the funder's name, or a mapping with funder (a name, or a mapping with name and ror, the funder's ROR ID, checked for its checksum) and, as you like, grant (the award's number or name, as the funder gives it). An EPUB records each funder as a contributor, a funder (MARC's fnd); the grants are kept for the book's records.

**`contact`**—`contact`; default `""` (empty)

Where a reader writes about the book, to report a mistake say: an email address (econ-book@example.edu) or an http or https URL. Read and checked; for the book's records (see ROADMAP.md).

## coverage

The place and the time the book is about, where it's about one (a history of the United States, say). An EPUB records them as its coverage, and a cartridge's manifest each as a coverage of its own.

**`coverage.place`**—`string`; default `""` (empty)

The place, as a reader would name it (United States).

**`coverage.time`**—`string`; default `""` (empty)

The time, as a reader would name it (1865 to 1900, or the twentieth century).

**`copyright`**—`string`; default `""` (empty)

The book's copyright line, as it should read (© 2026 Robert Szarka). An EPUB records it, with the license, as its rights; a PDF as its copyright; a cartridge's manifest in its rights' description.

**`license`**—`string`; default `""` (empty)

The license the book is published under, as its SPDX identifier where it has one (CC-BY-4.0, CC-BY-NC-SA-4.0, CC0-1.0) and otherwise as its name. A Creative Commons license and CC0 are known by name and deed; another is given as it's written. An EPUB records it, after the copyright line, as its rights; a PDF its address as its license's; a cartridge's manifest says it costs nothing where it's Creative Commons' or CC0, that it has conditions but for CC0, and names it in its rights' description. A part may have a license of its own (parts), which its outputs give in its place.

## education

Who the book is for and what it teaches, for the catalogs and the learning management systems that read a book's educational metadata.

**`education.level`**—`string`; default `""` (empty)

The level it's written for, in your own words (Undergraduate, lower division). A cartridge's manifest classifies the book by it, as its educational level.

**`education.context`**—one of ``, `higher education`, `school`, `training`, `other`; default `""` (empty)

Where it's used, as IEEE LOM names the setting: higher education, school, training, or other. A cartridge's manifest gives it as its context, which Common Cartridge's guide calls information only, not meant to change what an LMS does.

**`education.audience`**—`string`; default `""` (empty)

Who reads it, in your own words (learners, instructors). Read and checked; for the book's records (see ROADMAP.md).

**`education.subjects`**—`list`; default `[]`

The subjects the book is classed under, each a name, or a mapping with name, id (its code in a scheme), and scheme (the scheme's name): {name: "Economics, General", id: "45.0601", scheme: CIP 2020}. An EPUB records each as a subject, with its scheme as the authority and its code as the term; a cartridge's manifest classifies the book by each as a discipline, the classification's description naming the scheme.

**`education.objectives`**—`list`; default `[]`

What a reader learns from the book, one entry each. A cartridge's manifest classifies the book by each, as an educational objective.

**`education.prerequisites`**—`list`; default `[]`

What a reader should know first, one entry each. A cartridge's manifest classifies the book by each, as a prerequisite.

**`education.resource_type`**—`string`; default `""` (empty)

What kind of resource the book is, in your own words (textbook). Read and checked; for the book's records (see ROADMAP.md), since a cartridge takes one value alone, IMS Common Cartridge.

**`education.typical_age`**—`agerange`; default `""` (empty)

Its readers' ages, as a range (18-22, or 18- for 18 and over). Read and checked; for the book's records (see ROADMAP.md).

**`education.time_required`**—`duration`; default `""` (empty)

How long working through it takes, as an ISO 8601 duration (PT40H for 40 hours). Read and checked; for the book's records (see ROADMAP.md).

**`metadata_license`**—`string`; default `CC0-1.0`

The license for the book's metadata, as distinct from the book: CC0-1.0, the default, lets a catalog copy the record freely. An SPDX identifier where it has one. Read and checked; for the book's records (see ROADMAP.md).

**`numbering`**—`bool`; default `false`

Number the book's structure the way a printed book does: groups and top-level pages with the main role 1, 2, 3 and their pages 1.1, 1.2; appendices A, B and A.1, A.2; front and back matter unnumbered. The numbers appear in the EPUB's table of contents and headings, the cartridge organization, the generated contents page, and the pages' titles.

**`authors`**—`list`; default `[]`

Who wrote the book, one entry each: a name, as a reader should see it, or a mapping with name and, as you like, given and family (the parts of the name, which nothing works out for you), orcid (an ORCID iD, 0000-0002-1825-0097 or its address, checked for its check digit), and affiliation (a name, or a mapping with name and ror). An EPUB records each as a creator, an author, filed under "family, given" where both are given; a PDF names each as its author; a cartridge's manifest gives each, as a vCard, as an author. For an OpenStax book the publisher is usually the right entry.

**`adapters`**—`list`; default `[]`

Who adapted another's book into this one, each written as an author is. An EPUB records each as a creator, an adapter, after the authors; a cartridge's manifest as an editor, the nearest of its roles.

**`editors`**—`list`; default `[]`

Who edited the book, each written as an author is. An EPUB records each as a creator, an editor, after the adapters, and a cartridge's manifest as an editor.

**`contributors`**—`list`; default `[]`

Who else had a hand in the book, each a mapping written as an author's is, with a role: a MARC relator, by its code (ill) or its term (illustrator), from the Library of Congress's list (https://www.loc.gov/marc/relators/relaterm.html). An EPUB records each as a contributor in that role; a cartridge's manifest has no place for one.

**`passthrough`**—`path`; default `_pt`

A directory, inside the book's, for pages that aren't converted from the book's sources: an .html here is a page someone finished and is copied into every HTML target as it stands (and read for the EPUB), and an .md here is converted alongside the sources. Its files are treated as though they sat beside the sources, so a reference in _pt/about.html to images/logo.png names the book's images/logo.png. Every .html beside the sources is a source.

**`contents`**—`opaque`; default `[]`

The book's structure as a nested list of pages and groups. This describes the book, not any one package, so a cartridge organization and an EPUB table of contents are both built from it. A group or page may carry a role, front, main, appendix, or back, which says how it counts when numbering is on and where it belongs in the book; the default is main. It may also carry a type, what it is (preface, glossary, index, part, or another of the types EPUB's structural semantics name that docs/configuration.md lists; any other is warned of and ignored), which an EPUB marks for reading systems and screen readers; a top-level entry with no role is in the part of the book its type implies, and a type isn't inherited. An entry "generate: toc" is a page the run writes, a full table of contents with links, named toc unless "name" says otherwise and titled Contents unless "title" does. Left empty, tools that need an order guess one and say so.

**`parts`**—`opaque`; default `{}`

What the project is made of, when it's more than one thing: a block of names, each a part with its kind, book, slides, or files (a folder of files that travel with the project and that no target uses; testbank is kept for the test banks to come). A part may name the file it's unpacked from, its from, as a path inside the project (upstream/book.zip) or as a block with file, unpacker (cartridge, cnx, epub, jekyll, site, or archive), and options, the unpacker's options that change what it writes; and a license, when the part's isn't the book's. A part's name is a lowercase letter, then lowercase letters, digits, - and _. In a project with a folder for each part under src/, a part's kind is what its run takes it for, and a project that names no parts has one, the folder src/ holds; with more than one folder there the run stops and asks for them. A part may have an identifier, title, contents, and numbering of its own, which its run takes in place of the project's: a second book in a project (an instructor's version beside the student's) is then another course to an LMS, with its own order. Where a part has none, the project's is used, but for a part that isn't a book (decks), which gets no contents or numbering it doesn't set. An unpacker given --part writes the part's from, and a run unpacks the file it names into the part's folder under src/ when that folder holds nothing, and says afterwards when the folder no longer matches it (convert.py --src-status lists how). A part's license is its run's in place of the project's, so its EPUB, its PDF, and a cartridge of its pages give it as their rights.

**`include`**—`list`; default `[]`

Files at the top of the project's folder that travel with it, a README or a notes file, each a path from there. Read and checked; not acted on yet (see ROADMAP.md).
