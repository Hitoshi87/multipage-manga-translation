"""UTF-8 interchange and lightweight TXT/DOCX translation import."""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def import_text(path):
    path = Path(path)
    if path.suffix.lower() == ".txt":
        raw = path.read_bytes()
        if len(raw) > 5_000_000:
            raise ValueError("TXT vượt giới hạn 5 MB")
        return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    if path.suffix.lower() != ".docx":
        raise ValueError("Chỉ nhận TXT UTF-8/UTF-16 hoặc DOCX")
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("word/document.xml")
        if info.file_size > 10_000_000:
            raise ValueError("Nội dung DOCX vượt giới hạn 10 MB")
        xml = archive.read(info)
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise ValueError("DOCX chứa XML không được hỗ trợ")
    root = ET.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(ns + "p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == ns + "t":
                parts.append(node.text or "")
            elif node.tag in (ns + "br", ns + "cr"):
                parts.append("\n")
            elif node.tag == ns + "tab":
                parts.append(" ")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def parse_translations(text):
    """One utterance per nonempty line; literal \\n is an intentional soft break."""
    pages = {}
    page = 1
    marked = False
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line:
            continue
        marker = re.fullmatch(r"(?:\[(?:PAGE|Trang)\s+(\d+)\]|(\d+))", line, re.I)
        if marker:
            new_page = int(marker.group(1) or marker.group(2))
            if new_page < 1:
                raise ValueError("Số trang phải từ 1 trở lên")
            if str(new_page) in pages and pages[str(new_page)]:
                raise ValueError(f"Đánh dấu trang {new_page} bị lặp")
            page, marked = new_page, True
            pages.setdefault(str(page), [])
        else:
            pages.setdefault(str(page), []).append(line.replace("\\n", "\n"))
    return {"pages": pages, "marked": marked,
            'filename_pages': bool(re.search(r'\[Trang\s+\d+\]', text, re.I))}


def import_translation_folder(path):
    """Choose polished per chapter; reject overlapping pages rather than merge silently."""
    folder = Path(path)
    chosen = {}
    for file in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if file.suffix.lower() not in ('.txt', '.docx') or file.name.startswith('~$'):
            continue
        key = re.sub(r'_polished$', '', file.stem, flags=re.I).casefold()
        if key not in chosen or file.stem.casefold().endswith('_polished'):
            chosen[key] = file
    pages, files = {}, []
    for file in chosen.values():
        parsed = parse_translations(import_text(file))
        if not parsed['marked']:
            raise ValueError('Thư mục cần marker [Trang N]/[PAGE N]: '+file.name)
        for key, lines in parsed['pages'].items():
            if key in pages:
                raise ValueError('Trùng trang '+key+' trong thư mục bản dịch')
            pages[key] = lines
        files.append(str(file))
    if not files:
        raise ValueError('Không có TXT/DOCX trong thư mục')
    # Folder imports always use filename numbers, never ordinal fallback.
    text = '\n\n'.join('[Trang '+key+']\n'+'\n'.join(v.replace('\n', '\\n') for v in pages[key])
                         for key in sorted(pages, key=int))
    return {'text': text, 'files': files, **parse_translations(text)}


def checked_mapping(manifest, mapping):
    regions = {r["id"]: r for r in manifest["regions"]}
    seen = set()
    output = []
    for item in mapping:
        key = item.get("id")
        if key not in regions or key in seen:
            raise ValueError(f"ID vùng không hợp lệ hoặc lặp: {key}")
        seen.add(key)
        text = item.get("translation", "")
        if not isinstance(text, str):
            raise ValueError("Bản dịch phải là chuỗi Unicode")
        role = item.get("font_role", "auto")
        if role not in ("auto", "dialogue", "box", "shout"):
            raise ValueError("Kiểu font vùng không hợp lệ")
        if text.strip():
            output.append({"id": key, "translation": text, "clean": bool(item.get("clean", True)), "force": item.get("force") is True, "font_role": role})
    return output


def validate_manifest(manifest):
    """Reject corrupt geometry before reading masks or allocating a clean canvas."""
    if manifest.get("schema") != 1:
        raise ValueError("Schema manifest không được hỗ trợ")
    def integer(value):
        return type(value) is int and value >= 0
    width, height = manifest.get("width"), manifest.get("height")
    if not integer(width) or not integer(height) or min(width, height) < 1:
        raise ValueError("Kích thước manifest không hợp lệ")
    analysis_size=manifest.get('analysis_size',[width,height])
    if not isinstance(analysis_size,list) or len(analysis_size)!=2 or not all(integer(v) and v>0 for v in analysis_size) or analysis_size[0]>width or analysis_size[1]>height:
        raise ValueError('Kích thước phân tích không hợp lệ')
    regions = manifest.get("regions")
    if not isinstance(regions, list):
        raise ValueError("Danh sách vùng không hợp lệ")
    ids = set()
    for region in regions:
        key = region.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"B[0-9]+", key) or key in ids:
            raise ValueError("ID vùng không hợp lệ hoặc lặp")
        ids.add(key)
        for name in ("box", "safe"):
            rect = region.get(name)
            if not isinstance(rect, list) or len(rect) != 4 or not all(integer(v) for v in rect):
                raise ValueError("Tọa độ vùng không hợp lệ")
            x, y, w, h = rect
            if min(w, h) < 1 or x + w > width or y + h > height:
                raise ValueError("Vùng vượt kích thước trang")
        x, y, w, h = region["box"]
        sx, sy, sw, sh = region["safe"]
        if sx < x or sy < y or sx + sw > x + w or sy + sh > y + h:
            raise ValueError("Vùng an toàn nằm ngoài bong bóng")
        fill = region.get("fill")
        if not isinstance(fill, list) or len(fill) != 3 or not all(integer(v) and v <= 255 for v in fill):
            raise ValueError("Màu clean không hợp lệ")
        if type(region.get("auto_clean")) is not bool:
            raise ValueError("Cờ clean không hợp lệ")
        if 'analysis_geometry' in region:
            geometry=region['analysis_geometry']
            if not isinstance(geometry,dict):raise ValueError('Hình học phân tích không hợp lệ')
            box=geometry.get('box');outline=geometry.get('outline')
            if not isinstance(box,list) or len(box)!=4 or not all(integer(v) for v in box) or min(box[2:])<1 or box[0]+box[2]>analysis_size[0] or box[1]+box[3]>analysis_size[1]:
                raise ValueError('Khung phân tích vượt ảnh')
            if not isinstance(outline,list) or not 3<=len(outline)<=10000 or any(not isinstance(p,list) or len(p)!=2 or not all(integer(v) for v in p) or not(box[0]<=p[0]<box[0]+box[2] and box[1]<=p[1]<box[1]+box[3]) for p in outline):
                raise ValueError('Biên phân tích không hợp lệ')
    return manifest
