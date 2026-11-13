"""Local PDF page composition. No networking or persistent document storage."""
from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
import os
import tempfile
import uuid

import pymupdf as pdf
from PIL import Image, ImageOps
from . import __version__, __author__

A4 = (595.2756, 841.8898)
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}


@dataclass(frozen=True)
class Page:
    source: str
    number: int
    label: str
    rotation: int = 0
    uid: str = ''
    orientation: str = 'auto'
    is_image: bool = False


class Library:
    def __init__(self):
        self.documents: dict[str, pdf.Document] = {}

    def add_pdf(self, data: bytes, label: str, password: str = '') -> list[Page]:
        doc = pdf.open(stream=data, filetype='pdf')
        try:
            authentication = 0
            if doc.needs_pass:
                authentication = doc.authenticate(password)
                if not authentication:
                    raise ValueError('PDF 需要密码，或密码不正确。')
            if doc.is_encrypted:
                raise ValueError('无法解密此 PDF。')
            if not len(doc):
                raise ValueError('PDF 中没有页面。')
            if not (doc.permissions & pdf.PDF_PERM_MODIFY) and not (authentication & 4):
                raise ValueError('该 PDF 限制修改，请使用有修改权限的版本。')
            # Bake visible comments/form appearances, keeping page text as text.
            # This also makes resized and original-size exports behave consistently.
            doc.bake(annots=True, widgets=True)
            key = uuid.uuid4().hex
            self.documents[key] = doc
            return [Page(key, i, label, uid=uuid.uuid4().hex) for i in range(len(doc))]
        except Exception:
            doc.close()
            raise

    def add_image(self, data: bytes, label: str) -> list[Page]:
        with Image.open(BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                image = Image.new('RGB', rgba.size, 'white')
                image.paste(rgba, mask=rgba.getchannel('A'))
            else:
                image = image.convert('RGB')
            stream = BytesIO()
            image.save(stream, format='PNG')
            doc = pdf.open()
            # Physical image dimensions are only used before fitting to A4.
            w, h = image.size
            factor = min(1, 14400 / max(w, h))
            page = doc.new_page(width=max(1, w * factor), height=max(1, h * factor))
            page.insert_image(page.rect, stream=stream.getvalue())
            data_pdf = doc.tobytes()
            doc.close()
        return [replace(p, is_image=True) for p in self.add_pdf(data_pdf, label)]

    def page_size(self, item: Page, preserve: bool = False):
        """Visible dimensions include original PDF rotation and the user's rotation."""
        bounds = self.documents[item.source][item.number].rect
        w, h = bounds.width, bounds.height
        if item.rotation % 180:
            w, h = h, w
        if preserve and not item.is_image:
            return w, h
        if item.orientation not in ('auto', 'portrait', 'landscape'):
            raise ValueError('未知的纸张方向。')
        landscape = item.orientation == 'landscape' or (item.orientation == 'auto' and w > h)
        return A4[::-1] if landscape else A4

    def compose_page(self, output: pdf.Document, item: Page, preserve: bool = False):
        source = self.documents[item.source]
        single = pdf.open()
        try:
            single.insert_pdf(source, from_page=item.number, to_page=item.number)
            single[0].set_rotation((single[0].rotation + item.rotation) % 360)
            if preserve and not item.is_image:
                output.insert_pdf(single)
                return
            single[0].remove_rotation()
            w, h = self.page_size(item, preserve)
            target = output.new_page(width=w, height=h)
            if single[0].get_contents():
                target.show_pdf_page(target.rect, single, 0, keep_proportion=True)
        finally:
            single.close()

    def document(self, pages: list[Page], preserve=False):
        result = pdf.open()
        try:
            for page in pages:
                self.compose_page(result, page, preserve)
            return result
        except Exception:
            result.close()
            raise

    def export(self, pages: list[Page], destination: str, preserve=False):
        if not pages:
            raise ValueError('请先添加页面。')
        destination = str(Path(destination).absolute())
        fd, temporary = tempfile.mkstemp(prefix='.paperdesk-', suffix='.pdf', dir=Path(destination).parent)
        os.close(fd)
        try:
            with self.document(pages, preserve) as result:
                result.set_metadata({'title': Path(destination).stem,
                                     'creator': f'轻页 PaperDesk v{__version__} / {__author__}'})
                result.save(temporary, garbage=4, deflate=True)
            with pdf.open(temporary) as check:
                if len(check) != len(pages):
                    raise ValueError('导出页数校验失败。')
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def close(self):
        for doc in self.documents.values():
            doc.close()
        self.documents.clear()


def rotate_pages(pages: list[Page], indices: list[int], degrees: int):
    selected = set(indices)
    return [replace(p, rotation=(p.rotation + degrees) % 360) if i in selected else p
            for i, p in enumerate(pages)]


def parse_pages(text: str, count: int) -> list[int]:
    if not text.strip():
        return list(range(count))
    result = []
    for part in text.replace('，', ',').split(','):
        pieces = part.strip().split('-')
        if len(pieces) == 1:
            values = [int(pieces[0])]
        elif len(pieces) == 2:
            start, end = map(int, pieces)
            if start > end:
                raise ValueError('页码范围应从小到大。')
            if start < 1 or end > count:
                raise ValueError(f'页码应在 1 至 {count} 之间。')
            values = range(start, end + 1)
        else:
            raise ValueError('页码格式示例：1,3-5')
        for value in values:
            if not 1 <= value <= count:
                raise ValueError(f'页码应在 1 至 {count} 之间。')
            if value - 1 not in result:
                result.append(value - 1)
    return result
