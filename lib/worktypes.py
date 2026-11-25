"""
worktypes.py -- what kind of work a book or a part is, in DataCite's
words, and what a run takes it for where nothing says.

A work's type is one of DataCite's resourceTypeGeneral values (schema
4.7, which lists 34), written as DataCite spells it and matched without
regard to case. Where neither the project nor the part gives one, it
follows the part's kind: a book is a Book, slides a Presentation, and
files a Dataset. A poster, which TextbookImprover makes from either kind
of part, says so itself.

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

# DataCite Metadata Schema 4.7's resourceTypeGeneral, in its own order.
WORK_TYPES = (
    "Audiovisual", "Award", "Book", "BookChapter", "Collection", "ComputationalNotebook",
    "ConferencePaper", "ConferenceProceeding", "DataPaper", "Dataset", "Dissertation",
    "Event", "Image", "Instrument", "InteractiveResource", "Journal", "JournalArticle",
    "Model", "OutputManagementPlan", "PeerReview", "PhysicalObject", "Poster", "Preprint",
    "Presentation", "Project", "Report", "Service", "Software", "Sound", "Standard",
    "StudyRegistration", "Text", "Workflow", "Other")
BY_LOWER = {name.lower(): name for name in WORK_TYPES}
# What a part's kind is taken for where no type is given.
BY_KIND = {"book": "Book", "slides": "Presentation", "files": "Dataset"}


def normalize(value):
    """A work's type as DataCite spells it, or ValueError where it isn't
    one of DataCite's."""
    text = str(value).strip()
    found = BY_LOWER.get(text.lower())
    if found is None:
        raise ValueError(f"{value!r} isn't one of DataCite's types of work: "
                         + ", ".join(WORK_TYPES))
    return found


def default(kind):
    """The type a part of this kind is taken for: a book's Book, slides'
    Presentation, files' Dataset, and anything else's Other."""
    return BY_KIND.get(str(kind or "book"), "Other")
