"""Packaged-runtime smoke check; only synthetic data is generated."""
import json
from io import BytesIO
from pathlib import Path

import pymupdf as pdf
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QItemSelectionModel
from .app import Window, configure_app


def run(directory):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    configure_app(app)
    window = Window()
    window.show()
    app.processEvents()
    window.grab().save(str(output / '界面-空白.png'))
    document = pdf.open()
    for index in range(3):
        page = document.new_page(width=595, height=842)
        page.insert_text((52, 90), 'PAPERDESK', fontsize=14, color=(.15,.45,.85))
        page.insert_text((52, 145), 'Office document / 2026', fontsize=25)
        page.insert_text((52, 183), f'Sample page {index+1} - Local PDF workspace', fontsize=12)
        for line in range(10):
            page.draw_line((52, 240+line*36), (535,240+line*36), color=(.86,.89,.94), width=.7)
        page.draw_rect(pdf.Rect(52,650,535,740), fill=(.92,.96,1), color=None)
        page.insert_text((72, 695), 'Preview. Arrange. Export.', fontsize=20, color=(.15,.45,.85))
    window.pages = window.library.add_pdf(document.tobytes(), '办公资料.pdf')
    document.close()
    image = Image.new('RGB', (1200,800), '#faf9f6')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70,60,1130,740), radius=20, fill='white', outline='#d8dee8', width=3)
    draw.rectangle((120,130,1080,180), fill='#2478ed')
    for y in range(260, 680, 70):
        draw.line((120,y,1080,y), fill='#d8dee8', width=3)
    data = BytesIO()
    image.save(data, 'PNG')
    window.pages += window.library.add_image(data.getvalue(), '横向图片.png')
    window.rebuild(3)
    for _ in window.pages:
        window.fill_thumbnail()
    app.processEvents()
    window.render_preview()
    window.grab().save(str(output / '界面-页面整理.png'))
    assert window.preview.pixmap().width() > window.preview.pixmap().height()
    window.set_orientation('portrait')
    for _ in window.pages:
        window.fill_thumbnail()
    app.processEvents()
    window.grab().save(str(output / '界面-手动纵向.png'))
    assert window.preview.pixmap().width() < window.preview.pixmap().height()
    window.rotate(90)
    assert window.pages[3].orientation == 'portrait'
    assert window.preview.pixmap().width() < window.preview.pixmap().height()
    window.undo()
    window.undo()
    assert window.pages[3].orientation == 'auto'
    clipboard = QImage(120,80,QImage.Format.Format_RGB32)
    clipboard.fill(QColor('white'))
    QApplication.clipboard().setImage(clipboard)
    app.processEvents()
    window.paste()
    assert len(window.pages) == 5
    window.undo()
    window.rotate(90)
    window.undo()
    window.list.setCurrentRow(0, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    window.library.export(window.pages, str(output / '混合导出-示例.pdf'))
    with pdf.open(output / '混合导出-示例.pdf') as exported:
        assert len(exported) == 4
        assert 'PAPERDESK' in exported[0].get_text()
        assert exported[0].rect.width < exported[0].rect.height
        assert exported[3].rect.width > exported[3].rect.height
        exported[0].get_pixmap(matrix=pdf.Matrix(1,1)).save(output / '导出-预览.png')
        exported[3].get_pixmap(matrix=pdf.Matrix(1,1)).save(output / '导出-横向.png')
    window.saved_state = window.state()
    window.close()
    (output / 'selfcheck.json').write_text(json.dumps({'status':'passed', 'pages':4,
        'checks':['runtime','clipboard','undo','rotation','per-page A4 orientation',
                  'fixed portrait','mixed portrait/landscape export','searchable text','render']}, indent=2), encoding='utf-8')
