from __future__ import annotations

import sys
import os
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QBuffer, QIODevice, Signal
from PySide6.QtGui import QAction, QIcon, QImage, QPixmap, QKeySequence, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QAbstractItemView, QSplitter,
    QScrollArea, QFileDialog, QMessageBox, QInputDialog, QComboBox,
    QCheckBox, QFrame, QDialog, QDialogButtonBox, QLineEdit, QSpinBox,
)
from .core import Library, IMAGE_EXTENSIONS, rotate_pages, parse_pages
from . import __version__, __author__, __url__

FILTER = '办公文档 (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;PDF (*.pdf);;所有文件 (*)'
STYLE = '''
QWidget { font-family: "Microsoft YaHei"; font-size: 13px; color: #263246; }
QMainWindow, QDialog { background: #f5f6f8; }
QPushButton { background: white; border: 1px solid #dfe3e9; border-radius: 8px; padding: 8px 13px; }
QPushButton:hover { background: #eef4ff; border-color: #b1cbf5; }
QPushButton:pressed { background: #dce9ff; }
QPushButton:disabled { color: #a3aab6; background: #f4f5f7; }
QPushButton#primary { background: #2478ed; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #1764d3; }
QPushButton#primary:disabled { background: #a9c7f2; }
QListWidget { background: #fbfcfe; border: none; outline: none; padding: 8px; }
QListWidget::item { border-radius: 9px; padding: 10px; margin: 3px; border: 1px solid transparent; }
QListWidget::item:selected { background: #e5efff; border-color: #a6c8fb; color: #155ebc; }
QListWidget::item:hover { background: #f0f4fa; }
QComboBox, QLineEdit, QSpinBox { background: white; border: 1px solid #dfe3e9; border-radius: 6px; padding: 6px; }
QComboBox::drop-down { border: none; width: 22px; }
QCheckBox { spacing: 7px; }
QScrollArea { border: none; background: #e9ecf1; }
QLabel#muted { color: #7a8596; }
QLabel#title { font-size: 25px; font-weight: 700; }
QFrame#bar { background: #ffffff; border-bottom: 1px solid #e5e8ee; }
QStatusBar { background: #f9fafc; border-top: 1px solid #e5e8ee; color: #788395; }
QSplitter::handle { background: #e1e5ec; width: 1px; }
'''


def configure_app(app):
    # Qt's offscreen Windows platform does not enumerate system fonts itself.
    # Use installed fonts only; no Microsoft font is redistributed.
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for name in ('msyh.ttc', 'msyhbd.ttc'):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)


class PageList(QListWidget):
    filesDropped = Signal(list)
    moved = Signal()

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setIconSize(QSize(78, 100))
        self.setSpacing(2)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.filesDropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
            self.moved.emit()


class ImportDialog(QDialog):
    def __init__(self, parent, count, total, current):
        super().__init__(parent)
        self.setWindowTitle('添加 PDF 页面')
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(QLabel(f'此 PDF 共 {count} 页'))
        self.range = QLineEdit()
        self.range.setPlaceholderText('留空添加全部；例如 1,3-5')
        layout.addWidget(self.range)
        layout.addWidget(QLabel('插入位置'))
        self.position = QSpinBox()
        self.position.setRange(1, total + 1)
        self.position.setValue(current + 2 if current >= 0 else total + 1)
        self.position.setSuffix('  页之前（最大值表示末尾）')
        layout.addWidget(self.position)
        self.selected = []
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('添加页面')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(lambda: self.validate(count))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self, count):
        try:
            self.selected = parse_pages(self.range.text(), count)
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, '请检查页码', str(exc))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = Library()
        self.pages = []
        self.undo_stack, self.redo_stack = [], []
        self.saved_state = ((), False, False)
        self.rebuilding = False
        self.thumbnails = OrderedDict()
        self.zoom = 0.0
        self.preview_pixmap = None
        self.preview_key = None
        self.setWindowTitle('轻页 PaperDesk')
        assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets'
        self.setWindowIcon(QIcon(str(assets / 'PaperDesk.ico')))
        self.resize(1180, 820)
        self.setMinimumSize(960, 640)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName('bar')
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 16, 24, 16)
        brand = QVBoxLayout()
        title = QLabel('轻页')
        title.setObjectName('title')
        brand.addWidget(title)
        subtitle = QLabel(f'PaperDesk v{__version__}  /  作者：{__author__}')
        subtitle.setObjectName('muted')
        brand.addWidget(subtitle)
        row.addLayout(brand)
        row.addStretch()
        self.button(row, '添加文件', self.open_files, 'Ctrl+O')
        self.button(row, '粘贴图片', self.paste, 'Ctrl+V')
        self.export_button = self.button(row, '导出 PDF', self.export, 'Ctrl+S', primary=True)
        layout.addWidget(header)

        settings = QHBoxLayout()
        settings.setContentsMargins(24, 12, 24, 12)
        settings.addWidget(QLabel('纸张'))
        self.orientation = QComboBox()
        self.orientation.addItems(['A4 纵向', 'A4 横向'])
        settings.addWidget(self.orientation)
        self.preserve = QCheckBox('保留原 PDF 页面尺寸')
        settings.addWidget(self.preserve)
        settings.addStretch()
        self.button(settings, '撤销', self.undo, 'Ctrl+Z')
        self.button(settings, '重做', self.redo, 'Ctrl+Shift+Z')
        self.button(settings, '新建', self.new_document, 'Ctrl+N')
        layout.addLayout(settings)

        splitter = QSplitter()
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(10, 8, 10, 8)
        caption = QLabel('  页面列表 · 拖动排序')
        caption.setObjectName('muted')
        side_layout.addWidget(caption)
        self.list = PageList()
        side_layout.addWidget(self.list)
        side_layout.addWidget(QLabel('  Ctrl / Shift 多选页面'))
        splitter.addWidget(side)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        tools = QHBoxLayout()
        tools.setContentsMargins(14, 8, 14, 8)
        self.edit_buttons = []
        for text, callback, shortcut in [
            ('左转 90°', lambda: self.rotate(-90), 'Ctrl+L'),
            ('右转 90°', lambda: self.rotate(90), 'Ctrl+R'),
            ('前移', lambda: self.move(-1), 'Alt+Up'),
            ('后移', lambda: self.move(1), 'Alt+Down'),
            ('删除', self.delete, 'Delete')]:
            self.edit_buttons.append(self.button(tools, text, callback, shortcut))
        tools.addStretch()
        preview_layout.addLayout(tools)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.preview = QLabel('把图片或 PDF 拖到这里\n\n也可以点击「添加文件」，或按 Ctrl+V 粘贴图片\n\n整理 · 旋转 · 合并 · 导出')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet('background: #e9ecf1; color: #7c8899; font-size: 16px;')
        self.scroll.setWidget(self.preview)
        preview_layout.addWidget(self.scroll)
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 8)
        self.page_label = QLabel('尚未添加页面')
        footer.addWidget(self.page_label)
        footer.addStretch()
        self.button(footer, '−', lambda: self.change_zoom(-0.25))
        self.zoom_label = QLabel('适合窗口')
        footer.addWidget(self.zoom_label)
        self.button(footer, '+', lambda: self.change_zoom(0.25))
        self.button(footer, '适合窗口', self.fit)
        preview_layout.addLayout(footer)
        splitter.addWidget(preview_panel)
        splitter.setSizes([275, 905])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        layout.addWidget(splitter, 1)
        self.statusBar().showMessage('本机离线处理  ·  默认另存为，保留原文件')
        self.list.filesDropped.connect(self.import_files)
        self.list.moved.connect(self.reordered)
        self.list.currentRowChanged.connect(self.render_preview)
        self.list.itemSelectionChanged.connect(self.update_actions)
        self.orientation.currentIndexChanged.connect(self.settings_changed)
        self.preserve.toggled.connect(self.settings_changed)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_preview)
        self.thumb_timer = QTimer(self)
        self.thumb_timer.timeout.connect(self.fill_thumbnail)
        self.thumb_timer.start(35)
        menu = self.menuBar().addMenu('帮助')
        about = menu.addAction('关于与使用说明')
        about.triggered.connect(self.about)
        self.update_actions()

    def button(self, layout, text, callback, shortcut=None, primary=False):
        button = QPushButton(text)
        if primary:
            button.setObjectName('primary')
        button.clicked.connect(callback)
        if shortcut:
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
            button.setToolTip(shortcut)
        layout.addWidget(button)
        return button

    def state(self):
        return (tuple(self.pages), self.preserve.isChecked(), self.orientation.currentIndex() == 1)

    def checkpoint(self):
        self.undo_stack.append(self.state())
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()

    def restore(self, state):
        pages, preserve, landscape = state
        self.pages = list(pages)
        self.preserve.blockSignals(True)
        self.orientation.blockSignals(True)
        self.preserve.setChecked(preserve)
        self.orientation.setCurrentIndex(int(landscape))
        self.preserve.blockSignals(False)
        self.orientation.blockSignals(False)
        self.rebuild()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.state())
            self.restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.state())
            self.restore(self.redo_stack.pop())

    def settings_changed(self):
        # The signal fires after changing the control. Reconstruct prior settings.
        self.undo_stack.append((tuple(self.pages), *self.last_settings))
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        self.last_settings = self.state()[1:]
        self.preview_key = None
        self.render_preview()
        self.update_actions()

    def selected(self):
        return sorted(self.list.row(x) for x in self.list.selectedItems())

    def update_actions(self):
        self.last_settings = self.state()[1:]
        self.export_button.setEnabled(bool(self.pages))
        for button in self.edit_buttons:
            button.setEnabled(bool(self.selected()))
        dirty = self.state() != self.saved_state
        self.setWindowTitle(('● ' if dirty else '') + '轻页 PaperDesk')

    def rebuild(self, select=None):
        self.rebuilding = True
        current = self.list.currentRow() if select is None else select
        self.list.clear()
        for i, page in enumerate(self.pages):
            item = QListWidgetItem(f'{i + 1:02d}   {page.label}\n原第 {page.number + 1} 页  ·  {page.rotation}°')
            item.setData(Qt.ItemDataRole.UserRole, page.uid)
            item.setToolTip(page.label)
            item.setSizeHint(QSize(215, 118))
            self.list.addItem(item)
        self.rebuilding = False
        if self.pages:
            self.list.setCurrentRow(max(0, min(current, len(self.pages)-1)))
        self.preview_key = None
        self.render_preview()
        self.update_actions()

    def thumbnail_key(self, page):
        return (page.source, page.number, page.rotation, *self.state()[1:])

    def pixmap(self, page, width, height):
        with self.library.document([page], *self.state()[1:]) as doc:
            bounds = doc[0].rect
            scale = min(width / bounds.width, height / bounds.height)
            pix = doc[0].get_pixmap(matrix=__import__('pymupdf').Matrix(scale, scale), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def fill_thumbnail(self):
        for i, page in enumerate(self.pages):
            item = self.list.item(i)
            key = self.thumbnail_key(page)
            if item.data(Qt.ItemDataRole.UserRole + 1) == key:
                continue
            try:
                if key not in self.thumbnails:
                    self.thumbnails[key] = self.pixmap(page, 78, 100)
                    if len(self.thumbnails) > 128:
                        self.thumbnails.popitem(last=False)
                item.setIcon(QIcon(self.thumbnails[key]))
                item.setData(Qt.ItemDataRole.UserRole + 1, key)
            except Exception as exc:
                item.setToolTip(f'预览失败：{exc}')
                item.setData(Qt.ItemDataRole.UserRole + 1, key)
            break

    def render_preview(self, *_):
        if self.rebuilding:
            return
        index = self.list.currentRow()
        if index < 0 or not self.pages:
            self.preview.clear()
            self.preview.setMinimumSize(1, 1)
            self.preview.setText('把图片或 PDF 拖到这里\n\n也可以点击「添加文件」，或按 Ctrl+V 粘贴图片\n\n整理 · 旋转 · 合并 · 导出')
            self.page_label.setText('尚未添加页面')
            return
        available = self.scroll.viewport().size()
        w, h = max(100, available.width()-56), max(100, available.height()-48)
        if self.zoom:
            w, h = int(595 * self.zoom), int(842 * self.zoom)
        key = (self.thumbnail_key(self.pages[index]), w, h)
        if key != self.preview_key:
            try:
                pix = self.pixmap(self.pages[index], min(w, 3000), min(h, 4000))
                self.preview.setPixmap(pix)
                self.preview.setMinimumSize(pix.width()+40 if self.zoom else 1, pix.height()+40 if self.zoom else 1)
                self.preview_key = key
            except Exception as exc:
                self.preview.setText('此页无法预览：' + str(exc))
        self.page_label.setText(f'第 {index+1} / {len(self.pages)} 页  ·  导出效果预览')
        self.zoom_label.setText(f'{int(self.zoom*100)}%' if self.zoom else '适合窗口')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'render_timer'):
            self.render_timer.start(120)

    def change_zoom(self, delta):
        self.zoom = max(0.25, min(4, (self.zoom or 1) + delta))
        self.render_preview()

    def fit(self):
        self.zoom = 0
        self.preview.setMinimumSize(1, 1)
        self.render_timer.start(0)

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '添加图片或 PDF', '', FILTER)
        self.import_files(paths)

    def import_files(self, paths):
        if not paths:
            return
        added, failures = [], []
        position = self.list.currentRow()+1 if self.list.currentRow() >= 0 else len(self.pages)
        for filename in paths:
            try:
                path = Path(filename)
                data = path.read_bytes()
                if path.suffix.lower() == '.pdf':
                    import pymupdf
                    with pymupdf.open(stream=data, filetype='pdf') as check:
                        password = ''
                        if check.needs_pass:
                            password, ok = QInputDialog.getText(self, 'PDF 密码', path.name, QLineEdit.EchoMode.Password)
                            if not ok:
                                continue
                    candidates = self.library.add_pdf(data, path.name, password)
                    if len(paths) == 1:
                        dialog = ImportDialog(self, len(candidates), len(self.pages), self.list.currentRow())
                        if not dialog.exec():
                            self.library.documents.pop(candidates[0].source).close()
                            continue
                        added.extend(candidates[i] for i in dialog.selected)
                        position = dialog.position.value()-1
                    else:
                        added.extend(candidates)
                elif path.suffix.lower() in IMAGE_EXTENSIONS:
                    added.extend(self.library.add_image(data, path.name))
                else:
                    raise ValueError('不支持此格式，请选择 PDF 或常见图片。')
            except Exception as exc:
                failures.append(f'{Path(filename).name}：{exc}')
        if added:
            self.checkpoint()
            self.pages[position:position] = added
            self.rebuild(position)
            self.statusBar().showMessage(f'已添加 {len(added)} 页  ·  可拖动排序、旋转和删除')
        if failures:
            QMessageBox.warning(self, '部分文件未能添加', '\n'.join(failures))

    def paste(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if image.isNull():
                return
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, 'PNG')
            try:
                pages = self.library.add_image(bytes(buffer.data()), '粘贴图片.png')
                self.checkpoint()
                position = self.list.currentRow()+1 if self.pages else 0
                self.pages[position:position] = pages
                self.rebuild(position)
            except Exception as exc:
                QMessageBox.warning(self, '粘贴失败', str(exc))
        elif mime.hasUrls():
            self.import_files([u.toLocalFile() for u in mime.urls() if u.isLocalFile()])
        else:
            self.statusBar().showMessage('剪贴板中没有图片。请先截图或复制图片，再粘贴。', 6000)

    def rotate(self, degrees):
        if self.selected():
            indices = self.selected()
            self.checkpoint()
            self.pages = rotate_pages(self.pages, indices, degrees)
            self.rebuild(indices[0])
            for i in indices:
                self.list.item(i).setSelected(True)

    def delete(self):
        selected = self.selected()
        if selected:
            self.checkpoint()
            self.pages = [p for i, p in enumerate(self.pages) if i not in selected]
            self.rebuild(min(selected))

    def move(self, direction):
        indices = self.selected()
        if not indices or (direction < 0 and indices[0] == 0) or (direction > 0 and indices[-1] == len(self.pages)-1):
            return
        self.checkpoint()
        for i in (indices if direction < 0 else reversed(indices)):
            self.pages[i], self.pages[i+direction] = self.pages[i+direction], self.pages[i]
        self.rebuild(indices[0]+direction)
        for i in indices:
            self.list.item(i+direction).setSelected(True)

    def reordered(self):
        by_id = {p.uid: p for p in self.pages}
        order = [by_id[self.list.item(i).data(Qt.ItemDataRole.UserRole)] for i in range(self.list.count())]
        if order != self.pages:
            self.checkpoint()
            selected_ids = {p.data(Qt.ItemDataRole.UserRole) for p in self.list.selectedItems()}
            self.pages = order
            self.rebuild()
            for i, page in enumerate(order):
                self.list.item(i).setSelected(page.uid in selected_ids)

    def export(self):
        if not self.pages:
            return False
        filename, _ = QFileDialog.getSaveFileName(self, '导出 PDF', '整理后的文档.pdf', 'PDF (*.pdf)')
        if not filename:
            return False
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
            if Path(filename).exists() and QMessageBox.question(self, '覆盖文件', '文件已存在，是否覆盖？') != QMessageBox.StandardButton.Yes:
                return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.library.export(self.pages, filename, *self.state()[1:])
            self.saved_state = self.state()
            self.update_actions()
            self.statusBar().showMessage(f'已导出 {len(self.pages)} 页：{filename}')
            return True
        except Exception as exc:
            QMessageBox.warning(self, '导出失败', f'请确认文件未被其他软件占用，且目录可以写入。\n\n{exc}')
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def can_discard(self):
        if self.state() == self.saved_state:
            return True
        box = QMessageBox(self)
        box.setWindowTitle('保存整理结果')
        box.setText('还有未导出的更改，是否先导出 PDF？')
        save = box.addButton('导出 PDF', QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton('放弃更改', QMessageBox.ButtonRole.DestructiveRole)
        box.addButton('取消', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == save:
            return bool(self.export())
        return box.clickedButton() == discard

    def new_document(self):
        if self.can_discard():
            self.library.close()
            self.pages = []
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.thumbnails.clear()
            self.saved_state = self.state()
            self.rebuild()

    def closeEvent(self, event):
        if self.can_discard():
            self.library.close()
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.import_files([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()

    def about(self):
        QMessageBox.information(self, '关于轻页',
            f'轻页 PaperDesk v{__version__}\n作者：{__author__}\n{__url__}\n'
            '本项目通过 AI 辅助完成，由作者确定需求并进行使用验证。\n\n'
            '图片与 PDF 页面整理工具 · 全部在本机处理\n'
            '添加 → 排序 / 旋转 / 删除 → 导出 PDF\n'
            '单独添加 PDF 时可选择页码和插入位置。\n'
            '图片默认一图一页，等比例放入 A4，不裁切。\n\n'
            '备注和表单会保留可见外观，导出后不再可编辑；\n'
            '不保留书签、附件、数字签名及交互链接。\n'
            '多帧图片只导入第一帧。不含 OCR 与文字编辑。\n\n'
            '开源许可：AGPL-3.0-or-later\nPyMuPDF / PySide6 / Pillow')


def main():
    app = QApplication(sys.argv)
    configure_app(app)
    app.setApplicationName('轻页 PaperDesk')
    window = Window()
    window.show()
    paths = [p for p in sys.argv[1:] if Path(p).is_file()]
    if paths:
        QTimer.singleShot(0, lambda: window.import_files(paths))
    sys.exit(app.exec())
