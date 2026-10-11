"""Compact PPTX assets without flattening editable text or slide artwork."""
from __future__ import annotations

import io
import posixpath
import struct
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as ET
from PIL import Image, ImageOps

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def prune_parts(parts: dict[str, bytes]) -> dict[str, bytes]:
    """Follow OPC relationships so unused source slides and photos are removed."""
    keep = {"[Content_Types].xml"}
    queue = [""]
    while queue:
        owner = queue.pop()
        rel_path = (posixpath.dirname(owner) + "/_rels/" + posixpath.basename(owner) + ".rels").lstrip("/") if owner else "_rels/.rels"
        if rel_path not in parts:
            continue
        keep.add(rel_path)
        for rel in ET.fromstring(parts[rel_path]):
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            dest = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target)).lstrip("/") if not target.startswith("/") else target.lstrip("/")
            if dest in parts and dest not in keep:
                keep.add(dest)
                queue.append(dest)
    result = {name: data for name, data in parts.items() if name in keep}
    ct = ET.fromstring(result["[Content_Types].xml"])
    for entry in list(ct):
        if entry.get("PartName") and entry.get("PartName").lstrip("/") not in keep:
            ct.remove(entry)
    result["[Content_Types].xml"] = ET.tostring(ct, encoding="UTF-8", xml_declaration=True, standalone=True)
    return result


def subset_embedded_fonts(parts: dict[str, bytes]) -> None:
    """Subset large EOT fonts to Latin, Cyrillic, Greek, punctuation and math.

    Used only by the offline preparation script. Runtime compression needs PIL
    and lxml, already installed by this application's requirements.
    """
    from fontTools import subset
    from fontTools.ttLib import TTFont

    codepoints = set(range(0x530)) | set(range(0x1E00, 0x1F00)) | set(range(0x2000, 0x2300))
    for name, data in list(parts.items()):
        if not name.endswith(".fntdata") or len(data) < 1_000_000:
            continue
        eot_size, font_size = struct.unpack("<II", data[:8])
        if eot_size != len(data) or font_size <= 0 or font_size > len(data):
            continue
        offset = len(data) - font_size
        font = TTFont(io.BytesIO(data[offset:]))
        options = subset.Options()
        options.name_IDs = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=codepoints)
        sub.subset(font)
        buffer = io.BytesIO()
        font.save(buffer)
        compact = buffer.getvalue()
        header = bytearray(data[:offset])
        struct.pack_into("<II", header, 0, offset + len(compact), len(compact))
        check = TTFont(io.BytesIO(compact))["head"].checkSumAdjustment
        struct.pack_into("<I", header, 60, check)
        parts[name] = bytes(header) + compact


def compact_images(parts: dict[str, bytes], max_dimension: int = 1600, quality: int = 82, colors: int = 256) -> None:
    for name, data in list(parts.items()):
        if not name.startswith("ppt/media/") or Path(name).suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        with Image.open(io.BytesIO(data)) as loaded:
            im = ImageOps.exif_transpose(loaded)
            im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            if Path(name).suffix.lower() in (".jpeg", ".jpg"):
                im.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, progressive=True)
            else:
                im = im.convert("RGBA")
                # Keep the alpha channel. Vector SVG artwork is never rasterized.
                im.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).save(buffer, "PNG", optimize=True)
            if len(buffer.getvalue()) < len(data):
                parts[name] = buffer.getvalue()


def write_package(parts: dict[str, bytes], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pptx-", suffix=".tmp", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with ZipFile(temp_path, "w", ZIP_DEFLATED, compresslevel=9) as package:
            for name in sorted(parts):
                package.writestr(name, parts[name])
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def optimize_pptx(path: str | Path, max_bytes: int = 5_000_000) -> Path:
    """Compact a generated deck and enforce the user's decimal 5 MB ceiling."""
    path = Path(path)
    with ZipFile(path) as package:
        parts = prune_parts({name: package.read(name) for name in package.namelist()})
    for dimension, quality, colors in ((1600, 82, 256), (1280, 76, 192), (1024, 70, 128), (800, 65, 96)):
        compact_images(parts, dimension, quality, colors)
        write_package(parts, path)
        if path.stat().st_size < max_bytes:
            return path
    raise ValueError(f"PPTX hajmi {max_bytes:,} baytdan kichik bo‘lmadi: {path.name}")
