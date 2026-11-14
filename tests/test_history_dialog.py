# -*- coding: utf-8 -*-
"""历史版本（启动快照）测试：清单枚举、对话框渲染、控制器恢复流程

控制器用 AppController.__new__ 轻量构造（照 test_restore_flow 先例），
手装 store/save_pool/timer，避免重量级构造与共享控制器互相污染。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PET_BOARD_DATA_DIR"] = tempfile.mkdtemp()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

_qapp = QApplication.instance() or QApplication([])

from app.models.board import Board, BoardList, Card
from app.models.board import BoardStore
from app.models import json_io
from app.views.history_dialog import HistoryDialog


def _doc(name: str, cards: int) -> dict:
    """构造一份最小合法看板文档（version 2）"""
    return {"app": "桌宠看板", "version": 2, "id": "a" * 32,
            "name": name, "saved_at": "2026-01-01T00:00:00",
            "lists": [{"id": "b" * 32, "title": "列", "cards": [
                {"title": f"卡{i}"} for i in range(cards)]}]}


class ListSnapshotsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "board.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_snapshot(self, doc: dict, tag: str | None = None) -> Path:
        if tag is None:
            ext = json_io.backup_ext("snap")   # ".snap.<时间戳>.bak"
            snap = self.path.with_name(self.path.name + ext)
        else:
            snap = self.path.with_name(f"{self.path.name}.snap.{tag}.bak")
        snap.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return snap

    def test_lists_snapshots_newest_first_with_summary(self):
        self._write_snapshot(_doc("早", 2), tag="20260101_000000_000000")
        self._write_snapshot(_doc("晚", 5), tag="20260102_000000_000000")
        items = json_io.list_snapshots(self.path)
        self.assertEqual(len(items), 2)
        # 名称时间戳排序保证"最新在前"
        self.assertEqual(items[0]["cards"], 5)
        self.assertEqual(items[1]["cards"], 2)
        self.assertEqual(items[0]["lists"], 1)
        self.assertFalse(items[0]["unreadable"])
        self.assertGreater(items[0]["size"], 0)
        self.assertEqual(items[0]["path"].suffix, ".bak")

    def test_corrupted_snapshot_marked_unreadable(self):
        snap = self.path.with_name(f"{self.path.name}.snap.20260101_000000_000000.bak")
        snap.write_text("{broken json", encoding="utf-8")
        items = json_io.list_snapshots(self.path)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["unreadable"])
        self.assertEqual(items[0]["cards"], -1)

    def test_empty_dir_returns_empty(self):
        self.assertEqual(json_io.list_snapshots(self.path), [])


class HistoryDialogTest(unittest.TestCase):
    def setUp(self):
        self.dlg = HistoryDialog()
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "board.json"

    def tearDown(self):
        self.dlg.close()
        self.dlg.deleteLater()
        self._tmp.cleanup()

    def test_render_rows_and_empty_state(self):
        self.dlg.set_items([])
        # 空态提示 + 末尾 stretch
        self.assertEqual(self.dlg._rows_layout.count(), 2)
        self.assertFalse(self.dlg._folder_btn.isEnabled())
        self.dlg.set_items(json_io.list_snapshots(self.path))   # 仍为空
        self.assertEqual(self.dlg._rows_layout.count(), 2)

    def test_rows_render_and_restore_signal_confirmed(self):
        snap = self.path.with_name(
            f"{self.path.name}.snap.20260101_000000_000000.bak")
        snap.write_text(json.dumps(_doc("板", 3), ensure_ascii=False),
                        encoding="utf-8")
        snap2 = self.path.with_name(
            f"{self.path.name}.snap.20260102_000000_000000.bak")
        snap2.write_text("{broken", encoding="utf-8")   # 损坏行
        self.dlg.set_items(json_io.list_snapshots(self.path))
        self.assertEqual(self.dlg._rows_layout.count(), 3)   # 2 行 + stretch
        self.assertTrue(self.dlg._folder_btn.isEnabled())

        # 损坏行的恢复按钮禁用（布局: stretch 在末尾）
        row0 = self.dlg._rows_layout.itemAt(0).widget()
        row1 = self.dlg._rows_layout.itemAt(1).widget()
        self.assertFalse(row0._restore_btn.isEnabled())     # 最新（损坏）
        self.assertTrue(row1._restore_btn.isEnabled())

        got = []
        self.dlg.signal_restore_requested.connect(got.append)
        with patch("app.views.history_dialog.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            row1._restore_btn.click()
        self.assertEqual(got, [str(snap)])

        # 用户取消：不发信号
        with patch("app.views.history_dialog.QMessageBox.question",
                   return_value=QMessageBox.No):
            row1._restore_btn.click()
        self.assertEqual(got, [str(snap)])


def _light_controller(store_path: Path):
    """轻量控制器：只装恢复路径触到的依赖（照 test_restore_flow 先例）"""
    from app.controllers.app_controller import AppController

    c = AppController.__new__(AppController)
    c._store = BoardStore(store_path)
    c._window = None
    c._history_dialog = None
    c._save_pool = QThreadPool()
    c._save_pool.setMaxThreadCount(1)
    c._save_timer = QTimer()
    c._save_timer.setSingleShot(True)
    c._save_timer.setInterval(500)
    notifications: list[str] = []
    c._notify = notifications.append
    c._apply_board_to_ui = lambda board: None
    c._refresh_archive = lambda: None
    c._refresh_calendar = lambda: None
    return c, notifications


class ControllerRestoreTest(unittest.TestCase):
    """端到端：快照 → 恢复 → 回读 + 恢复前自动留档"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self._tmp.name) / "board.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_board(self, title: str) -> Board:
        board = Board(name="测试板")
        lst = BoardList(title=title)
        lst.cards.append(Card(title=f"{title}卡"))
        board.lists = [lst]
        doc = {"app": "桌宠看板", "version": 2, "id": "a" * 32,
               "name": "测试板", "saved_at": "2026-01-01T00:00:00",
               "lists": [self._list_doc(title)]}
        self.store_path.write_text(json.dumps(doc, ensure_ascii=False),
                                   encoding="utf-8")
        return board

    @staticmethod
    def _list_doc(title: str) -> dict:
        return {"id": "b" * 32, "title": title, "cards": [
            {"id": "c" * 32, "title": f"{title}卡"}]}

    def test_restore_snapshot_swaps_content_and_takes_safety_snapshot(self):
        c, notifications = _light_controller(self.store_path)
        self._seed_board("第一版")
        c._store.load()

        # 造一份内容不同的快照（第二版）
        snap = self.store_path.with_name(
            f"{self.store_path.name}.snap.20260101_000000_000000.bak")
        snap.write_text(json.dumps(
            {"app": "桌宠看板", "version": 2, "id": "a" * 32,
             "name": "测试板", "saved_at": "2026-01-02T00:00:00",
             "lists": [self._list_doc("第二版")]}, ensure_ascii=False),
            encoding="utf-8")

        with patch("app.views.history_dialog.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            pass   # 控制器路径不再弹确认（确认在对话框内），此 patch 仅防漏
        c._on_restore_snapshot(str(snap))
        c._save_pool.waitForDone(5000)

        board = c._store.load()
        self.assertEqual(board.lists[0].title, "第二版")
        self.assertEqual(len(notifications), 1)
        self.assertIn("已恢复", notifications[0])

        # 恢复前自动留档：快照数从 1 → 2，新增档内容是恢复前的"第一版"
        snaps = json_io.list_snapshots(self.store_path)
        self.assertEqual(len(snaps), 2)
        contents = [Path(i["path"]).read_text(encoding="utf-8")
                    for i in snaps]
        restored_first = [t for t in contents if "第一版" in t]
        self.assertEqual(len(restored_first), 1,
                         "恢复前的当前状态（第一版）必须先被留档")

    def test_restore_missing_snapshot_shows_error(self):
        c, notifications = _light_controller(self.store_path)
        self._seed_board("第一版")
        errors = []
        c._show_error = errors.append
        c._on_restore_snapshot(str(self.store_path) + ".snap.none.bak")
        self.assertEqual(len(errors), 1)
        self.assertEqual(notifications, [])
        self.assertEqual(c._store.load().lists[0].title, "第一版")


if __name__ == "__main__":
    unittest.main()
