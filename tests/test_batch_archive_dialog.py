# -*- coding: utf-8 -*-
"""已完成列批量归档对话框：勾选、全选/清空、按钮态与结果回传"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PET_BOARD_DATA_DIR"] = tempfile.mkdtemp()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QDialog

_qapp = QApplication.instance() or QApplication([])

from app.models.board import Card                      # noqa: E402
from app.views.batch_archive_dialog import BatchArchiveDialog  # noqa: E402
from app.views.theme import AppTheme                   # noqa: E402


class BatchArchiveDialogTest(unittest.TestCase):
    def setUp(self):
        self.cards = [Card(title="甲"), Card(title="乙"), Card(title="丙")]
        self.cards[0].done = True
        self.cards[0].done_at = "2026-10-01T09:00:00+08:00"
        self.dlg = BatchArchiveDialog(self.cards)

    def tearDown(self):
        self.dlg.deleteLater()

    def test_defaults_to_nothing_selected(self):
        """归档是"离开看板"的动作：默认不替用户做决定"""
        self.assertEqual(self.dlg.selected_ids(), [])
        self.assertFalse(self.dlg._ok_btn.isEnabled())

    def test_select_all_and_clear(self):
        self.dlg._all_btn.click()
        self.assertEqual(self.dlg.selected_ids(),
                         [c.id for c in self.cards])
        self.assertTrue(self.dlg._ok_btn.isEnabled())
        self.assertFalse(self.dlg._all_btn.isEnabled())

        self.dlg._none_btn.click()
        self.assertEqual(self.dlg.selected_ids(), [])
        self.assertFalse(self.dlg._ok_btn.isEnabled())

    def test_partial_selection(self):
        self.dlg._boxes[1][0].setChecked(True)
        self.assertEqual(self.dlg.selected_ids(), [self.cards[1].id])
        self.assertIn("1", self.dlg._count_label.text())

    def test_accept_returns_selected_ids(self):
        self.dlg._boxes[0][0].setChecked(True)
        self.dlg._ok_btn.click()
        self.assertEqual(self.dlg.result(), QDialog.Accepted)
        self.assertEqual(self.dlg.selected_ids(), [self.cards[0].id])

    def test_tooltip_shows_done_date(self):
        """完成日期进 tooltip：批量归档前能看出这张是多久前收尾的"""
        box = self.dlg._boxes[0][0]
        self.assertIn("2026-10-01", box.toolTip())

    def test_reapply_theme_does_not_raise(self):
        for mode in ("light", "dark"):
            AppTheme.set_mode(mode)
            self.dlg.reapply_theme()
        AppTheme.set_mode("light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
