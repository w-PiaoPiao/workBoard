# -*- coding: utf-8 -*-
"""整仓备份导出测试：zip 内容清单（白名单打包 + 排除备份族）与解包读回

数据目录用临时目录伪造（create_workspace_backup 的 data_dir 参数可注入），
不触碰真实用户数据。
"""

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PET_BOARD_DATA_DIR"] = tempfile.mkdtemp()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.backup import create_workspace_backup

_BOARD_ID = "a" * 32
_BOARD_ID2 = "b" * 32


def _make_data_dir(root: Path) -> None:
    """伪造一个完整数据目录：数据 + 各族备份 + 运行态文件"""
    (root / "boards").mkdir(parents=True)
    (root / "workspace.json").write_text(
        '{"version":1,"current":"' + _BOARD_ID + '","boards":[]}',
        encoding="utf-8")
    (root / "templates.json").write_text("{}", encoding="utf-8")
    (root / "board.json").write_text('{"legacy": true}', encoding="utf-8")
    (root / "settings.ini").write_text("[ui]", encoding="utf-8")
    (root / "instance.sock").write_bytes(b"")

    (root / "boards" / f"{_BOARD_ID}.json").write_text(
        '{"app":"桌宠看板","version":2}', encoding="utf-8")
    (root / "boards" / f"{_BOARD_ID2}.json").write_text(
        '{"app":"桌宠看板","version":2}', encoding="utf-8")
    # 看板同族备份与临时文件：一律排除
    (root / "boards" / f"{_BOARD_ID}.prev").write_text("old", encoding="utf-8")
    (root / "boards" /
     f"{_BOARD_ID}.snap.20260101_000000_000000.bak").write_text(
        "snap", encoding="utf-8")
    (root / "boards" /
     f"{_BOARD_ID}.corrupt.20260102_000000_000000.bak").write_text(
        "corrupt", encoding="utf-8")
    (root / "boards" /
     f"{_BOARD_ID}.good.20260103_000000_000000.bak").write_text(
        "good", encoding="utf-8")
    (root / "boards" / ".tmp.1234.abcd").write_text("tmp", encoding="utf-8")
    (root / "boards" / "junk.json").write_text("{}", encoding="utf-8")  # 非法名

    card_dir = root / "attachments" / "card1"
    (card_dir / "sub").mkdir(parents=True)
    (card_dir / "img.png").write_bytes(b"\x89PNG")
    (card_dir / "sub" / "deep.txt").write_text("deep", encoding="utf-8")


class WorkspaceBackupTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name) / "data"
        _make_data_dir(self.data_dir)
        self.dest = Path(self._tmp.name) / "out.zip"

    def tearDown(self):
        self._tmp.cleanup()

    def _namelist(self) -> list[str]:
        with zipfile.ZipFile(self.dest) as zf:
            return sorted(zf.namelist())

    def test_packages_whitelisted_data_only(self):
        count = create_workspace_backup(self.dest, data_dir=self.data_dir)
        self.assertEqual(self._namelist(), sorted([
            "workspace.json",
            "templates.json",
            "board.json",
            f"boards/{_BOARD_ID}.json",
            f"boards/{_BOARD_ID2}.json",
            "attachments/card1/img.png",
            "attachments/card1/sub/deep.txt",
        ]))
        self.assertEqual(count, 7)

    def test_zip_contents_roundtrip(self):
        create_workspace_backup(self.dest, data_dir=self.data_dir)
        with zipfile.ZipFile(self.dest) as zf:
            self.assertIn(_BOARD_ID, zf.read("workspace.json").decode("utf-8"))
            self.assertEqual(zf.read(f"boards/{_BOARD_ID2}.json")
                             .decode("utf-8"),
                             '{"app":"桌宠看板","version":2}')
            self.assertEqual(zf.read("attachments/card1/sub/deep.txt")
                             .decode("utf-8"), "deep")

    def test_empty_data_dir_raises(self):
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            create_workspace_backup(self.dest, data_dir=empty)

    def test_missing_attachments_dir_is_ok(self):
        """最小数据目录（只有 workspace.json）也能打包"""
        minimal = Path(self._tmp.name) / "minimal"
        minimal.mkdir()
        (minimal / "workspace.json").write_text("{}", encoding="utf-8")
        count = create_workspace_backup(self.dest, data_dir=minimal)
        self.assertEqual(count, 1)
        self.assertEqual(self._namelist(), ["workspace.json"])


if __name__ == "__main__":
    unittest.main()
