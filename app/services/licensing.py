"""许可文件定位（源码运行 / PyInstaller 打包运行共用）

发布物里 Qt / PySide6 以 LGPLv3 分发，需要随包提供许可证文本。打包时
`LICENSE`、`THIRD_PARTY_NOTICES.md`、`LICENSES/*.txt` 被放进
`app/resources/licenses/`（见 tools/build_app.py 与 tools/build.sh），
应用内「开源许可」对话框从这里读取；源码运行时回退到仓库根
（三个文件本来就在那里）。找不到时返回空列表，由界面提示，不让启动失败。

不依赖 Qt，可独立单测。
"""

from __future__ import annotations

import sys
from pathlib import Path

NOTICES_NAME = "THIRD_PARTY_NOTICES.md"
OWN_LICENSE_NAME = "LICENSE"

# 已知文件 → 稳定排序权重（未知文件按文件名排在后面）
_KNOWN_ORDER = {"LGPL-3.0.txt": 0, "GPL-3.0.txt": 1}


def _candidate_dirs() -> list[tuple[Path, bool]]:
    """候选目录：[(目录, 是否打包解包目录)]

    打包解包目录里的许可文件是**平铺**的（PyInstaller datas 只指定一个
    目标目录），源码仓库根的许可全文在 `LICENSES/` 子目录下——两者布局
    不同，由调用方按标志区分。
    """
    cands: list[tuple[Path, bool]] = []
    mei = getattr(sys, "_MEIPASS", "")
    if mei:
        cands.append((Path(mei) / "app" / "resources" / "licenses", True))
    # app/services/licensing.py → 上三层即仓库根（含 LICENSE / LICENSES/）
    cands.append((Path(__file__).resolve().parent.parent.parent, False))
    return cands


def _resolve_root() -> tuple[Path | None, bool]:
    """(含许可文件的目录, 是否打包解包目录)；都没有时 (None, False)"""
    for cand, bundled in _candidate_dirs():
        try:
            if (cand / NOTICES_NAME).is_file() or (cand / OWN_LICENSE_NAME).is_file():
                return cand, bundled
        except OSError:      # 极端情况下路径不可访问：换下一个候选
            continue
    return None, False


def license_root() -> Path | None:
    """找到含许可文件的目录；都没有返回 None"""
    return _resolve_root()[0]


def license_documents() -> list[tuple[Path, str]]:
    """全部可展示的许可文档：[(文件路径, 种类标识)]

    种类标识：``notices`` / ``own`` / 文件名去扩展名（如 ``LGPL-3.0``）。
    顺序：第三方声明 → 本应用 MIT → 各许可全文（LGPL/GPL 优先）。
    """
    root, bundled = _resolve_root()
    if root is None:
        return []

    docs: list[tuple[Path, str]] = []
    notices = root / NOTICES_NAME
    if notices.is_file():
        docs.append((notices, "notices"))
    own = root / OWN_LICENSE_NAME
    if own.is_file():
        docs.append((own, "own"))

    extras: list[Path] = []
    lic_dir = root / "LICENSES"
    if lic_dir.is_dir():
        try:
            extras.extend(p for p in lic_dir.glob("*.txt") if p.is_file())
        except OSError:
            pass
    # 打包时 datas 把 LICENSES/*.txt 平铺进同一目录；源码根只认 LICENSES/，
    # 否则会把 requirements.txt 之类当许可文档
    if bundled:
        try:
            extras.extend(p for p in root.glob("*.txt") if p.is_file())
        except OSError:
            pass
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in extras:
        if p.name in seen:
            continue
        seen.add(p.name)
        uniq.append(p)
    uniq.sort(key=lambda p: (_KNOWN_ORDER.get(p.name, 9), p.name.lower()))
    docs.extend((p, p.stem) for p in uniq)
    return docs
