"""开源许可面板：第三方组件声明 + 各许可全文

Qt / PySide6 以 LGPLv3 分发，许可证文本必须随二进制一起提供。打包时这些
文件被放进 `app/resources/licenses/`（见 tools/build_app.py 与
tools/build.sh），本对话框在应用内直接展示，用户不必去翻发布包里的
LICENSES/ 目录；源码运行时读仓库根的同名文件（app/services/licensing.py）。

一次性对话框（每次打开现构造）：与快捷键面板同范式，主题/语言回调由
调用方重新构造即可，不常驻。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from app.i18n import tr
from app.services.licensing import license_documents
from app.views import tokens
from app.views.theme import AppTheme

# 已知许可文件 → 列表显示名（组件名不翻译，中英界面通用）
_KNOWN_LABELS = {
    "LGPL-3.0": "GNU LGPL v3",
    "GPL-3.0": "GNU GPL v3",
    "Python-3.12": "Python 3.12 (PSF)",
    "MIT-appdirs": "appdirs (MIT)",
    "MIT-openpyxl": "openpyxl (MIT)",
}


class LicenseDialog(QDialog):
    """开源许可（一次性，模态）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("开源许可"))
        self.setMinimumSize(560, 420)
        self.resize(720, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(*tokens.dialog_margins(bottom_trim=4, top=16))
        root.setSpacing(tokens.space(8))

        body = QHBoxLayout()
        body.setSpacing(tokens.space(12))
        self._list = QListWidget()
        self._list.setObjectName("licList")
        self._list.setFixedWidth(tokens.size(190))
        self._list.currentRowChanged.connect(self._on_row_changed)
        body.addWidget(self._list)
        self._text = QTextBrowser()
        self._text.setObjectName("licText")
        self._text.setOpenExternalLinks(True)
        body.addWidget(self._text, 1)
        root.addLayout(body, 1)

        self._hint = QLabel(tr("许可文本与第三方声明随安装包一同分发"))
        self._hint.setObjectName("licHint")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        btns = QHBoxLayout()
        btns.addStretch(1)
        close = QPushButton(tr("关闭"))
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        root.addLayout(btns)

        self._docs = license_documents()
        self._load()
        self.reapply_theme()
        AppTheme.register(self.reapply_theme)

    # ── 内容 ──────────────────────────────────────────────

    def _label(self, kind: str, name: str) -> str:
        if kind == "notices":
            return tr("第三方组件与许可声明")
        if kind == "own":
            return tr("本应用（MIT 许可）")
        return _KNOWN_LABELS.get(kind, name)

    def _load(self) -> None:
        """填充左侧文件列表；没有任何许可文件时给出提示而不是空窗"""
        self._list.clear()
        if not self._docs:
            self._hint.setText(tr("未找到许可文件"))
            self._list.setEnabled(False)
            return
        for path, kind in self._docs:
            item = QListWidgetItem(self._label(kind, path.name))
            item.setToolTip(str(path.name))
            self._list.addItem(item)
        self._list.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if not (0 <= row < len(self._docs)):
            self._text.clear()
            return
        path, _kind = self._docs[row]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self._text.setPlainText(tr("读取许可文件失败：{err}").format(err=e))
            return
        # 声明是 Markdown（带表格/链接），其余是纯文本许可全文
        if path.suffix.lower() in (".md", ".markdown"):
            self._text.setMarkdown(text)
        else:
            self._text.setPlainText(text)

    # ── 主题 ──────────────────────────────────────────────

    def reapply_theme(self) -> None:
        """重下配色：样式是构建期快照，打开期间换主题需重刷"""
        c = AppTheme.colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg_primary']}; }}
            QListWidget#licList {{
                background: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: {tokens.radius('control')}px;
                color: {c['text_primary']};
                {tokens.font_css(12)};
                outline: none;
            }}
            QListWidget#licList::item {{
                {tokens.pad(6, 10)};
                border-radius: {tokens.radius('chip')}px;
            }}
            QListWidget#licList::item:selected {{
                background: {c['accent_soft']};
                color: {c['accent']};
            }}
            QTextBrowser#licText {{
                background: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: {tokens.radius('control')}px;
                color: {c['text_primary']};
                {tokens.font_css(12)};
                {tokens.pad(10, 12)};
            }}
            QLabel#licHint {{
                color: {c['text_secondary']};
                {tokens.font_css(11)};
                background: transparent;
            }}
        """)
