# 第三方组件与许可声明（Third-Party Notices）

本项目（桌宠看板 / peTTrello）本体以 [MIT 许可证](LICENSE) 发布。

通过官方渠道分发的安装包 / 可执行文件中还包含下列第三方组件。它们的许可
与本项目自身的 MIT 许可相互独立，分发本项目的二进制产物时必须一并遵守。

## 组件清单

| 组件 | 版本 | 许可 | 分发形态 | 许可文本 |
|---|---|---|---|---|
| PySide6（Qt for Python 绑定） | 6.10.3 | LGPL-3.0-only（亦提供 GPL-2.0/3.0 与商业许可） | `_internal/PySide6/*.pyd`、`pyside6.abi3.dll` | [LGPL-3.0](LICENSES/LGPL-3.0.txt) + [GPL-3.0](LICENSES/GPL-3.0.txt) |
| Shiboken6（绑定生成运行时） | 6.10.3 | LGPL-3.0-only | `_internal/shiboken6/` | 同上 |
| Qt 6（Core / Gui / Widgets 及其插件、翻译） | 6.10.3 | LGPL-3.0-only | `_internal/PySide6/Qt6*.dll`、`plugins/`、`translations/qtbase_zh_CN.qm`、`qtbase_en.qm` | 同上 |
| Python 运行时 | 3.12 | PSF-2.0（Python Software Foundation License） | `python312.dll`、`base_library.zip`、标准库 `.pyd` | [Python-3.12](LICENSES/Python-3.12.txt) |
| appdirs | 1.4.4 | MIT | 程序代码内（Python 模块） | [MIT-appdirs](LICENSES/MIT-appdirs.txt) |
| openpyxl | 3.1.5 | MIT | 程序代码内（Python 模块） | [MIT-openpyxl](LICENSES/MIT-openpyxl.txt) |
| PyInstaller（含 bootloader） | 6.22.3 | GPL-2.0-or-later **WITH Bootloader-exception**（仅构建期使用；其 bootloader 例外条款允许打包并分发非自由程序） | 打包器内嵌于 exe 的引导代码 | 见下方说明 |
| 随包动态库（OpenSSL、libffi、zlib、bzip2、liblzma、Microsoft VC++ 运行库等） | 随 Python / Qt 上游版本 | 各自许可（Apache-2.0 / MIT / zlib / BSD 等） | `_internal/*.dll` | 由上游分发，按其各自许可使用 |

各上游项目的完整版权与许可信息请以对应发行包内附带的 license 文件为准；
本目录收录了分发时常用的许可全文。

## 关于 Qt / PySide6 的 LGPLv3 义务（重要）

本项目**未修改** Qt、PySide6 或 Shiboken6 的任何源码；它们以动态库形式
随应用分发。为满足 LGPLv3 第 4 条对「组合作品」的要求，我们做了以下安排：

1. **动态链接、可替换**：推荐的发布形态是「便携目录版」
   （`peTTrello-v<版本>-portable.zip`）。其中 Qt/PySide6 的库文件
   （`_internal/PySide6/Qt6Core.dll` 等，macOS 为 framework）是独立的可替换
   文件，用户可以直接替换为接口兼容的修改版本。
2. **附带许可证文本与通知**：发布包内附带本文件、`LICENSES/LGPL-3.0.txt`
   与 `LICENSES/GPL-3.0.txt`；未删除 Qt/PySide6 库内嵌的版权信息。
3. **源码获取**：Qt 与 PySide6 的对应源码可从上游获取（见下）。
   若你收到的只是「单文件 exe」形态（PyInstaller onefile 会把 Qt 库内嵌进
   可执行文件），需要可重链接的版本时，请使用同版本的便携目录版，或向
   分发者索取本项目的源码（MIT）与对应上游源码。

上游源码与许可：

- Qt 6.10 源码与许可：<https://www.qt.io/licensing/open-source-lgpl-obligations>
  · <https://download.qt.io/official_releases/qt/6.10/>
- PySide6 / Shiboken6 源码：<https://download.qt.io/official_releases/QtForPython/>
  · PyPI 页面 <https://pypi.org/project/PySide6/6.10.3/>
- GNU LGPLv3：<https://www.gnu.org/licenses/lgpl-3.0.html>
- GNU GPLv3：<https://www.gnu.org/licenses/gpl-3.0.html>

## 商标

- Qt 与 Qt 标志是 The Qt Company Ltd. 的商标。
- Trello 是 Atlassian 的商标。本项目与 Atlassian 无任何隶属或背书关系，
  仅在「可导入 Trello 导出的 JSON」等互操作场景下提及该名称。
- 项目自有名称：桌宠看板 / peTTrello。
