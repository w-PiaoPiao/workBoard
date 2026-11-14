# -*- coding: utf-8 -*-
"""CSV 导入测试：本应用导出格式回读（往返无损）、坏行跳过、边界容错

导出端是 AppController._write_export_csv（staticmethod，直接调用不实例
化控制器），导入端是 importers.board_from_csv 纯函数。
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

from app.controllers import app_controller as controller_mod
from app.models.board import Board, BoardList, Card
from app.models.importers import board_from_csv


def _export_csv_text(board: Board) -> str:
    """走真实导出函数拿 CSV 文本（临时文件落盘再读回）"""
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "out.csv"
    controller_mod.AppController._write_export_csv(p, board)
    return p.read_text(encoding="utf-8-sig")


class RoundTripTest(unittest.TestCase):
    def test_roundtrip_preserves_all_fields(self):
        """导出 → 导入往返：全部业务字段无损还原"""
        board = Board(name="往返板")
        lst = BoardList(title="进行中")
        lst.cards.append(Card(
            title="写周报", notes="含项目进度\n第二行", labels=["blue", "red"],
            due_date="2026-09-10", done=True, priority=1, pomodoros=3,
            repeat="weekly"))
        lst.cards.append(Card(
            title="带清单项", repeat="custom", repeat_interval=7))
        lst.cards.append(Card(title="=HYPERLINK(\"x\", \"点\")", notes="@风险"))
        # 注意：CSV 格式无法表达空列表（没有卡片就没有行），往返只保证
        # 有卡片的列表还原
        board.lists = [lst]

        board2, report = board_from_csv(_export_csv_text(board),
                                        fallback_title="回读")
        self.assertEqual(board2.name, "回读")
        self.assertEqual(report, "列表 1 · 卡片 3")
        self.assertEqual([l.title for l in board2.lists], ["进行中"])
        c = board2.lists[0].cards[0]
        self.assertEqual(c.title, "写周报")
        self.assertEqual(c.notes, "含项目进度\n第二行")
        self.assertEqual(c.labels, ["blue", "red"])
        self.assertEqual(c.due_date, "2026-09-10")
        self.assertTrue(c.done)
        self.assertEqual(c.priority, 1)
        self.assertEqual(c.pomodoros, 3)
        self.assertEqual(c.repeat, "weekly")
        c2 = board2.lists[0].cards[1]
        self.assertEqual(c2.repeat, "custom")
        self.assertEqual(c2.repeat_interval, 7)
        # _csv_safe 加的公式注入前缀 '=' 必须还原
        c3 = board2.lists[0].cards[2]
        self.assertEqual(c3.title, "=HYPERLINK(\"x\", \"点\")")
        self.assertEqual(c3.notes, "@风险")

    def test_roundtrip_done_at_missing_is_ok(self):
        """导出格式不含 done_at：完成卡导入后 done=True 即可，不要求时刻"""
        board = Board(name="x")
        lst = BoardList(title="列")
        lst.cards.append(Card(title="已办", done=True))
        board.lists = [lst]
        board2, _ = board_from_csv(_export_csv_text(board))
        self.assertTrue(board2.lists[0].cards[0].done)


class ParseRuleTest(unittest.TestCase):
    """手写 CSV（对齐导出列名）的逐项解析规则"""

    @staticmethod
    def _parse(text: str):
        return board_from_csv(text, fallback_title="f")

    def test_minimal_header_only_title(self):
        """只要求「标题」列，其余列缺失用默认值"""
        board, report = self._parse("标题\n只写标题")
        self.assertEqual(report, "列表 1 · 卡片 1")
        c = board.lists[0].cards[0]
        self.assertEqual(c.title, "只写标题")
        self.assertEqual(board.lists[0].title, "待办")   # 无列表列 → 待办
        self.assertEqual(c.labels, [])
        self.assertIsNone(c.due_date)
        self.assertFalse(c.done)
        self.assertEqual(c.priority, 0)
        self.assertEqual(c.pomodoros, 0)
        self.assertEqual(c.repeat, "never")

    def test_old_export_without_interval_column(self):
        """旧版导出没有「重复间隔」列：custom 周期仍可导入（间隔默认 1）"""
        board, _ = self._parse(
            "列表,标题,优先级,重复\n列A,任务,高,自定义")
        c = board.lists[0].cards[0]
        self.assertEqual(c.priority, 1)
        self.assertEqual(c.repeat, "custom")
        self.assertEqual(c.repeat_interval, 1)

    def test_value_tolerances(self):
        """非法值降级不整行作废：标签/优先级/日期/番茄数/created_at"""
        board, _ = self._parse(
            "列表,标题,标签,截止日期,完成,优先级,番茄数,创建时间\n"
            "列A,任务, purple ; 不存在的色 ,2026-13-40,是,P2,abc,不是时间")
        c = board.lists[0].cards[0]
        self.assertEqual(c.labels, ["purple"])       # 未知色 key 忽略
        self.assertIsNone(c.due_date)                # 非法日期丢弃
        self.assertTrue(c.done)                      # "是"
        self.assertEqual(c.priority, 2)              # "P2" 也接受
        self.assertEqual(c.pomodoros, 0)             # 非数字 → 0
        self.assertNotEqual(c.created_at, "不是时间")  # 非法时刻 → 默认 now
        self.assertEqual(board.lists[0].title, "列A")

    def test_empty_title_rows_are_skipped_and_counted(self):
        board, report = self._parse(
            "标题\n正常卡\n\n   \n,只有备注没有标题\n另一个")
        self.assertEqual([c.title for c in board.lists[0].cards],
                         ["正常卡", "另一个"])
        self.assertEqual(report, "列表 1 · 卡片 2 · 跳过 1 行")

    def test_lists_keep_first_seen_order(self):
        board, report = self._parse(
            "列表,标题\n乙列,a\n甲列,b\n乙列,c")
        self.assertEqual([l.title for l in board.lists], ["乙列", "甲列"])
        self.assertEqual(report, "列表 2 · 卡片 3")
        self.assertEqual(board.lists[0].cards[1].title, "c")

    def test_done_column_variants(self):
        for raw, want in (("是", True), ("x", True), ("否", False),
                          ("", False), ("no", False)):
            board, _ = self._parse(f"标题,完成\n卡,{raw}")
            self.assertEqual(board.lists[0].cards[0].done, want, raw)

    def test_crlf_and_bom_tolerated(self):
        """Windows 记事本改过的文件：\r\n 行尾 + 手滑留下的 BOM"""
        board, _ = self._parse("\ufeff标题,备注\r\n卡,注\r\n")
        self.assertEqual(board.lists[0].cards[0].title, "卡")
        self.assertEqual(board.lists[0].cards[0].notes, "注")


class ErrorTest(unittest.TestCase):
    def test_empty_text_raises(self):
        with self.assertRaises(ValueError):
            board_from_csv("")

    def test_header_only_raises(self):
        with self.assertRaises(ValueError):
            board_from_csv("标题\n")

    def test_missing_title_column_raises(self):
        with self.assertRaises(ValueError):
            board_from_csv("名称,备注\n卡,注")


if __name__ == "__main__":
    unittest.main()
