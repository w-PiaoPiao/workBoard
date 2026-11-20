# -*- coding: utf-8 -*-
"""开源许可面板测试：文件发现、列表填充、逐份可读

Qt/PySide6 以 LGPLv3 分发，许可文本必须随包提供；这里覆盖「找得到、
读得出、列表能切」三件事——打包时 datas 路径写错（app/resources/licenses）
会在这里暴露成空列表。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PET_BOARD_DATA_DIR"] = tempfile.mkdtemp()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

_qapp = QApplication.instance() or QApplication([])

from app import i18n
from app.services import licensing
from app.views.license_dialog import LicenseDialog


class LicensingTest(unittest.TestCase):
    def test_finds_repo_root_in_source_run(self):
        root = licensing.license_root()
        self.assertIsNotNone(root)
        self.assertTrue((root / licensing.OWN_LICENSE_NAME).is_file())

    def test_documents_are_ordered_and_complete(self):
        docs = licensing.license_documents()
        kinds = [kind for _path, kind in docs]
        self.assertEqual(kinds[:2], ["notices", "own"])
        self.assertIn("LGPL-3.0", kinds)
        self.assertIn("GPL-3.0", kinds)
        # LGPL/GPL 紧随声明与本应用许可（排序权重 0/1）
        self.assertEqual(kinds[2:4], ["LGPL-3.0", "GPL-3.0"])

    def test_source_mode_ignores_non_license_txt(self):
        """源码运行时只认 LICENSES/，不能把 requirements.txt 当许可文档"""
        names = [p.name for p, _kind in licensing.license_documents()]
        self.assertNotIn("requirements.txt", names)
        self.assertEqual(len(names), 7)

    def test_every_document_is_readable_utf8(self):
        for path, _kind in licensing.license_documents():
            text = path.read_text(encoding="utf-8")
            self.assertGreater(len(text), 100, f"{path.name} 内容异常")


class LicenseDialogTest(unittest.TestCase):
    def setUp(self):
        self.dlg = LicenseDialog()

    def tearDown(self):
        self.dlg.deleteLater()
        i18n.set_lang("zh")

    def test_list_matches_documents(self):
        self.assertEqual(self.dlg._list.count(),
                         len(licensing.license_documents()))
        self.assertEqual(self.dlg._list.currentRow(), 0)

    def test_first_row_renders_notices(self):
        self.assertIn("MIT", self.dlg._text.toPlainText())
        # 第二行是本应用 MIT 许可全文
        self.dlg._list.setCurrentRow(1)
        self.assertIn("Permission is hereby granted",
                      self.dlg._text.toPlainText())

    def test_title_translates(self):
        self.assertEqual(self.dlg.windowTitle(), "开源许可")
        i18n.set_lang("en")
        dlg = LicenseDialog()
        try:
            self.assertEqual(dlg.windowTitle(), "Open-source licenses")
        finally:
            dlg.deleteLater()


if __name__ == "__main__":
    import unittest
    unittest.main()
