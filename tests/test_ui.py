import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtTest import QTest
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
        self.window.set_orientation('landscape')
        self.window.preserve.setChecked(True)
        self.window.undo()
        self.assertFalse(self.window.preserve.isChecked())
        self.assertEqual(self.window.pages[0].orientation, 'landscape')
        self.window.undo()
        self.assertEqual(self.window.pages[0].orientation, 'auto')

    def test_paper_buttons_apply_only_selected_and_keep_multiselection(self):
        self.window.list.item(1).setSelected(True)
        QTest.mouseClick(self.window.paper_buttons['landscape'], Qt.MouseButton.LeftButton)
        self.assertEqual([p.orientation for p in self.window.pages], ['landscape','landscape','auto'])
        self.assertEqual(self.window.selected(), [0,1])
        self.window.rotate(90)
        self.assertEqual(self.window.selected(), [0,1])
        self.assertEqual([p.orientation for p in self.window.pages], ['landscape','landscape','auto'])
        self.window.undo()
        self.window.undo()
        self.assertTrue(all(p.orientation == 'auto' for p in self.window.pages))
        self.window.redo()
        self.assertEqual(self.window.pages[1].orientation, 'landscape')

    def test_paper_controls_follow_selection_and_mixed_state(self):
        self.window.set_orientation('portrait')
        self.assertTrue(self.window.paper_buttons['portrait'].isChecked())
        self.window.list.setCurrentRow(1, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.assertTrue(self.window.paper_buttons['auto'].isChecked())
        self.window.list.item(0).setSelected(True)
        self.assertFalse(any(b.isChecked() for b in self.window.paper_buttons.values()))
        self.window.list.clearSelection()
        self.assertFalse(any(b.isEnabled() for b in self.window.paper_buttons.values()))

    def test_preserve_disables_only_original_pdf_controls(self):
        self.window.set_orientation('portrait')
        self.window.preserve.setChecked(True)
        self.assertFalse(any(b.isEnabled() for b in self.window.paper_buttons.values()))
        self.assertIn('原尺寸', self.window.page_label.text())
        self.assertIn('原尺寸', self.window.list.item(0).text())
        image = QImage(240,120,QImage.Format.Format_RGB32)
        image.fill(QColor('white'))
        QApplication.clipboard().setImage(image)
        app.processEvents()
        self.window.paste()
        self.assertEqual(len(self.window.pages), 4)
        self.assertTrue(self.window.paper_buttons['auto'].isEnabled())
        self.window.list.item(0).setSelected(True)
        self.window.set_orientation('landscape')
        self.assertEqual(self.window.pages[0].orientation, 'portrait')
        self.assertEqual(self.window.pages[1].orientation, 'landscape')

    def test_new_paste_auto_and_preview_cache_invalidation(self):
        self.window.show()
        app.processEvents()
        self.window.set_orientation('portrait')
        image = QImage(240,120,QImage.Format.Format_RGB32)
        image.fill(QColor('orange'))
        QApplication.clipboard().setImage(image)
        QTest.qWait(50)
        self.window.paste()
        self.assertEqual(len(self.window.pages), 4)
        page = self.window.pages[1]
        self.assertEqual(page.orientation, 'auto')
        pix = self.window.preview.pixmap()
        self.assertGreater(pix.width(),pix.height())
        before = self.window.preview_key
        self.window.set_orientation('portrait')
        self.assertNotEqual(self.window.preview_key,before)
        pix = self.window.preview.pixmap()
        self.assertLess(pix.width(),pix.height())
        self.window.rotate(90)
        self.assertEqual(self.window.pages[1].orientation,'portrait')
        self.window.set_orientation('auto')
        self.window.rotate(90)
        pix = self.window.preview.pixmap()
        self.assertGreater(pix.width(),pix.height())

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
