import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from paperdesk.app import Window, configure_app
from tests.test_core import sample

app = QApplication.instance() or QApplication([])
configure_app(app)


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = Window()
        self.window.pages = self.window.library.add_pdf(sample(), '办公文档.pdf')
        self.window.rebuild(0)

    def tearDown(self):
        self.window.saved_state = self.window.state()
        self.window.close()

    def test_delete_undo_redo(self):
        self.window.delete()
        self.assertEqual(len(self.window.pages), 2)
        self.window.undo()
        self.assertEqual(len(self.window.pages), 3)
        self.window.redo()
        self.assertEqual(len(self.window.pages), 2)

    def test_settings_undo(self):
        self.window.preserve.setChecked(True)
        self.window.orientation.setCurrentIndex(1)
        self.window.undo()
        self.assertEqual(self.window.state()[1:], (True, False))
        self.window.undo()
        self.assertEqual(self.window.state()[1:], (False, False))

    def test_multiple_rotation(self):
        self.window.list.item(1).setSelected(True)
        self.window.rotate(90)
        self.assertEqual([p.rotation for p in self.window.pages], [90,90,0])
        self.window.undo()
        self.assertEqual([p.rotation for p in self.window.pages], [0,0,0])

    def test_move_reorder(self):
        uid = self.window.pages[0].uid
        self.window.move(1)
        self.assertEqual(self.window.pages[1].uid, uid)
        self.window.undo()
        self.assertEqual(self.window.pages[0].uid, uid)
        item = self.window.list.takeItem(0)
        self.window.list.insertItem(2, item)
        self.window.reordered()
        self.assertEqual(self.window.pages[2].uid, uid)

    def test_clipboard_real_image(self):
        image = QImage(150,100,QImage.Format.Format_RGB32)
        image.fill(QColor('orange'))
        QApplication.clipboard().setImage(image)
        self.window.paste()
        self.assertEqual(len(self.window.pages), 4)
        self.assertEqual(self.window.pages[1].label, '粘贴图片.png')

    def test_cancel_export_does_not_mark_saved(self):
        before = self.window.saved_state
        with patch('paperdesk.app.QFileDialog.getSaveFileName', return_value=('', '')):
            self.assertFalse(self.window.export())
        self.assertEqual(self.window.saved_state, before)


if __name__ == '__main__':
    unittest.main()
