"""打包入口（Python 侧执行 PyInstaller）

从 app/config.py 读取版本号生成包名。打包逻辑放 Python 侧，
避免 Windows PowerShell 传中文参数给 pyinstaller 时的编码乱码
（曾把 "桌宠看板" 变成 "妗屽疇鐪嬫澘" 文件名）。

onefile 产物是单个 exe，无法打包后清理内部文件，所以这里动态
生成 spec，在 Analysis 结果上过滤未使用的 Qt 组件后再打出 onefile
（--exclude-module 只挡 Python 绑定，Qt 的 C++ dll 仍会被 PySide6
hook 全量收集；应用只用 QtCore/QtGui/QtWidgets）。

用法：
    python tools/build_app.py            # onefile（dist/<name>.exe）
    python tools/build_app.py --onedir   # 便携目录版（dist/<name>-portable/ + zip）

便携目录版不向 %TEMP% 解包：onefile 的 bootloader 必须先解包到系统临时
目录，而受限令牌（沙箱/托管桌面）下 %TEMP% 往往写不进，会直接弹
"Could not create temporary directory!" 且 Python 代码根本没机会运行。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# dist_name 里路径分隔符统一按 / 匹配（已小写）。命中即从产物剔除：
# Qt6* 为 C++ dll（PySide6/Qt/bin），PySide6/Qt* 为绑定扩展，
# imageformats/iconengines/platforminputcontexts 为按需 dlopen 的插件，
# pyside6/qt/qml 为 QML 模块目录。若 Windows 上启动异常，
# 把对应条目从这里移除即可。
DEAD_PATTERNS = (
    "qt6pdf",
    "qt6qml",
    "qt6quick",
    "qt6network",
    "qt6dbus",
    "qt6opengl",
    "qt6svg",
    "qt6virtualkeyboard",
    "pyside6/qtdbus",
    "pyside6/qtnetwork",
    "pyside6/qtqml",
    "pyside6/qtquick",
    "pyside6/qtpdf",
    "pyside6/qtopengl",
    "pyside6/qtsvg",
    "pyside6/qtvirtualkeyboard",
    "imageformats/libqpdf",
    "imageformats/libqsvg",
    "imageformats/libqtiff",
    "imageformats/libqwbmp",
    "imageformats/libqtga",
    "iconengines/",
    "platforminputcontexts/qtvirtualkeyboard",
    "pyside6/qt/qml",
)

# Qt 自带翻译只留中英兜底标准对话框文案（应用自带中英 i18n）
KEEP_TRANSLATIONS = ("qtbase_zh_cn.qm", "qtbase_en.qm")

SPEC_TEMPLATE = '''# -*- mode: python ; coding: utf-8 -*-
# 由 tools/build_app.py 自动生成，勿手改（Windows onefile + Qt 死重过滤）

DEAD_PATTERNS = {dead!r}
KEEP_TRANSLATIONS = {keep!r}


def _is_dead(dest_name):
    n = dest_name.replace("\\\\", "/").lower()
    for p in DEAD_PATTERNS:
        if p in n:
            return True
    if "pyside6/qt/translations/" in n and not n.endswith(KEEP_TRANSLATIONS):
        return True
    return False


a = Analysis(
    [{entry!r}],
    pathex=[],
    binaries=[],
    datas={datas!r},
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtMultimedia',
        'PySide6.Qt3DCore', 'PySide6.QtNetwork',
    ],
    noarchive=False,
    optimize=0,
)

# PyInstaller 6 起 TOC 已移除，a.binaries / a.datas 是普通 list
a.binaries = [x for x in a.binaries if not _is_dead(x[0])]
a.datas = [x for x in a.datas if not _is_dead(x[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name={name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon!r},
)
'''

SPEC_TEMPLATE_ONEDIR = '''# -*- mode: python ; coding: utf-8 -*-
# 由 tools/build_app.py 自动生成，勿手改（Windows 便携目录版 + Qt 死重过滤）

DEAD_PATTERNS = {dead!r}
KEEP_TRANSLATIONS = {keep!r}


def _is_dead(dest_name):
    n = dest_name.replace("\\\\", "/").lower()
    for p in DEAD_PATTERNS:
        if p in n:
            return True
    if "pyside6/qt/translations/" in n and not n.endswith(KEEP_TRANSLATIONS):
        return True
    return False


a = Analysis(
    [{entry!r}],
    pathex=[],
    binaries=[],
    datas={datas!r},
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtMultimedia',
        'PySide6.Qt3DCore', 'PySide6.QtNetwork',
    ],
    noarchive=False,
    optimize=0,
)

# PyInstaller 6 起 TOC 已移除，a.binaries / a.datas 是普通 list
a.binaries = [x for x in a.binaries if not _is_dead(x[0])]
a.datas = [x for x in a.datas if not _is_dead(x[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name={name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon!r},
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name={name!r},
)
'''


# ── 许可声明 ─────────────────────────────────────────────────
# 发布物含 Qt/PySide6（LGPLv3）、Python（PSF-2.0）等第三方组件，分发二进制
# 时必须附带许可文本与通知（详见 THIRD_PARTY_NOTICES.md）。这些文件跟着
# 产物走，避免"exe 发出去、声明留在仓库里"。
LICENSE_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md")
LICENSE_DIRS = ("LICENSES",)


def _license_entries() -> list[Path]:
    """要随包分发的许可文件/目录；缺失时只警告，不让打包失败"""
    entries: list[Path] = []
    for rel in LICENSE_FILES:
        p = ROOT / rel
        if p.is_file():
            entries.append(p)
        else:
            print(f"警告: 缺少 {rel}，发布产物将不含许可声明")
    for rel in LICENSE_DIRS:
        p = ROOT / rel
        if p.is_dir():
            entries.append(p)
        else:
            print(f"警告: 缺少 {rel}/，发布产物将不含第三方许可全文")
    return entries


def _copy_license_bundle(dest_dir: Path) -> None:
    """把许可声明复制进发布目录（便携目录版，压缩前调用）"""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in _license_entries():
        dest = dest_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)


def _write_license_zip(path: Path) -> None:
    """onefile 版：许可声明单独打 zip，分发 exe 时一并提供"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in _license_entries():
            if src.is_dir():
                for f in sorted(src.rglob("*")):
                    if f.is_file():
                        zf.write(f, f.relative_to(ROOT).as_posix())
            else:
                zf.write(src, src.name)


def _license_datas() -> list[tuple[str, str]]:
    """许可文件随包打进 app/resources/licenses/（应用内「开源许可」读取）

    onefile 的 EXE 与 onedir 的 _internal 都由 PyInstaller 解包到
    sys._MEIPASS，app/services/licensing.py 按该路径定位，两种形态通用。
    """
    out: list[tuple[str, str]] = []
    for rel in LICENSE_FILES:
        p = ROOT / rel
        if p.is_file():
            out.append((str(p), "app/resources/licenses"))
    lic_dir = ROOT / "LICENSES"
    if lic_dir.is_dir():
        out.extend((str(p), "app/resources/licenses")
                   for p in sorted(lic_dir.glob("*.txt")) if p.is_file())
    return out


def _read_app_version() -> str:
    cfg = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION = "([^"]+)"', cfg)
    if not match:
        raise SystemExit("未能从 app/config.py 读取 APP_VERSION")
    return match.group(1)


def main() -> int:
    # 控制台可能不是 UTF-8（如 GitHub Actions 的 cp1252）：中文包名/日志
    # 打印会 UnicodeEncodeError，先把 stdout/stderr 切成 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass

    onedir = "--onedir" in sys.argv[1:]
    base = f"peTTrello-v{_read_app_version()}"
    name = f"{base}-portable" if onedir else base
    print(f"打包: {name}（{'便携目录' if onedir else 'onefile'}）")

    template = SPEC_TEMPLATE_ONEDIR if onedir else SPEC_TEMPLATE
    spec = template.format(
        dead=DEAD_PATTERNS,
        keep=KEEP_TRANSLATIONS,
        entry=str(ROOT / "main.py"),
        name=name,
        icon=str(ROOT / "assets" / "app.ico"),
        datas=_license_datas(),
    )
    spec_path = ROOT / "build_app.generated.spec"
    spec_path.write_text(spec, encoding="utf-8")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        str(spec_path),
    ]
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    finally:
        spec_path.unlink(missing_ok=True)

    if onedir:
        # 便携标记：app/config.py 据此把数据固定在 exe 旁的 data/，
        # 整个文件夹搬走即可带走数据（见 _portable_data_dir）
        (DIST / name / "portable.marker").write_text(
            "便携目录版：数据保存在同级 data/ 目录，可整个文件夹搬移\n",
            encoding="utf-8")
        # 许可声明跟着产物走，压缩前放进目录（QT 为 LGPLv3，见 README「许可证」）
        _copy_license_bundle(DIST / name)
        archive = shutil.make_archive(
            str(DIST / name), "zip", root_dir=DIST, base_dir=name)
        print(f"完成: dist\\{name}\\{name}.exe")
        print(f"压缩: dist\\{Path(archive).name}")
    else:
        print(f"完成: dist\\{name}.exe")
        # onefile 是单个 exe，塞不进许可文本：单独产出一个声明包，
        # 分发时与 exe 一起提供（README「许可证」有说明）
        bundle = DIST / f"{name}-licenses.zip"
        _write_license_zip(bundle)
        print(f"许可声明: dist\\{bundle.name}（分发 exe 时请一并提供）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
