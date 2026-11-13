from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as pdf
from PIL import Image
from paperdesk.core import Library, A4, rotate_pages, parse_pages


def sample():
    doc = pdf.open()
    for i in range(3):
        page = doc.new_page(width=300 + i * 50, height=450)
        page.insert_text((30, 70), f'PAGE {i+1} - searchable text', fontsize=14)
        page.draw_rect(pdf.Rect(20, 20, 50, 40), fill=(1, 0, 0))
        page.draw_rect(pdf.Rect(220, 350, 260, 390), fill=(0, 0, 1))
    doc[1].set_rotation(90)
    data = doc.tobytes()
    doc.close()
    return data


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.lib = Library()
        self.pages = self.lib.add_pdf(sample(), '测试文档.pdf')
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_a4_text_order(self):
        selected = [self.pages[2], self.pages[0]]
        with self.lib.document(selected) as result:
            self.assertEqual(len(result), 2)
            for page in result:
                self.assertAlmostEqual(page.rect.width, A4[0], places=2)
                self.assertAlmostEqual(page.rect.height, A4[1], places=2)
            self.assertIn('PAGE 3', result[0].get_text())
            self.assertIn('PAGE 1', result[1].get_text())

    def test_preserve_size_and_rotation(self):
        rotated = rotate_pages(self.pages, [0, 1], 90)
        with self.lib.document(rotated, preserve=True) as result:
            self.assertEqual(result[0].rotation, 90)
            self.assertEqual(result[1].rotation, 180)
            self.assertEqual(result[0].rect.width, 450)

    def test_rotations_match_visual_direction(self):
        # Rendering at native scale should retain corner positions and orientation.
        for degrees in (0, 90, 180, 270):
            pages = rotate_pages(self.pages, [1], degrees)
            with self.lib.document([pages[1]], True) as original, self.lib.document([pages[1]]) as a4:
                target = a4[0]
                source = original[0]
                scale = min(target.rect.width/source.rect.width, target.rect.height/source.rect.height)
                w, h = source.rect.width * scale, source.rect.height * scale
                clip = pdf.Rect((target.rect.width-w)/2, (target.rect.height-h)/2,
                                (target.rect.width+w)/2, (target.rect.height+h)/2)
                left = source.get_pixmap(matrix=pdf.Matrix(1, 1))
                right = target.get_pixmap(matrix=pdf.Matrix(1/scale, 1/scale), clip=clip)
                # Compare colored marker centroids normalized to avoid edge rounding.
                def centroid(pix, red):
                    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                    pts = [(x, y) for y in range(im.height) for x in range(im.width)
                           if (lambda c: c[0] > 220 and c[2] < 40 if red else c[2] > 220 and c[0] < 40)(im.getpixel((x,y)))]
                    return (sum(x for x,y in pts)/len(pts)/im.width, sum(y for x,y in pts)/len(pts)/im.height)
                for red in (True, False):
                    a, b = centroid(left, red), centroid(right, red)
                    self.assertAlmostEqual(a[0], b[0], delta=.012)
                    self.assertAlmostEqual(a[1], b[1], delta=.012)

    def test_image_alpha_landscape_mixed(self):
        stream = BytesIO()
        Image.new('RGBA', (120, 80), (255, 0, 0, 128)).save(stream, 'PNG')
        image = self.lib.add_image(stream.getvalue(), '透明.png')
        with self.lib.document(image+self.pages, preserve=True, landscape=True) as result:
            self.assertEqual(len(result), 4)
            self.assertAlmostEqual(result[0].rect.width, A4[1], places=2)
            self.assertEqual(result[1].rect.width, 300)
            pix = result[0].get_pixmap()
            self.assertEqual(pix.pixel(0, 0), (255,255,255))

    def test_password(self):
        with pdf.open(stream=sample(), filetype='pdf') as doc:
            data = doc.tobytes(encryption=pdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret')
        with self.assertRaises(ValueError):
            self.lib.add_pdf(data, 'private.pdf')
        self.assertEqual(len(self.lib.add_pdf(data, 'private.pdf', 'secret')), 3)

    def test_atomic_export_failure_keeps_existing(self):
        path = Path(self.tmp.name) / '结果.pdf'
        path.write_bytes(b'original')
        with patch('paperdesk.core.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                self.lib.export(self.pages, str(path))
        self.assertEqual(path.read_bytes(), b'original')
        self.assertEqual(list(path.parent.glob('.paperdesk-*')), [])

    def test_restricted_pdf_requires_owner(self):
        with pdf.open(stream=sample(), filetype='pdf') as doc:
            data = doc.tobytes(encryption=pdf.PDF_ENCRYPT_AES_256,
                               owner_pw='owner', user_pw='reader', permissions=0)
        with self.assertRaisesRegex(ValueError, '限制修改'):
            self.lib.add_pdf(data, 'restricted.pdf', 'reader')
        self.assertEqual(len(self.lib.add_pdf(data, 'restricted.pdf', 'owner')), 3)

    def test_blank_page_and_exif_image(self):
        with pdf.open() as blank:
            blank.new_page()
            pages = self.lib.add_pdf(blank.tobytes(), 'blank.pdf')
        with self.lib.document(pages) as output:
            self.assertEqual(len(output), 1)
        stream = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (120,80), 'red').save(stream, 'JPEG', exif=exif)
        image = self.lib.add_image(stream.getvalue(), 'phone.jpg')[0]
        bounds = self.lib.documents[image.source][0].rect
        self.assertEqual((bounds.width,bounds.height), (80,120))

    def test_export_unicode_and_empty(self):
        path = Path(self.tmp.name) / '办公文档.pdf'
        self.lib.export(self.pages, str(path))
        with pdf.open(path) as doc:
            self.assertEqual(len(doc), 3)
        with self.assertRaises(ValueError):
            self.lib.export([], str(path))

    def test_ranges(self):
        self.assertEqual(parse_pages('1,3-5,3', 5), [0,2,3,4])
        self.assertEqual(parse_pages('', 3), [0,1,2])
        for value in ('0', '9', '4-2', 'a', '1-999999999'):
            with self.assertRaises(ValueError):
                parse_pages(value, 5)

    def test_annotation_appearance_preserved(self):
        with pdf.open(stream=sample(), filetype='pdf') as doc:
            doc[0].add_freetext_annot(pdf.Rect(50,100,200,150), 'VISIBLE NOTE', fontsize=12)
            pages = self.lib.add_pdf(doc.tobytes(), 'annotated.pdf')
        with self.lib.document(pages) as out:
            self.assertIn('VISIBLE NOTE', out[0].get_text())


if __name__ == '__main__':
    unittest.main()
