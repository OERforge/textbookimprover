"""What a picture's file says about the people who made it, taken out
of the copies TextbookImprover writes (project.strip_metadata).

A photograph carries metadata into every output byte for byte: a
camera's position and serial number, the owner's name, the software and
dates of each edit, and sometimes a thumbnail of the picture before it
was cropped. This module takes out what a reader of the book has no use
for, at one of three levels:

- report: nothing changed; what private would take out is listed.
- private (the default): what's on the keep list stays, and the rest
  goes. Kept: the color profile, the orientation, and the resolution;
  rights, license, and credit; the creator; the description, alt text,
  and extended description. A project can add categories (gps,
  software, timestamps, device) or EXIF fields by name (keep_metadata).
- bare: only what the picture needs to be drawn as it is: the color
  profile, the orientation, and the markers a decoder reads.

JPEG, PNG, GIF, and WebP pictures are stripped; a TIFF is named and left
as it is. An Office or OpenDocument file loses its own properties about
its editors, and a PDF its editors' data (strip_pdf_document).

The strip is lossless and repeatable: a JPEG's segments, a PNG's chunks,
a GIF's extensions, and a WebP's chunks are dropped or rewritten, never
the compressed picture, so the pixels decoded before and after are the
same, and a second strip gives the same bytes. Everything is read as untrusted: offsets and counts are
checked against the file's length, an XMP packet with a document type
is dropped whole, a compressed chunk is never inflated, and a structure
that can't be read is taken out rather than kept, the orientation saved
where it can be.
"""

import re
import struct
import zlib

LEVELS = ("report", "private", "bare")
CATEGORIES = ("gps", "software", "timestamps", "device")

# EXIF's tags this module knows by name, as exiftool names them, for
# keep_metadata, with the category each belongs to and whether private
# keeps it. (tag, ifd) -> (name, category or "", kept by private)
IFD0, EXIF_IFD, GPS_IFD = "0", "exif", "gps"
EXIF_TAGS = {
    (0x010E, IFD0): ("ImageDescription", "", True),
    (0x010F, IFD0): ("Make", "device", False),
    (0x0110, IFD0): ("Model", "device", False),
    (0x0112, IFD0): ("Orientation", "", True),
    (0x011A, IFD0): ("XResolution", "", True),
    (0x011B, IFD0): ("YResolution", "", True),
    (0x0128, IFD0): ("ResolutionUnit", "", True),
    (0x0131, IFD0): ("Software", "software", False),
    (0x0132, IFD0): ("ModifyDate", "timestamps", False),
    (0x013B, IFD0): ("Artist", "", True),
    (0x0213, IFD0): ("YCbCrPositioning", "", True),
    (0x8298, IFD0): ("Copyright", "", True),
    (0x9000, EXIF_IFD): ("ExifVersion", "", True),
    (0x9003, EXIF_IFD): ("DateTimeOriginal", "timestamps", False),
    (0x9004, EXIF_IFD): ("CreateDate", "timestamps", False),
    (0x9010, EXIF_IFD): ("OffsetTime", "timestamps", False),
    (0x9011, EXIF_IFD): ("OffsetTimeOriginal", "timestamps", False),
    (0x9012, EXIF_IFD): ("OffsetTimeDigitized", "timestamps", False),
    (0x9290, EXIF_IFD): ("SubSecTime", "timestamps", False),
    (0x9291, EXIF_IFD): ("SubSecTimeOriginal", "timestamps", False),
    (0x9292, EXIF_IFD): ("SubSecTimeDigitized", "timestamps", False),
    (0xA001, EXIF_IFD): ("ColorSpace", "", True),
    (0xA430, EXIF_IFD): ("OwnerName", "", False),
    (0xA431, EXIF_IFD): ("SerialNumber", "device", False),
    (0xA433, EXIF_IFD): ("LensMake", "device", False),
    (0xA434, EXIF_IFD): ("LensModel", "device", False),
    (0xA435, EXIF_IFD): ("LensSerialNumber", "device", False),
    (0x927C, EXIF_IFD): ("MakerNote", "device", False),
    (0x9286, EXIF_IFD): ("UserComment", "", False),
    (0xA420, EXIF_IFD): ("ImageUniqueID", "", False),
}
NAMES = {name.lower(): key for key, (name, _, _) in EXIF_TAGS.items()}
# What bare keeps of EXIF: what a reader needs to draw the picture the
# right way up.
BARE_TAGS = {(0x0112, IFD0)}
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8,
              13: 4}
EXIF_POINTER, GPS_POINTER, INTEROP_POINTER = 0x8769, 0x8825, 0xA005

# XMP's properties private keeps, by namespace and name; None keeps the
# whole namespace.
DC = "http://purl.org/dc/elements/1.1/"
XMP_KEPT = {
    DC: {"rights", "creator", "description"},
    "http://ns.adobe.com/xap/1.0/rights/": None,
    "http://creativecommons.org/ns#": None,
    "http://ns.adobe.com/photoshop/1.0/": {"Credit"},
    "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/": {"AltTextAccessibility",
                                                    "ExtDescrAccessibility"},
    "http://ns.adobe.com/tiff/1.0/": {"Orientation", "XResolution", "YResolution",
                                      "ResolutionUnit"},
}
XMP_CATEGORIES = {
    "gps": {"http://ns.adobe.com/exif/1.0/": {"GPSLatitude", "GPSLongitude", "GPSAltitude",
                                              "GPSAltitudeRef", "GPSTimeStamp",
                                              "GPSVersionID", "GPSMapDatum"}},
    "software": {"http://ns.adobe.com/xap/1.0/": {"CreatorTool"}},
    "timestamps": {"http://ns.adobe.com/xap/1.0/": {"CreateDate", "ModifyDate", "MetadataDate"},
                   "http://ns.adobe.com/photoshop/1.0/": {"DateCreated"}},
    "device": {"http://ns.adobe.com/tiff/1.0/": {"Make", "Model"},
               "http://ns.adobe.com/exif/1.0/aux/": None},
}
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PDF_NS = "http://ns.adobe.com/pdf/1.3/"
PDFUA_ID = "http://www.aiim.org/pdfua/ns/id/"
PDFA_ID = "http://www.aiim.org/pdfa/ns/id/"
PDFA_EXTENSION = "http://www.aiim.org/pdfa/ns/extension/"
# A PDF's document XMP keeps, beside a picture's, what says what the
# document is and which standards it claims, so a PDF/UA or PDF/A file
# stays one: its title and language, its keywords, its PDF/UA and PDF/A
# identification, and the extension schemas PDF/A declares. At bare only
# these.
PDF_XMP_BARE = {
    DC: {"title", "language", "format"},
    PDFUA_ID: None,
    PDFA_ID: None,
    PDFA_EXTENSION: None,
}
PDF_XMP_KEPT = dict(XMP_KEPT, **{ns: names for ns, names in PDF_XMP_BARE.items() if ns != DC})
PDF_XMP_KEPT[DC] = XMP_KEPT[DC] | PDF_XMP_BARE[DC]
PDF_XMP_KEPT[PDF_NS] = {"Keywords"}
XMP_ID = b"http://ns.adobe.com/xap/1.0/\x00"
XMP_EXTENSION_ID = b"http://ns.adobe.com/xmp/extension/\x00"

# IPTC's datasets in record 2 that private keeps: the record's version,
# the by-line, its title, the credit, the source, the copyright notice,
# and the caption.
IPTC_KEPT = {0, 80, 85, 110, 115, 116, 120}

# PNG's chunks: what a decoder needs is kept at every level; text by its
# keyword, EXIF and XMP filtered, and the rest dropped.
PNG_DRAWN = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"cHRM", b"gAMA", b"iCCP",
             b"sBIT", b"sRGB", b"cICP", b"mDCv", b"cLLi", b"acTL", b"fcTL", b"fdAT"}
PNG_PRIVATE = {b"pHYs", b"bKGD"}
PNG_TEXT_KEPT = {b"Author", b"Copyright", b"Description"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def kept_tags(level, keep):
    """The EXIF tags kept at the level, with keep's categories and names."""
    if level == "bare":
        return set(BARE_TAGS)
    out = {key for key, (_, _, kept) in EXIF_TAGS.items() if kept}
    for word in keep or []:
        word = str(word).lower()
        out |= {key for key, (_, category, _) in EXIF_TAGS.items() if category == word}
        if word in NAMES:
            out.add(NAMES[word])
    return out


def check_keep(values):
    """keep_metadata's problems: each entry a category or an EXIF field
    this module knows by name."""
    problems = []
    for value in values or []:
        word = str(value).strip().lower()
        if word not in CATEGORIES and word not in NAMES:
            problems.append(f"{value!r} is neither a category ({', '.join(CATEGORIES)}) "
                            "nor an EXIF field kept by name ("
                            + ", ".join(sorted(n for n, _, _ in EXIF_TAGS.values())) + ")")
    return problems


# ---- EXIF ----

def _read_ifd(data, offset, order, limit=512):
    """An IFD's entries as [(tag, type, count, raw value bytes)] and the
    next IFD's offset, every offset and count checked against data."""
    if offset < 8 or offset + 2 > len(data):
        raise ValueError("an IFD outside the EXIF block")
    count = struct.unpack(order + "H", data[offset:offset + 2])[0]
    if count > limit or offset + 2 + count * 12 + 4 > len(data):
        raise ValueError("an IFD longer than the EXIF block")
    entries = []
    for index in range(count):
        at = offset + 2 + index * 12
        tag, kind, number = struct.unpack(order + "HHI", data[at:at + 8])
        size = TYPE_SIZES.get(kind)
        if size is None or number > len(data):
            raise ValueError("an EXIF entry of an unknown type or size")
        length = size * number
        if length <= 4:
            raw = data[at + 8:at + 8 + length]
        else:
            where = struct.unpack(order + "I", data[at + 8:at + 12])[0]
            if where + length > len(data):
                raise ValueError("an EXIF value outside the block")
            raw = data[where:where + length]
        entries.append((tag, kind, number, raw))
    following = struct.unpack(order + "I", data[offset + 2 + count * 12:
                                                 offset + 2 + count * 12 + 4])[0]
    return entries, following


def _pointer(entries, tag, order):
    for entry_tag, kind, number, raw in entries:
        if entry_tag == tag and kind in (4, 13) and number == 1:
            return struct.unpack(order + "I", raw)[0]
    return None


def _write_ifds(ifds, order):
    """A TIFF block of the IFDs [(name, entries)], IFD0 first, each sub-IFD
    linked from IFD0 by its pointer tag; no IFD1, so no thumbnail."""
    header = (b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, 8)
    named = dict(ifds)
    layout = [name for name in (IFD0, EXIF_IFD, GPS_IFD) if name in named]
    # Each IFD's entries, IFD0's with the pointers to the others.
    pointers = {EXIF_IFD: EXIF_POINTER, GPS_IFD: GPS_POINTER}
    tables = {}
    for name in layout:
        entries = [e for e in named[name] if e[0] not in (EXIF_POINTER, GPS_POINTER,
                                                         INTEROP_POINTER)]
        if name == IFD0:
            entries += [(pointers[n], 4, 1, b"\0\0\0\0") for n in layout if n != IFD0]
        tables[name] = sorted(entries, key=lambda e: e[0])
    # Offsets: each IFD then its values, in order.
    offsets, at = {}, 8
    for name in layout:
        offsets[name] = at
        at += 2 + 12 * len(tables[name]) + 4
        for _, _, _, raw in tables[name]:
            if len(raw) > 4:
                at += len(raw) + (len(raw) & 1)
    out = bytearray(header)
    for name in layout:
        values_at = offsets[name] + 2 + 12 * len(tables[name]) + 4
        block, values = bytearray(struct.pack(order + "H", len(tables[name]))), bytearray()
        for tag, kind, number, raw in tables[name]:
            if tag in (EXIF_POINTER, GPS_POINTER):
                target = EXIF_IFD if tag == EXIF_POINTER else GPS_IFD
                raw = struct.pack(order + "I", offsets[target])
            block += struct.pack(order + "HHI", tag, kind, number)
            if len(raw) <= 4:
                block += raw.ljust(4, b"\0")
            else:
                block += struct.pack(order + "I", values_at + len(values))
                values += raw + (b"\0" if len(raw) & 1 else b"")
        block += struct.pack(order + "I", 0)
        out += block + values
    return bytes(out)


def filter_exif(tiff, level, keep):
    """The TIFF block of an EXIF segment with only the kept tags, and what
    went, as names; None where nothing's kept. A block that can't be read
    goes whole."""
    removed = []
    try:
        order = {b"II": "<", b"MM": ">"}[tiff[:2]]
        if struct.unpack(order + "H", tiff[2:4])[0] != 42:
            raise ValueError("not a TIFF header")
        ifd0, following = _read_ifd(tiff, struct.unpack(order + "I", tiff[4:8])[0], order)
        found = {IFD0: ifd0}
        for name, tag in ((EXIF_IFD, EXIF_POINTER), (GPS_IFD, GPS_POINTER)):
            where = _pointer(ifd0, tag, order)
            if where is not None:
                found[name] = _read_ifd(tiff, where, order)[0]
    except (ValueError, KeyError, struct.error):
        return None, ["EXIF (unreadable, taken out whole)"]
    if following:
        removed.append("EXIF thumbnail (IFD1)")
    wanted = kept_tags(level, keep)
    keep_gps = level != "bare" and "gps" in [str(k).lower() for k in keep or []]
    kept = []
    for name, entries in found.items():
        if name == GPS_IFD:
            if keep_gps:
                kept.append((name, entries))
            else:
                removed.append("GPS position")
            continue
        own = []
        for entry in entries:
            tag = entry[0]
            if tag in (EXIF_POINTER, GPS_POINTER, INTEROP_POINTER):
                continue
            if (tag, name) in wanted:
                own.append(entry)
            else:
                label = EXIF_TAGS.get((tag, name), (f"tag 0x{tag:04X}",))[0]
                removed.append(f"EXIF {label}")
        if own:
            kept.append((name, own))
    if not kept:
        return None, removed or ["EXIF"]
    if all(name != IFD0 for name, _ in kept):
        kept.insert(0, (IFD0, []))
    return _write_ifds(kept, order), removed


# ---- XMP ----

def filter_xmp(packet, level, keep, kept=None):
    """An XMP packet with only the kept properties, and what went; None
    where nothing's kept. A packet with a document type, or one that
    isn't XML, goes whole. kept: a PDF's own kept list (PDF_XMP_KEPT),
    in place of a picture's, at bare too."""
    import xml.etree.ElementTree as ET
    if level == "bare" and kept is None:
        return None, ["XMP"]
    if b"<!DOCTYPE" in packet or b"<!ENTITY" in packet:
        return None, ["XMP (with a document type, taken out whole)"]
    text = re.sub(rb"<\?xpacket[^>]*\?>", b"", packet).strip(b"\x00 \r\n\t")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, ["XMP (unreadable, taken out whole)"]
    base = XMP_KEPT if kept is None else kept
    kept_ns = {ns: (None if names is None else set(names)) for ns, names in base.items()}
    for word in (keep or []) if level != "bare" else []:
        for ns, names in XMP_CATEGORIES.get(str(word).lower(), {}).items():
            if names is None or (ns in kept_ns and kept_ns[ns] is None):
                kept_ns[ns] = None
            else:
                kept_ns[ns] = (kept_ns.get(ns) or set()) | names

    def wanted(tag):
        if not tag.startswith("{"):
            return False
        ns, local = tag[1:].split("}", 1)
        return ns in kept_ns and (kept_ns[ns] is None or local in kept_ns[ns])

    def label(tag):
        return "XMP " + (tag.split("}", 1)[1] if tag.startswith("{") else tag)
    removed, any_kept = [], False
    for description in root.iter(f"{{{RDF}}}Description"):
        for name in list(description.attrib):
            if name.startswith(f"{{{RDF}}}"):
                continue
            if wanted(name):
                any_kept = True
            else:
                removed.append(label(name))
                del description.attrib[name]
        for child in list(description):
            if wanted(child.tag):
                any_kept = True
            else:
                removed.append(label(child.tag))
                description.remove(child)
        description.attrib.pop(f"{{{RDF}}}about", None)
        if f"{{{RDF}}}about" not in description.attrib:
            description.set(f"{{{RDF}}}about", "")
    if not any_kept:
        return None, removed or ["XMP"]
    for prefix, ns in (("x", "adobe:ns:meta/"), ("rdf", RDF), ("dc", DC),
                       ("xmpRights", "http://ns.adobe.com/xap/1.0/rights/"),
                       ("cc", "http://creativecommons.org/ns#"),
                       ("photoshop", "http://ns.adobe.com/photoshop/1.0/"),
                       ("Iptc4xmpCore", "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"),
                       ("tiff", "http://ns.adobe.com/tiff/1.0/"),
                       ("exif", "http://ns.adobe.com/exif/1.0/"),
                       ("xmp", "http://ns.adobe.com/xap/1.0/"),
                       ("aux", "http://ns.adobe.com/exif/1.0/aux/"),
                       ("pdf", PDF_NS), ("pdfuaid", PDFUA_ID), ("pdfaid", PDFA_ID),
                       ("pdfaExtension", PDFA_EXTENSION),
                       ("pdfaSchema", "http://www.aiim.org/pdfa/ns/schema#"),
                       ("pdfaProperty", "http://www.aiim.org/pdfa/ns/property#")):
        ET.register_namespace(prefix, ns)
    body = ET.tostring(root, encoding="utf-8").replace(b"<?xml version='1.0' encoding='utf-8'?>\n",
                                                       b"")
    out = (b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>' + body
           + b'<?xpacket end="w"?>')
    return out, removed


# ---- IPTC, in a JPEG's Photoshop segment ----

def filter_photoshop(data, level):
    """A JPEG's APP13 (Photoshop's image resources) with only IPTC's kept
    datasets, and what went; None where nothing's kept. Every other
    resource goes, the thumbnail among them."""
    if level == "bare":
        return None, ["Photoshop resources and IPTC"]
    head = b"Photoshop 3.0\x00"
    if not data.startswith(head):
        return None, ["APP13"]
    at, removed, iptc = len(head), [], b""
    while at + 12 <= len(data) and data[at:at + 4] == b"8BIM":
        ident = struct.unpack(">H", data[at + 4:at + 6])[0]
        name_length = data[at + 6]
        at_size = at + 6 + 1 + name_length + ((1 + name_length) & 1)
        if at_size + 4 > len(data):
            break
        size = struct.unpack(">I", data[at_size:at_size + 4])[0]
        start = at_size + 4
        if start + size > len(data):
            break
        if ident == 0x0404:
            iptc = data[start:start + size]
        else:
            removed.append(f"Photoshop resource 0x{ident:04X}"
                           + (" (thumbnail)" if ident in (0x0409, 0x040C) else ""))
        at = start + size + (size & 1)
    kept, here = b"", 0
    while here + 5 <= len(iptc) and iptc[here] == 0x1C:
        record, dataset = iptc[here + 1], iptc[here + 2]
        size = struct.unpack(">H", iptc[here + 3:here + 5])[0]
        if size & 0x8000:
            removed.append(f"IPTC {record}:{dataset} (extended)")
            break
        end = here + 5 + size
        if end > len(iptc):
            break
        if record == 2 and dataset in IPTC_KEPT:
            kept += iptc[here:end]
        else:
            removed.append(f"IPTC {record}:{dataset}")
        here = end
    datasets = [d for d in _iptc_sets(kept) if d != 0]
    if not datasets:
        return None, removed or ["IPTC"]
    block = b"8BIM" + struct.pack(">H", 0x0404) + b"\x00\x00" + struct.pack(">I", len(kept))
    block += kept + (b"\x00" if len(kept) & 1 else b"")
    return head + block, removed


def _iptc_sets(data):
    out, here = [], 0
    while here + 5 <= len(data) and data[here] == 0x1C:
        out.append(data[here + 2])
        here += 5 + struct.unpack(">H", data[here + 3:here + 5])[0]
    return out


# ---- JPEG ----

STANDALONE = set(range(0xD0, 0xD8)) | {0x01, 0xD8}


def strip_jpeg(data, level="private", keep=()):
    """A JPEG's bytes with what the level takes out taken out, and what
    went. The compressed picture, its tables, and its frame are copied
    as they are."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out, removed, at = bytearray(b"\xff\xd8"), [], 2
    while at < len(data):
        if data[at] != 0xFF:
            raise ValueError("a JPEG segment that doesn't begin with a marker")
        marker = data[at + 1] if at + 1 < len(data) else 0xD9
        if marker == 0xFF:
            at += 1
            continue
        if marker == 0xD9:
            out += b"\xff\xd9"
            if at + 2 < len(data):
                removed.append(f"{len(data) - at - 2} bytes after the picture's end")
            break
        if marker in STANDALONE:
            out += data[at:at + 2]
            at += 2
            continue
        if at + 4 > len(data):
            raise ValueError("a JPEG cut short")
        length = struct.unpack(">H", data[at + 2:at + 4])[0]
        end = at + 2 + length
        if length < 2 or end > len(data):
            raise ValueError("a JPEG segment longer than the file")
        body = data[at + 4:end]
        segment = data[at:end]
        if marker == 0xDA:
            # The scan: copied with the entropy-coded data after it, up to
            # the next marker that isn't a restart or a stuffed byte.
            scan_end = end
            while scan_end + 1 < len(data):
                if data[scan_end] == 0xFF and data[scan_end + 1] not in \
                        (0x00, *range(0xD0, 0xD8), 0xFF):
                    break
                scan_end += 1
            else:
                scan_end = len(data)
            out += data[at:scan_end]
            at = scan_end
            continue
        new = segment
        if marker == 0xE0 and body.startswith(b"JFIF\x00") and len(body) >= 14:
            if body[12] or body[13]:
                removed.append("JFIF thumbnail")
                fixed = body[:12] + b"\x00\x00"
                new = b"\xff\xe0" + struct.pack(">H", len(fixed) + 2) + fixed
        elif marker == 0xE0:
            new = None
            removed.append("JFIF extension (thumbnail)")
        elif marker == 0xE1 and body.startswith(b"Exif\x00\x00"):
            tiff, gone = filter_exif(body[6:], level, keep)
            removed += gone
            new = None if tiff is None else (b"\xff\xe1" + struct.pack(">H", len(tiff) + 8)
                                             + b"Exif\x00\x00" + tiff)
        elif marker == 0xE1 and body.startswith(XMP_ID):
            packet, gone = filter_xmp(body[len(XMP_ID):], level, keep)
            removed += gone
            if packet is not None and len(packet) + len(XMP_ID) + 2 > 0xFFFF:
                packet, removed = None, removed + ["XMP (too long once rewritten)"]
            new = None if packet is None else (
                b"\xff\xe1" + struct.pack(">H", len(packet) + len(XMP_ID) + 2) + XMP_ID + packet)
        elif marker == 0xE1:
            new = None
            removed.append("extended XMP" if body.startswith(XMP_EXTENSION_ID) else "APP1")
        elif marker == 0xE2 and body.startswith(b"ICC_PROFILE\x00"):
            pass
        elif marker == 0xED:
            resources, gone = filter_photoshop(body, level)
            removed += gone
            new = None if resources is None else (
                b"\xff\xed" + struct.pack(">H", len(resources) + 2) + resources)
        elif marker == 0xEE and body.startswith(b"Adobe"):
            pass
        elif 0xE0 <= marker <= 0xEF:
            new = None
            kind = body[:body.find(b"\x00")].decode("latin-1", "replace") if b"\x00" in body[:32] \
                else ""
            removed.append(f"APP{marker - 0xE0}" + (f" ({kind})" if kind.isprintable() and kind
                                                    else ""))
        elif marker == 0xFE:
            new = None
            removed.append("comment")
        if new is not None:
            out += new
        at = end
    return bytes(out), removed


# ---- PNG ----

def _chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(
        ">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def strip_png(data, level="private", keep=()):
    """A PNG's bytes with what the level takes out taken out, and what
    went. Every chunk a decoder needs, and every critical chunk it
    doesn't know, is copied as it is."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    out, removed, at = bytearray(PNG_SIGNATURE), [], len(PNG_SIGNATURE)
    while at + 12 <= len(data):
        length = struct.unpack(">I", data[at:at + 4])[0]
        kind = data[at + 4:at + 8]
        end = at + 12 + length
        if end > len(data):
            raise ValueError("a PNG chunk longer than the file")
        body = data[at + 8:at + 8 + length]
        whole = data[at:end]
        at = end
        if kind in PNG_DRAWN or not (kind[:1].islower()):
            out += whole
        elif kind in PNG_PRIVATE and level != "bare":
            out += whole
        elif kind in (b"tEXt", b"zTXt", b"iTXt"):
            keyword = body[:body.find(b"\x00")] if b"\x00" in body else body[:79]
            if kind == b"iTXt" and keyword == b"XML:com.adobe.xmp":
                # keyword, compression flag and method, language, and the
                # translated keyword, then the text, which is left as it is
                # if it's compressed (and dropped).
                head = body.split(b"\x00", 1)
                rest = head[1] if len(head) == 2 else b""
                if len(rest) >= 2 and rest[0] == 0:
                    tail = rest[2:].split(b"\x00", 2)
                    if len(tail) == 3:
                        packet, gone = filter_xmp(tail[2], level, keep)
                        removed += gone
                        if packet is not None:
                            out += _chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00"
                                          + packet)
                        continue
                removed.append("XMP (compressed or unreadable)")
            elif level != "bare" and keyword in PNG_TEXT_KEPT:
                out += whole
            else:
                removed.append(f"PNG text {keyword.decode('latin-1', 'replace')}")
        elif kind == b"eXIf":
            tiff, gone = filter_exif(body, level, keep)
            removed += gone
            if tiff is not None:
                out += _chunk(b"eXIf", tiff)
        elif kind == b"tIME":
            if level != "bare" and "timestamps" in [str(k).lower() for k in keep or []]:
                out += whole
            else:
                removed.append("PNG tIME")
        else:
            removed.append(f"PNG {kind.decode('latin-1', 'replace')}")
        if kind == b"IEND":
            if at < len(data):
                removed.append(f"{len(data) - at} bytes after the picture's end")
            break
    return bytes(out), removed


# ---- GIF ----

GIF_KEPT_APPLICATIONS = (b"NETSCAPE2.0", b"ANIMEXTS1.0", b"ICCRGBG1012")
GIF_XMP_ID = b"XMP DataXMP"
# XMP in a GIF ends with a "magic trailer" that lets a decoder walk it as
# sub-blocks: 0x01, then 0xFF down to 0x00 (XMP's specification, part 3).
GIF_XMP_TRAILER = b"\x01" + bytes(range(255, -1, -1))


def _gif_sub_blocks(data, at):
    """Where the sub-blocks starting at at end, just past their terminator."""
    while True:
        if at >= len(data):
            raise ValueError("a GIF cut short in its sub-blocks")
        size = data[at]
        at += 1 + size
        if size == 0:
            return at


def strip_gif(data, level="private", keep=()):
    """A GIF's bytes with its comments, XMP (filtered as a picture's),
    and other applications' data taken out, the looping and the color
    profile's kept, and nothing after its trailer; what went. Every
    picture and its graphic control are copied as they are."""
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data) < 13:
        raise ValueError("not a GIF")
    at = 13
    flags = data[10]
    if flags & 0x80:
        at += 3 * (2 << (flags & 7))
    if at > len(data):
        raise ValueError("a GIF's color table longer than the file")
    out, removed = bytearray(data[:at]), []
    while True:
        if at >= len(data):
            raise ValueError("a GIF without its trailer")
        block = data[at]
        if block == 0x3B:
            out += b"\x3b"
            if at + 1 < len(data):
                removed.append(f"{len(data) - at - 1} bytes after the picture's end")
            break
        if block == 0x2C:
            if at + 10 > len(data):
                raise ValueError("a GIF picture cut short")
            local = data[at + 9]
            start = at
            at += 10 + (3 * (2 << (local & 7)) if local & 0x80 else 0) + 1
            at = _gif_sub_blocks(data, at)
            out += data[start:at]
            continue
        if block != 0x21 or at + 2 > len(data):
            raise ValueError("a GIF block of an unknown kind")
        label, start = data[at + 1], at
        end = _gif_sub_blocks(data, at + 2)
        if label in (0xF9, 0x01):
            out += data[start:end]
        elif label == 0xFE:
            removed.append("GIF comment")
        elif label == 0xFF and at + 3 < len(data) and data[at + 2] == 11:
            name = data[at + 3:at + 14]
            if name in GIF_KEPT_APPLICATIONS:
                out += data[start:end]
            elif name == GIF_XMP_ID:
                raw = data[at + 14:end - 1]
                packet = raw[:-len(GIF_XMP_TRAILER)] if raw.endswith(GIF_XMP_TRAILER) else None
                if packet is None:
                    removed.append("XMP (unreadable, taken out whole)")
                else:
                    packet, gone = filter_xmp(packet, level, keep)
                    removed += gone
                    if packet is not None and b"\x00" not in packet:
                        out += (b"\x21\xff\x0b" + GIF_XMP_ID + packet + GIF_XMP_TRAILER
                                + b"\x00")
            else:
                removed.append("GIF application data ("
                               + name.decode("latin-1", "replace").strip() + ")")
        else:
            removed.append(f"GIF extension 0x{label:02X}")
        at = end
    return bytes(out), removed


# ---- WebP ----

WEBP_DRAWN = {b"VP8 ", b"VP8L", b"VP8X", b"ALPH", b"ANIM", b"ANMF", b"ICCP"}


def strip_webp(data, level="private", keep=()):
    """A WebP's bytes with its EXIF and XMP filtered as a picture's and
    every chunk a decoder doesn't need taken out, VP8X's flags and the
    file's size put right; what went."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP" or len(data) < 20:
        raise ValueError("not a WebP")
    size = struct.unpack("<I", data[4:8])[0]
    end_of_file = min(len(data), 8 + size)
    chunks, removed, at = [], [], 12
    while at + 8 <= end_of_file:
        kind = data[at:at + 4]
        length = struct.unpack("<I", data[at + 4:at + 8])[0]
        body = data[at + 8:at + 8 + length]
        if at + 8 + length > end_of_file:
            raise ValueError("a WebP chunk longer than the file")
        at += 8 + length + (length & 1)
        if kind in WEBP_DRAWN:
            chunks.append((kind, body))
        elif kind == b"EXIF":
            tiff = body[6:] if body.startswith(b"Exif\x00\x00") else body
            tiff, gone = filter_exif(tiff, level, keep)
            removed += gone
            if tiff is not None:
                chunks.append((kind, tiff))
        elif kind == b"XMP ":
            packet, gone = filter_xmp(body, level, keep)
            removed += gone
            if packet is not None:
                chunks.append((kind, packet))
        else:
            removed.append("WebP " + kind.decode("latin-1", "replace").strip())
    if len(data) > end_of_file + (end_of_file & 1):
        removed.append(f"{len(data) - end_of_file} bytes after the picture's end")
    kinds = {kind for kind, _ in chunks}
    out = bytearray()
    for kind, body in chunks:
        if kind == b"VP8X" and len(body) >= 1:
            flags = body[0] & ~0x0C
            flags |= (0x08 if b"EXIF" in kinds else 0) | (0x04 if b"XMP " in kinds else 0)
            body = bytes([flags]) + body[1:]
        out += kind + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")
    return b"RIFF" + struct.pack("<I", len(out) + 4) + b"WEBP" + bytes(out), removed


# ---- TIFF, reported ----

def tiff_said(data):
    """What a TIFF's first IFD says about its people, by EXIF_TAGS' names,
    and its EXIF and GPS IFDs; a TIFF is reported, not stripped, since
    its tags hold the picture's own layout."""
    order = {b"II": "<", b"MM": ">"}.get(data[:2])
    if order is None or struct.unpack(order + "H", data[2:4])[0] != 42:
        raise ValueError("not a TIFF")
    entries, _ = _read_ifd(data, struct.unpack(order + "I", data[4:8])[0], order, limit=4096)
    said = []
    for tag, _kind, _number, _raw in entries:
        if tag == GPS_POINTER:
            said.append("GPS position")
        elif tag == EXIF_POINTER:
            said.append("EXIF")
        elif tag == 0x02BC:
            said.append("XMP")
        elif tag in (0x83BB, 0x8649):
            said.append("IPTC" if tag == 0x83BB else "Photoshop data")
        elif (tag, IFD0) in EXIF_TAGS and not EXIF_TAGS[(tag, IFD0)][2]:
            said.append(f"EXIF {EXIF_TAGS[(tag, IFD0)][0]}")
    return said


# ---- by kind ----

JPEG_EXTENSIONS = (".jpg", ".jpeg", ".jpe", ".jfif")
PNG_EXTENSIONS = (".png",)
GIF_EXTENSIONS = (".gif",)
WEBP_EXTENSIONS = (".webp",)
TIFF_EXTENSIONS = (".tif", ".tiff")
PICTURE_EXTENSIONS = (JPEG_EXTENSIONS + PNG_EXTENSIONS + GIF_EXTENSIONS + WEBP_EXTENSIONS
                      + TIFF_EXTENSIONS)


def kind_of(name, data):
    """jpeg, png, gif, webp, tiff, or None, by the file's first bytes, its
    name agreeing."""
    lower = name.lower()
    if data[:2] == b"\xff\xd8" and lower.endswith(JPEG_EXTENSIONS):
        return "jpeg"
    if data.startswith(PNG_SIGNATURE) and lower.endswith(PNG_EXTENSIONS):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a") and lower.endswith(GIF_EXTENSIONS):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and lower.endswith(WEBP_EXTENSIONS):
        return "webp"
    if data[:4] in (b"II*\x00", b"MM\x00*") and lower.endswith(TIFF_EXTENSIONS):
        return "tiff"
    return None


def strip(name, data, level="private", keep=()):
    """(the bytes the level leaves, what private or bare takes out) for a
    picture named name; at report the bytes are data and the list what
    private would take out. A file this module doesn't know, or can't
    read, is returned as it is with nothing listed but why."""
    kind = kind_of(name, data)
    if kind is None:
        return data, []
    working = "private" if level == "report" else level
    try:
        if kind == "tiff":
            said = tiff_said(data)
            return data, ([f"TIFF, not stripped: {', '.join(said)} left as it is"]
                          if said else [])
        new, removed = {"jpeg": strip_jpeg, "png": strip_png, "gif": strip_gif,
                        "webp": strip_webp}[kind](data, working, keep)
    except (ValueError, struct.error, IndexError) as exc:
        return data, [f"not read ({exc}); left as it is"]
    return (data if level == "report" else new), removed


# ---- an Office file's own properties ----

CORE_NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": DC,
    "dcterms": "http://purl.org/dc/terms/",
}
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
# What private takes out of an Office file's core and extended
# properties, by namespace and name, each with the category that keeps
# it; bare takes out the creator, the description, and the rest of the
# core properties too, keeping the title and the language.
OFFICE_REMOVED = [
    (CORE_NS["cp"], "lastModifiedBy", ""),
    (CORE_NS["cp"], "revision", ""),
    (CORE_NS["cp"], "lastPrinted", "timestamps"),
    (CORE_NS["dcterms"], "created", "timestamps"),
    (CORE_NS["dcterms"], "modified", "timestamps"),
    (APP_NS, "Company", ""),
    (APP_NS, "Manager", ""),
    (APP_NS, "Template", ""),
    (APP_NS, "TotalTime", ""),
    (APP_NS, "Application", "software"),
    (APP_NS, "AppVersion", "software"),
]
OFFICE_BARE = [(DC, "creator", ""), (DC, "description", ""), (CORE_NS["cp"], "keywords", ""),
               (CORE_NS["cp"], "category", ""), (DC, "subject", "")]


def _prefixes(text, namespace):
    """The prefixes the document binds to namespace, "" for a default."""
    found = re.findall(r'xmlns(?::([\w.-]+))?="' + re.escape(namespace) + '"', text)
    return set(found)


def strip_office_properties(name, data, level, keep):
    """An Office file's docProps/core.xml or docProps/app.xml with its
    last editor, revision count, dates, company, manager, template, and
    editing time taken out at private (OFFICE_REMOVED), and its creator
    and description too at bare; what went. The elements are cut from
    the text as written, the rest left byte for byte; custom properties
    and comments are never touched."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, ["Office properties (not UTF-8); left as it is"]
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        return data, ["Office properties (with a document type); left as it is"]
    words = [str(k).lower() for k in keep or []]
    wanted = [entry for entry in OFFICE_REMOVED if not entry[2] or entry[2] not in words]
    if level == "bare":
        wanted = OFFICE_REMOVED + OFFICE_BARE
    text, removed, changed = _cut_elements(text, wanted, "Office")
    return (text.encode("utf-8") if changed else data), removed


def _cut_elements(text, wanted, kind):
    """text without the elements wanted names [(namespace, local name,
    category)], under whatever prefix the document binds; (text, what
    went, as "kind local", whether it changed). An element said to have
    gone is one with text or, empty, with attributes (ODF's template)."""
    removed, changed = [], False
    for namespace, local, _ in wanted:
        for prefix in _prefixes(text, namespace):
            tag = f"{prefix}:{local}" if prefix else local
            pattern = re.compile(r"<%s(?:\s[^<>]*)?(?:/>|>[^<]*</%s\s*>)" % (
                re.escape(tag), re.escape(tag)))
            said = [m for m in pattern.findall(text)
                    if (re.sub(r"<[^>]*>", "", m).strip() if not m.endswith("/>")
                        else re.search(r"\s[\w.:-]+\s*=", m))]
            text, count = pattern.subn("", text)
            changed = changed or bool(count)
            if said:
                removed.append(f"{kind} {local}")
    return text, removed, changed


# ---- an OpenDocument file's own properties ----

ODF_META = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
ODF_CONFIG = "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
# What private takes out of an OpenDocument file's meta.xml: dc:creator is
# its last editor there, meta:initial-creator its author, who's kept.
ODF_REMOVED = [
    (DC, "creator", ""),
    (ODF_META, "printed-by", ""),
    (ODF_META, "editing-cycles", ""),
    (ODF_META, "editing-duration", ""),
    (ODF_META, "template", ""),
    (ODF_META, "creation-date", "timestamps"),
    (DC, "date", "timestamps"),
    (ODF_META, "print-date", "timestamps"),
    (ODF_META, "generator", "software"),
]
ODF_BARE = [(ODF_META, "initial-creator", ""), (DC, "description", ""),
            (DC, "subject", ""), (ODF_META, "keyword", "")]
# settings.xml's printer, by its name and its driver's settings.
ODF_PRINTER_ITEMS = ("PrinterName", "PrinterSetup")


def strip_odf_properties(name, data, level, keep):
    """An OpenDocument file's meta.xml with its last editor, printer,
    editing count and time, template, dates, and generator taken out at
    private (ODF_REMOVED), its author and description too at bare, or
    its settings.xml with the printer's name and setup emptied; what went.
    The rest is left byte for byte, its user-defined properties among it."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, ["OpenDocument properties (not UTF-8); left as it is"]
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        return data, ["OpenDocument properties (with a document type); left as it is"]
    if name == "settings.xml":
        removed, changed = [], False
        for prefix in _prefixes(text, ODF_CONFIG):
            item = f"{prefix}:config-item" if prefix else "config-item"
            attr = f"{prefix}:name" if prefix else "name"
            for which in ODF_PRINTER_ITEMS:
                pattern = re.compile(r'(<%s\s[^<>]*%s="%s"[^<>]*>)([^<]+)(</%s\s*>)' % (
                    re.escape(item), re.escape(attr), which, re.escape(item)))
                text, count = pattern.subn(r"\1\3", text)
                if count:
                    changed = True
                    removed.append(f"OpenDocument {which}")
        return (text.encode("utf-8") if changed else data), removed
    words = [str(k).lower() for k in keep or []]
    wanted = [entry for entry in ODF_REMOVED if not entry[2] or entry[2] not in words]
    if level == "bare":
        wanted = ODF_REMOVED + ODF_BARE
    text, removed, changed = _cut_elements(text, wanted, "OpenDocument")
    return (text.encode("utf-8") if changed else data), removed


ODF_EXTENSIONS = (".odt", ".odp", ".ods", ".odg", ".ott", ".otp", ".ots")
ODF_PARTS = ("meta.xml", "settings.xml")


OFFICE_EXTENSIONS = (".docx", ".pptx", ".xlsx", ".docm", ".pptm", ".xlsm")
OFFICE_PARTS = ("docProps/core.xml", "docProps/app.xml")


# ---- an output's folder ----

# Containers whose pictures are stripped where they are: an EPUB, Office's
# and OpenDocument's files, a cartridge, and a zip the run writes.
ZIP_EXTENSIONS = (".epub", ".docx", ".pptx", ".xlsx", ".docm", ".pptm", ".xlsm", ".odt",
                  ".odp", ".ods", ".odg", ".ott", ".otp", ".ots", ".imscc", ".zip")


def strip_zip(path, level, keep, own_dates=False):
    """The pictures inside a zip, and an Office file's own properties,
    stripped in place, every other member and each member's entry (name,
    date, mode, compression, order) kept; [(member, what went)]. Written
    again only where something changed. own_dates: the Office file's
    dates are the run's own, a writer's, not an editor's, and kept."""
    import zipfile
    rows, changed = [], {}
    office = path.lower().endswith(OFFICE_EXTENSIONS)
    odf = path.lower().endswith(ODF_EXTENSIONS)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            properties = (office and info.filename in OFFICE_PARTS) or (
                odf and info.filename in ODF_PARTS)
            pdf = info.filename.lower().endswith(".pdf")
            if info.is_dir() or not (properties or pdf or info.filename.lower().endswith(
                    PICTURE_EXTENSIONS)):
                continue
            data = archive.read(info)
            if pdf:
                try:
                    new, found = strip_pdf_bytes(data, level, keep)
                except Exception as exc:  # a PDF that can't be read is left, and said
                    new, found = data, [("", [f"not read ({type(exc).__name__}); left as it is"])]
                rows += [(info.filename + (f", {where}" if where else ""), removed)
                         for where, removed in found]
                if new != data:
                    changed[info.filename] = new
                continue
            if properties:
                new, removed = (strip_odf_properties if odf else strip_office_properties)(
                    info.filename, data, "private" if level == "report" else level,
                    tuple(keep) + (("timestamps",) if own_dates else ()))
                new = data if level == "report" else new
            else:
                new, removed = strip(info.filename, data, level, keep)
            if removed:
                rows.append((info.filename, removed))
            if new != data:
                changed[info.filename] = new
    if changed:
        tmp = path + ".strip"
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(tmp, "w") as out:
            for info in source.infolist():
                out.writestr(info, changed.get(info.filename) or source.read(info),
                             compress_type=info.compress_type)
        import os
        os.replace(tmp, path)
    return rows


# A PDF's document information: what private keeps, and what a category
# keeps besides; bare keeps the title alone.
PDF_INFO_KEPT = {"/Title", "/Subject", "/Keywords", "/Author", "/Trapped"}
PDF_INFO_CATEGORIES = {"software": {"/Creator", "/Producer"},
                       "timestamps": {"/CreationDate", "/ModDate"}}
# What pdfTeX and LuaTeX copy from a PDF they include, beside its page:
# its document information and its file's name (/PTEX.*), and its page's
# editor's data and dates; all of it goes from a PDF the run made.
PTEX_KEYS = ("/PTEX.InfoDict", "/PTEX.FileName")


def _pdf_info_drops(info, level, keep):
    """The document information's keys the level takes out."""
    words = [str(k).lower() for k in keep or []] if level != "bare" else []
    kept = {"/Title"} if level == "bare" else set(PDF_INFO_KEPT)
    for word in words:
        kept |= PDF_INFO_CATEGORIES.get(word, set())
    return [key for key in info.keys() if key not in kept]


def _filtered_metadata(holder, level, keep, kept, where, rows):
    """holder's /Metadata stream given only what the level keeps (filter_xmp
    with kept), or taken out where nothing is; True if it changed."""
    import pikepdf
    stream = holder.get("/Metadata")
    if not isinstance(stream, pikepdf.Stream):
        return False
    try:
        data = stream.read_bytes()
    except Exception:  # a stream that can't be decoded goes
        del holder["/Metadata"]
        rows.append((where, ["XMP (unreadable, taken out whole)"]))
        return True
    packet, removed = filter_xmp(data, level, keep, kept=kept)
    if removed:
        rows.append((where, removed))
    if packet is None:
        del holder["/Metadata"]
        return True
    if packet != data:
        stream.write(packet)
        return True
    return False


def strip_pdf_document(pdf, level, keep, own=False):
    """An open PDF's metadata about its people taken out in place, at
    private or bare; ([(where in it, what went)], whether it changed).

    Every PDF: a JPEG picture's own metadata (a DCTDecode stream is a JPEG
    file), a picture's and a page's XMP, a page's /PieceInfo (an editor's
    private data, sometimes the whole working file) and /LastModified,
    and what pdfTeX and LuaTeX copy from a PDF they include as a figure:
    its document information and file name (PTEX_KEYS), its page's XMP,
    /PieceInfo, and /LastModified. A PDF the run didn't make (own False),
    a copy of an author's file, also loses its document information but
    PDF_INFO_KEPT and its document XMP but PDF_XMP_KEPT, so a PDF/UA or
    PDF/A file keeps its claim; one the run made keeps those as written."""
    import pikepdf
    rows, changed = [], False
    xmp_kept = PDF_XMP_BARE if level == "bare" else PDF_XMP_KEPT
    timestamps = "timestamps" in [str(k).lower() for k in keep or []] and level != "bare"

    def editors_data(holder, where):
        nonlocal changed
        gone = []
        if "/PieceInfo" in holder:
            del holder["/PieceInfo"]
            gone.append("PDF PieceInfo (an editor's data)")
        if "/LastModified" in holder and not timestamps:
            del holder["/LastModified"]
            gone.append("PDF LastModified")
        for key in PTEX_KEYS:
            if key in holder:
                value = holder[key]
                said = ", ".join(str(k)[1:] for k in value.keys()) \
                    if isinstance(value, pikepdf.Dictionary) else ""
                del holder[key]
                gone.append("an included PDF's " + ("information" + (f" ({said})" if said else "")
                                                    if key == "/PTEX.InfoDict" else "file name"))
        if gone:
            rows.append((where, gone))
            changed = True
        if _filtered_metadata(holder, level, keep, xmp_kept, where, rows):
            changed = True

    for number, page in enumerate(pdf.pages, 1):
        editors_data(page.obj, f"page {number}")
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream):
            continue
        subtype = obj.get("/Subtype")
        if subtype == "/Form":
            editors_data(obj, f"object {obj.objgen[0]}")
        elif subtype == "/Image":
            editors_data(obj, f"object {obj.objgen[0]}")
            if obj.get("/Filter") == "/DCTDecode":
                data = obj.read_raw_bytes()
                new, removed = strip("picture.jpg", data, level, keep)
                if removed:
                    rows.append((f"object {obj.objgen[0]}", removed))
                if new != data:
                    obj.write(new, filter=pikepdf.Name.DCTDecode,
                              decode_parms=obj.get("/DecodeParms"))
                    changed = True
    if not own:
        if "/PieceInfo" in pdf.Root:
            del pdf.Root["/PieceInfo"]
            rows.append(("document", ["PDF PieceInfo (an editor's data)"]))
            changed = True
        if _filtered_metadata(pdf.Root, level, keep, xmp_kept, "document", rows):
            changed = True
        info = pdf.trailer.get("/Info")
        if isinstance(info, pikepdf.Dictionary):
            drops = _pdf_info_drops(info, level, keep)
            if drops:
                for key in drops:
                    del info[key]
                rows.append(("document", [f"PDF {str(key)[1:]}" for key in drops]))
                changed = True
    return rows, changed


def _pdf_left(pdf):
    """Why a PDF is left as it is, or None: one that's encrypted, or
    signed, whose signature a rewrite would break."""
    if pdf.is_encrypted:
        return "encrypted; left as it is"
    acroform = pdf.Root.get("/AcroForm")
    try:
        if acroform is not None and int(acroform.get("/SigFlags", 0)) & 1:
            return "signed; left as it is"
    except (TypeError, ValueError):
        pass
    if "/Perms" in pdf.Root:
        return "signed; left as it is"
    return None


def strip_pdf_bytes(data, level, keep, own=False):
    """A PDF's bytes stripped (strip_pdf_document), and [(where in it,
    what went)]; at report the bytes are data. Without pikepdf, or for a
    PDF that's encrypted or signed, data and one row saying why."""
    import io
    try:
        import pikepdf
    except ImportError:
        return data, [("", ["not read (pikepdf isn't installed); left as it is"])]
    working = "private" if level == "report" else level
    with pikepdf.open(io.BytesIO(data)) as pdf:
        left = _pdf_left(pdf)
        if left:
            return data, [("", [left])]
        rows, changed = strip_pdf_document(pdf, working, keep, own)
        if level == "report" or not changed:
            return data, rows
        out = io.BytesIO()
        pdf.save(out, deterministic_id=True)
    return out.getvalue(), rows


def strip_pdf(path, level, keep, own=False):
    """A PDF file stripped in place (strip_pdf_bytes), written again only
    where something changed; [(where in it, what went)]. own: the run made
    it, and its document information and XMP are left as written."""
    with open(path, "rb") as fh:
        data = fh.read()
    new, rows = strip_pdf_bytes(data, level, keep, own)
    if new != data:
        import os
        tmp = path + ".strip"
        with open(tmp, "wb") as fh:
            fh.write(new)
        os.replace(tmp, path)
    return rows


def strip_folder(folder, level="private", keep=(), own_dates=False, own_pdfs=False):
    """Every picture an output's folder holds, as a file or inside a
    container (ZIP_EXTENSIONS, a PDF), and every PDF's and Office file's
    metadata about its people, stripped in place at the level, no link
    followed; [(the file's path from folder, the member or "", what
    went)], at report what private would take out. own_dates: an Office
    file's dates are the run's (strip_zip); own_pdfs: the folder's PDFs
    are the run's, their document information and XMP left as written
    (strip_pdf_document)."""
    import os
    rows = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
        for name in sorted(files):
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            where = os.path.relpath(path, folder).replace(os.sep, "/")
            lower = name.lower()
            try:
                if lower.endswith(PICTURE_EXTENSIONS):
                    with open(path, "rb") as fh:
                        data = fh.read()
                    new, removed = strip(name, data, level, keep)
                    if removed:
                        rows.append((where, "", removed))
                    if new != data:
                        with open(path, "wb") as fh:
                            fh.write(new)
                elif lower.endswith(ZIP_EXTENSIONS):
                    rows += [(where, member, removed)
                             for member, removed in strip_zip(path, level, keep, own_dates)]
                elif lower.endswith(".pdf"):
                    rows += [(where, member, removed)
                             for member, removed in strip_pdf(path, level, keep, own_pdfs)]
            except Exception as exc:  # a file that can't be read is left, and said
                rows.append((where, "", [f"not read ({type(exc).__name__}); left as it is"]))
    return rows
