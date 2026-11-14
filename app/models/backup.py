"""整仓备份：把数据目录打包为 zip（workspace.json + 全部看板 + 模板 + 附件）

与「导出备份（.json）」（单块看板）互补：zip 覆盖数据目录里的全部用户
数据。只打包"数据"不打包"备份"——boards/ 下每块看板同族的 .prev /
.snap.*.bak / .corrupt.*.bak / .good.*.bak 与 .tmp 临时文件一律排除；
settings.ini（QSettings 环境覆盖时的落盘位置）与 instance.sock（单实例
运行态）不属于看板数据，同样不打包。

zip 内路径是相对数据目录的目录结构（workspace.json / boards/<id>.json /
attachments/<卡id>/<文件>），恢复 = 退出应用后解压覆盖数据目录，或对单块
看板用「从备份导入…」导入为新看板（见 README「自动备份与恢复」）。

标准库 zipfile，不依赖 Qt，可独立单测。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from app.config import AppConfig

# 与 workspace._BOARD_ID_RE 同源：boards/ 下只有合法 id 的主文件是数据，
# 其余都是备份族/临时文件，不进 zip（孤儿文件由 workspace.load 收编）
_BOARD_FILE_RE = re.compile(r"^[0-9a-f]{32}\.json$")

# 数据目录顶层的散文件白名单（board.json 为旧版单看板留档，可能不存在）
_TOP_FILES = ("workspace.json", "templates.json", "board.json")


def create_workspace_backup(dest: Path, data_dir: Path | None = None) -> int:
    """打包数据目录到 dest（zip），返回打包的文件数

    没有任何可打包内容（数据目录为空）抛 ValueError；写 zip 失败抛
    OSError，由调用方统一提示。
    """
    data_dir = Path(data_dir) if data_dir is not None else Path(AppConfig.DATA_DIR)
    files: list[tuple[Path, str]] = []   # (磁盘路径, zip 内相对路径)
    for name in _TOP_FILES:
        p = data_dir / name
        if p.is_file():
            files.append((p, name))
    boards_dir = data_dir / "boards"
    if boards_dir.is_dir():
        for p in sorted(boards_dir.iterdir()):
            if p.is_file() and _BOARD_FILE_RE.fullmatch(p.name):
                files.append((p, f"boards/{p.name}"))
    attachments = data_dir / "attachments"
    if attachments.is_dir():
        for p in sorted(attachments.rglob("*")):
            # 附件目录是纯数据，全部收进 zip（含嵌套的 <卡id>/ 子目录）
            if p.is_file():
                files.append((p, p.relative_to(data_dir).as_posix()))
    if not files:
        raise ValueError("数据目录里没有可备份的内容")
    dest = Path(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in files:
            zf.write(src, arcname)
    return len(files)
