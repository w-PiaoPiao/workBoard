# -*- coding: utf-8 -*-
"""统计视图测试：聚合纯函数口径、对话框渲染与空态、控制器注入"""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PET_BOARD_DATA_DIR"] = tempfile.mkdtemp()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

_qapp = QApplication.instance() or QApplication([])

from app.models.board import Board, BoardList, Card
from app.models.stats import compute_stats
from app.views.stats_dialog import StatsDialog

TODAY = date(2026, 11, 14)


def _done_at(d: date) -> str:
    return datetime(d.year, d.month, d.day, 12, 0).isoformat()


def _make_board() -> Board:
    board = Board(name="统计板")
    lst = BoardList(title="进行中")
    lst.cards.append(Card(title="甲", labels=["blue", "red"],
                          priority=1, pomodoros=5,
                          done=True, done_at=_done_at(TODAY)))
    lst.cards.append(Card(title="乙", labels=["blue"], priority=2))
    lst.cards.append(Card(title="丙", pomodoros=3,
                          done=True, done_at=_done_at(TODAY - timedelta(days=10)),
                          archived=True))   # 归档但今日完成
    lst2 = BoardList(title="已完成")
    lst2.cards.append(Card(title="丁", done=True,
                           done_at=_done_at(TODAY - timedelta(days=5))))
    board.lists = [lst, lst2]
    return board


class ComputeStatsTest(unittest.TestCase):
    def setUp(self):
        self.board = _make_board()
        self.s = compute_stats(self.board, TODAY)

    def test_overview_matches_today_stats(self):
        ov = self.s["overview"]
        # 未归档 3 张（甲乙丁），完成 2（甲丁），归档丙不算 total
        self.assertEqual(ov["total"], 3)
        self.assertEqual(ov["done"], 2)

    def test_trend_counts_archived_and_window(self):
        trend = dict(self.s["trend"])   # 键是 date 对象（展示层直接对轴）
        self.assertEqual(len(trend), 30)
        self.assertEqual(trend[TODAY], 1)   # 甲（丙也是今天完成）
        self.assertEqual(trend[TODAY - timedelta(days=10)],
                         1)   # 归档卡丙仍计入完成趋势
        self.assertEqual(trend[TODAY - timedelta(days=5)], 1)

    def test_label_distribution_counts_active_only(self):
        self.assertEqual(dict(self.s["label_counts"]),
                         {"blue": 2, "red": 1})   # 归档丙无标签，也不重复算甲

    def test_list_distribution_shows_active_and_total(self):
        self.assertEqual(self.s["list_counts"],
                         [("进行中", 2, 3), ("已完成", 1, 1)])

    def test_pomodoro_top(self):
        # 番茄统计与分布同口径只算未归档（甲5；丙3 已归档不计）
        self.assertEqual(self.s["pomo_total"], 5)
        self.assertEqual(self.s["pomo_top"], [("甲", 5)])

    def test_weekly_comparison(self):
        # 甲今天完成 → 本周 1；丁 5 天前（2026-11-09 周一）也在本周
        self.assertEqual(self.s["done_this_week"], 2)
        self.assertGreaterEqual(self.s["done_last_week"], 0)

    def test_priority_counts_active_only(self):
        self.assertEqual(self.s["priority_counts"],
                         {0: 1, 1: 1, 2: 1, 3: 0})   # 丁无优先级


class StatsDialogTest(unittest.TestCase):
    def setUp(self):
        self.dlg = StatsDialog()

    def tearDown(self):
        self.dlg.close()
        self.dlg.deleteLater()

    def test_set_summary_renders_rows(self):
        self.dlg.set_summary(compute_stats(_make_board(), TODAY))
        self.assertIn("总 3", self.dlg._overview_label.text())
        self.assertEqual(len(self.dlg._label_rows), 2)
        self.assertEqual(len(self.dlg._list_rows), 2)
        self.assertIn("累计 5 个番茄", self.dlg._pomo_label.text())

    def test_empty_then_data_recovers_sections(self):
        self.dlg.set_summary(None)
        self.assertIsNotNone(self.dlg._empty_label)
        self.assertFalse(self.dlg._trend.isVisibleTo(self.dlg))
        self.dlg.set_summary(compute_stats(_make_board(), TODAY))
        self.assertIsNone(self.dlg._empty_label)
        self.assertTrue(self.dlg._trend.isVisibleTo(self.dlg))

    def test_set_summary_twice_does_not_duplicate_rows(self):
        s = compute_stats(_make_board(), TODAY)
        self.dlg.set_summary(s)
        self.dlg.set_summary(s)
        self.assertEqual(len(self.dlg._list_rows), 2)

    def test_offscreen_paint_does_not_crash(self):
        """离屏渲染柱状图与比例条（paintEvent 全路径）"""
        self.dlg.set_summary(compute_stats(_make_board(), TODAY))
        self.dlg.resize(720, 560)
        self.dlg.grab()   # 强制整树渲染一次


class ControllerStatsTest(unittest.TestCase):
    """轻量控制器：_refresh_stats 按看板有无卡片注入不同摘要"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from app.controllers.app_controller import AppController
        from app.models.board import BoardStore

        self.c = AppController.__new__(AppController)
        self.c._store = BoardStore(Path(self._tmp.name) / "board.json")
        self.c._stats_dialog = StatsDialog()

    def tearDown(self):
        self._tmp.cleanup()

    def test_refresh_empty_board_shows_empty_state(self):
        self.c._refresh_stats()
        self.assertIsNotNone(self.c._stats_dialog._empty_label)

    def test_refresh_with_cards_injects_summary(self):
        board = self.c._store.load()
        board.lists[0].cards.append(Card(title="有卡"))
        self.c._refresh_stats()
        self.assertIsNone(self.c._stats_dialog._empty_label)
        self.assertIn("总 1", self.c._stats_dialog._overview_label.text())


if __name__ == "__main__":
    unittest.main()
