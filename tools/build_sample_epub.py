#!/usr/bin/env python3
"""Build the approved chapters 1–3 sample from the canonical Chinese V1 EPUB."""

from __future__ import annotations

import argparse
import hashlib
import html
import posixpath
import re
import urllib.parse
import uuid
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


BOOK_TITLE = "爱与幻想的法西斯主义"
SAMPLE_TITLE = "爱与幻想的法西斯主义：V1 译文样章（第1—3章）"
AUTHOR = "村上龙"
TRANSLATOR = "郁江（Ikue）"
CHAPTER_FILES = [f"section-{number:03d}.xhtml" for number in range(1, 4)]
COPIED_FILES = ["style.css", "cover.svg", "cover.xhtml", "volume-1.xhtml", *CHAPTER_FILES]
RELEASE_TIMESTAMP = (2026, 10, 19, 1, 16, 34)
MODIFIED_UTC = "2026-10-18T17:16:34Z"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def xhtml(title: str, body: str, body_class: str = "") -> bytes:
    document = (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN" xml:lang="zh-CN">'
        f'<head><title>{esc(title)}</title><meta charset="utf-8"/>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>'
        f'<body class="{esc(body_class)}">{body}</body></html>'
    )
    return document.encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")

    with zipfile.ZipFile(source) as source_zip:
        source_names = set(source_zip.namelist())
        required = {f"OEBPS/{name}" for name in COPIED_FILES}
        required.update({"mimetype", "META-INF/container.xml", "OEBPS/content.opf"})
        missing = sorted(required - source_names)
        if missing:
            raise ValueError(f"Source EPUB is missing required files: {missing}")

        copied = {f"OEBPS/{name}": source_zip.read(f"OEBPS/{name}") for name in COPIED_FILES}

    chapter_links = "".join(
        f'<li><a href="{filename}">第{index}章</a></li>'
        for index, filename in enumerate(CHAPTER_FILES, 1)
    )
    title_body = (
        f"<h1>{esc(BOOK_TITLE)}</h1>"
        f'<p class="author">{esc(AUTHOR)}</p>'
        '<p class="subtitle">V1 译文样章 · 第1—3章</p>'
        f'<p class="center">译者、总审定：{esc(TRANSLATOR)}</p>'
        '<p class="center version">AI 辅助生成，人工核校与修订中</p>'
        '<h2>样章说明</h2>'
        '<p>本文件从项目现有中文 V1 译文中分出上卷第1至第3章，正文未作重新翻译。'
        'V1 尚在人工核校、审读与修订中，不是正式出版物，也不代表全书定稿。'
        '原作权利与中文译文及编校成果的权利分别处理；公开展示不构成开放许可。</p>'
    )
    nav_body = (
        '<nav epub:type="toc" id="toc"><h1>目录</h1><ol>'
        '<li><a href="title.xhtml">样章说明</a></li>'
        '<li><a href="volume-1.xhtml">上卷</a><ol>'
        f"{chapter_links}</ol></li></ol></nav>"
    )

    files = dict(copied)
    files["OEBPS/title.xhtml"] = xhtml(SAMPLE_TITLE, title_body)
    files["OEBPS/nav.xhtml"] = xhtml("目录", nav_body, "toc")

    identifier = "urn:uuid:" + str(
        uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/mizhidaili/fascism-of-love-and-fantasy-zh/releases/v1-sample-ch1-3")
    )
    order = 1
    ncx_points = (
        f'<navPoint id="n{order}" playOrder="{order}"><navLabel><text>上卷</text></navLabel>'
        '<content src="volume-1.xhtml"/>'
    )
    for index, filename in enumerate(CHAPTER_FILES, 1):
        order += 1
        ncx_points += (
            f'<navPoint id="n{order}" playOrder="{order}"><navLabel><text>第{index}章</text></navLabel>'
            f'<content src="{filename}"/></navPoint>'
        )
    ncx_points += "</navPoint>"
    files["OEBPS/toc.ncx"] = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f'<head><meta name="dtb:uid" content="{identifier}"/><meta name="dtb:depth" content="2"/>'
        '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
        f'<docTitle><text>{esc(SAMPLE_TITLE)}</text></docTitle><navMap>{ncx_points}</navMap></ncx>'
    ).encode("utf-8")

    manifest = [
        ("css", "style.css", "text/css", ""),
        ("cover-image", "cover.svg", "image/svg+xml", "cover-image"),
        ("cover", "cover.xhtml", "application/xhtml+xml", ""),
        ("title", "title.xhtml", "application/xhtml+xml", ""),
        ("vol-1", "volume-1.xhtml", "application/xhtml+xml", ""),
        *((f"section-{index:03d}", filename, "application/xhtml+xml", "") for index, filename in enumerate(CHAPTER_FILES, 1)),
        ("nav", "nav.xhtml", "application/xhtml+xml", "nav"),
        ("ncx", "toc.ncx", "application/x-dtbncx+xml", ""),
    ]
    spine = ["cover", "title", "vol-1", *(f"section-{index:03d}" for index in range(1, 4))]
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="zh-CN">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="book-id">{identifier}</dc:identifier><dc:title>{esc(SAMPLE_TITLE)}</dc:title>'
        f'<dc:creator>{esc(AUTHOR)}</dc:creator><dc:contributor>{esc(TRANSLATOR)}</dc:contributor>'
        '<dc:language>zh-CN</dc:language><dc:description>中文 V1 译文样章，第1至第3章；AI 辅助生成，人工核校与修订中。</dc:description>'
        '<dc:subject>中文译文样章</dc:subject><dc:rights>保留全部权利；公开展示不构成开放许可。</dc:rights>'
        f'<meta property="dcterms:modified">{MODIFIED_UTC}</meta><meta name="cover" content="cover-image"/></metadata><manifest>'
    )
    for item_id, href, media_type, properties in manifest:
        prop = f' properties="{properties}"' if properties else ""
        opf += f'<item id="{item_id}" href="{href}" media-type="{media_type}"{prop}/>'
    opf += "</manifest><spine toc=\"ncx\">" + "".join(f'<itemref idref="{item_id}"/>' for item_id in spine) + "</spine></package>"
    files["OEBPS/content.opf"] = opf.encode("utf-8")
    files["META-INF/container.xml"] = (
        '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        '</rootfiles></container>'
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as target_zip:
        mimetype_info = zipfile.ZipInfo("mimetype", RELEASE_TIMESTAMP)
        mimetype_info.compress_type = zipfile.ZIP_STORED
        mimetype_info.external_attr = 0o644 << 16
        target_zip.writestr(mimetype_info, "application/epub+zip")
        for name, data in files.items():
            info = zipfile.ZipInfo(name, RELEASE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            target_zip.writestr(info, data)

    validate(output)
    print(f"built={output}")
    print(f"sha256={sha256(output)}")


def validate(path: Path) -> None:
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = {info.filename for info in infos}
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            errors.append("mimetype must be first and uncompressed")
        bad_crc = archive.testzip()
        if bad_crc:
            errors.append(f"CRC failure: {bad_crc}")

        roots: dict[str, ET.Element] = {}
        for name in names:
            if name.endswith((".xml", ".xhtml", ".opf", ".ncx", ".svg")):
                try:
                    roots[name] = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    errors.append(f"{name}: XML parse failure: {exc}")

        ids = {name: {node.get("id") for node in root.iter() if node.get("id")} for name, root in roots.items()}
        for name, root in roots.items():
            for node in root.iter():
                for attribute in ("href", "src"):
                    href = node.get(attribute)
                    if not href or re.match(r"[a-z]+:", href):
                        continue
                    parsed = urllib.parse.urlsplit(href)
                    target = (
                        posixpath.normpath(posixpath.join(posixpath.dirname(name), urllib.parse.unquote(parsed.path)))
                        if parsed.path
                        else name
                    )
                    if target not in names:
                        errors.append(f"{name}: missing target {href}")
                    elif parsed.fragment and parsed.fragment not in ids.get(target, set()):
                        errors.append(f"{name}: missing anchor {href}")

        opf = roots.get("OEBPS/content.opf")
        if opf is None:
            errors.append("missing parsed OPF")
        else:
            ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
            manifest_ids = {item.get("id") for item in opf.findall("opf:manifest/opf:item", ns)}
            for itemref in opf.findall("opf:spine/opf:itemref", ns):
                if itemref.get("idref") not in manifest_ids:
                    errors.append(f"bad spine reference: {itemref.get('idref')}")
            if opf.findtext("opf:metadata/dc:language", namespaces=ns) != "zh-CN":
                errors.append("unexpected language metadata")

        unexpected_sections = sorted(
            name for name in names if re.fullmatch(r"OEBPS/section-\d{3}\.xhtml", name) and name not in {f"OEBPS/{item}" for item in CHAPTER_FILES}
        )
        if unexpected_sections:
            errors.append(f"unexpected chapter files: {unexpected_sections}")

    if errors:
        raise ValueError("; ".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
