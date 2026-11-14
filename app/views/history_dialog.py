"""历史版本对话框：浏览启动快照并一键恢复

由控制器按需创建并保持引用；快照清单经 set_items 注入
（json_io.list_snapshots 的产物），恢复操作通过
signal_restore_requested 交回控制器处理——对话框不自持数据，
也不直接碰磁盘（「打开文件夹」除外，只读打开）。

行内直接放「恢复」按钮（与归档对话框同构）：恢复是低频安全操作，
但逐行按钮比"先选中再点底部按钮"少一步，且行内容本身就是确认信息
（时间 + 列表/卡片数）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import tr
from app.views import tokens
from app.views.theme import AppTheme


def _fmt_size(n: int) -> str:
    if n < 1024:
        return tr("{n} B").format(n=n)
    if n < 1024 * 1024:
        return tr("{n} KB").format(n=round(n / 1024))
    return tr("{n} MB").format(n=round(n / (1024 * 1024), 1))


class _SnapshotRow(QFrame):
    """快照行：时间 + 摘要 + 大小 + 恢复（行控件自持样式）"""

    def __init__(self, info: dict, on_restore):
        super().__init__()
        self.setObjectName("historyRow")
        self._path: Path = info["path"]
        self._unreadable = bool(info["unreadable"])

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(8)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        mtime = datetime.fromtimestamp(info["mtime"])
        self._title = QLabel(mtime.strftime("%Y-%m-%d %H:%M:%S"))
        self._title.setObjectName("historyTime")
        texts.addWidget(self._title)
        if self._unreadable:
            self._summary = QLabel(tr("快照文件无法读取"))
        else:
            self._summary = QLabel(
                tr("列表 {l} · 卡片 {c}").format(
                    l=info["lists"], c=info["cards"]))
        self._summary.setObjectName("historySummary")
        texts.addWidget(self._summary)
        lay.addLayout(texts, 1)

        self._size = QLabel(_fmt_size(info["size"]))
        self._size.setObjectName("historySummary")
        lay.addWidget(self._size, 0)

        self._restore_btn = QPushButton(tr("恢复"))
        self._restore_btn.setCursor(Qt.PointingHandCursor)
        self._restore_btn.setEnabled(not self._unreadable)
        self._restore_btn.clicked.connect(
            lambda _=False: on_restore(str(self._path)))
        lay.addWidget(self._restore_btn, 0)

        self.reapply_theme()

    def reapply_theme(self) -> None:
        c = AppTheme.colors()
        self.setStyleSheet(f"""
            QFrame#historyRow {{
                background: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: {tokens.radius('control')}px;
            }}
            QFrame#historyRow:hover {{ border: 1px solid {c['accent']}; }}
        """)
        self._title.setStyleSheet(
            f"color: {c['text_primary']}; background: transparent;")
        dim = c['text_disabled'] if self._unreadable else c['text_secondary']
        self._summary.setStyleSheet(
            f"color: {dim}; {tokens.font_css(11)}; background: transparent;")
        self._size.setStyleSheet(
            f"color: {dim}; {tokens.font_css(11)}; background: transparent;")
        self._restore_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {c['accent'] if not self._unreadable
                        else c['text_disabled']};
                border: 1px solid {c['border']};
                border-radius: {tokens.radius('control')}px;
                {tokens.pad_preset(AppConfig.UI_PAD_SECONDARY)};
            }}
            QPushButton:hover {{
                {'border: 1px solid ' + c['accent'] + ';' if not self._unreadable else ''}
            }}
            QPushButton:disabled {{ color: {c['text_disabled']}; }}
        """)


class HistoryDialog(QDialog):
    """历史版本查看器：启动快照列表（最新在前），行内一键恢复"""

    signal_restore_requested = Signal(str)   # 快照文件路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("历史版本"))
        self.setModal(False)
        self.setMinimumSize(560, 420)

        self._stats_label = QLabel()
        root = QVBoxLayout(self)
        root.setContentsMargins(*tokens.dialog_margins(bottom_trim=2))
        root.setSpacing(8)
        root.addWidget(self._stats_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(2, 2, 2, 2)
        self._rows_layout.setSpacing(6)
        self._scroll.setWidget(self._rows_host)
        root.addWidget(self._scroll, 1)

        foot = QHBoxLayout()
        self._folder_btn = QPushButton(tr("打开文件夹"))
        self._folder_btn.setObjectName("ghostBtn")
        self._folder_btn.setCursor(Qt.PointingHandCursor)
        self._folder_btn.setToolTip(tr("在文件管理器中查看全部自动备份文件"))
        self._folder_btn.clicked.connect(self._on_open_folder)
        foot.addWidget(self._folder_btn)
        foot.addStretch(1)
        self._close_btn = QPushButton(tr("关闭"))
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)
        foot.addWidget(self._close_btn)
        root.addLayout(foot)

        self._last_items: list[dict] | None = None
        AppTheme.register(self.reapply_theme)
        self.reapply_theme()

    def retexts(self) -> None:
        """语言切换：标题/按钮刷新，有数据时整组重建行"""
        self.setWindowTitle(tr("历史版本"))
        self._close_btn.setText(tr("关闭"))
        self._folder_btn.setText(tr("打开文件夹"))
        self._folder_btn.setToolTip(tr("在文件管理器中查看全部自动备份文件"))
        if self._last_items is not None:
            self.set_items(self._last_items)

    def set_items(self, items: list[dict]) -> None:
        """注入快照清单（json_io.list_snapshots 产物）并重建行"""
        self._last_items = list(items)
        self._render()

    def _render(self) -> None:
        items = self._last_items or []
        self._stats_label.setText(
            tr("共 {n} 份启动快照 · 恢复前会先为当前数据留一份新快照")
            .format(n=len(items)))

        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if not items:
            empty = QLabel(tr("暂无历史快照：启动或切换看板时自动留档"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setSizePolicy(QSizePolicy.Policy.Preferred,
                                QSizePolicy.Policy.Preferred)
            self._rows_layout.addWidget(empty)
            self._apply_empty_style(empty)
        else:
            for info in items:
                self._rows_layout.addWidget(
                    _SnapshotRow(info, self._on_row_restore))
        self._rows_layout.addStretch(1)
        self._folder_btn.setEnabled(bool(items))

    def _on_row_restore(self, path: str) -> None:
        """行内「恢复」：先确认再交回控制器（控制器收到的都是已确认请求）"""
        if self.confirm_restore(path):
            self.signal_restore_requested.emit(path)

    def _on_open_folder(self) -> None:
        """打开快照所在目录（每块看板的快照存放在 boards/ 下）"""
        if self._last_items:
            target = Path(self._last_items[0]["path"]).parent
        else:
            target = Path(AppConfig.DATA_DIR)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def confirm_restore(self, path: str) -> bool:
        """恢复前确认：说明"当前数据先留档"，让操作可反悔这件事可见"""
        answer = QMessageBox.question(
            self, tr("恢复历史版本"),
            tr("把看板数据恢复到这份快照？当前数据会先自动留一份新快照，"
               "恢复后随时可以再恢复回来。"))
        return answer == QMessageBox.Yes

    def _apply_empty_style(self, label: QLabel) -> None:
        c = AppTheme.colors()
        label.setStyleSheet(
            f"color: {c['text_disabled']};"
            f" {tokens.font_css(12)}; {tokens.pad_all(24)};")

    def reapply_theme(self) -> None:
        c = AppTheme.colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg_primary']}; }}
            QLabel {{ color: {c['text_primary']}; }}
            QPushButton {{
                background: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {tokens.radius('control')}px;
                {tokens.pad_preset(AppConfig.UI_PAD_SECONDARY)};
            }}
            QPushButton:hover {{ background: {c['bg_hover']}; }}
            QPushButton#ghostBtn {{
                background: transparent;
                color: {c['text_secondary']};
                border: 1px solid {c['border']};
            }}
            QPushButton#ghostBtn:hover {{
                color: {c['text_primary']};
                background: {c['bg_hover']};
            }}
            QPushButton#ghostBtn:disabled {{
                color: {c['text_disabled']};
                border-color: {c['border']};
            }}
        """)
        self._stats_label.setStyleSheet(
            f"color: {c['text_secondary']}; {tokens.font_css(12)};")
        for i in range(self._rows_layout.count()):
            w = self._rows_layout.itemAt(i).widget()
            if isinstance(w, _SnapshotRow):
                w.reapply_theme()
            elif isinstance(w, QLabel):
                self._apply_empty_style(w)
