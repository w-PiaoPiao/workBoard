"""批量归档对话框：在「已完成」列里勾选卡片，一次归档

设计取舍：勾选式列表而不是"全选即归档"——已完成列里往往混着"这周还要
回看"的卡片，批量归档必须允许只挑一部分；全选/清空是两个快捷按钮，
默认全不选（归档是离开看板的动作，默认不替用户做决定）。

对话框只负责收集意图，实际归档与撤销快照由控制器统一处理（与批量编辑
对话框的 result 回传范式一致）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.models.board import Card
from app.views import tokens
from app.views.quick_add_dialog import _input_dialog_style
from app.views.theme import AppTheme, primary_button_style


class BatchArchiveDialog(QDialog):
    """已完成列的批量归档：逐张勾选后一次归档"""

    def __init__(self, cards: list[Card], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("批量归档已完成卡片"))
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self._boxes: list[tuple[QCheckBox, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(*tokens.dialog_margins(bottom_trim=2))
        root.setSpacing(8)

        hint = QLabel(tr("勾选要归档的卡片，归档后可在归档区恢复"))
        hint.setObjectName("bulkHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        host.setObjectName("bulkHost")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(4)
        for card in cards:
            box = QCheckBox(card.title)
            box.setCursor(Qt.PointingHandCursor)
            box.setAccessibleName(
                tr("归档 {title}").format(title=card.title))
            done_day = (card.done_at or "")[:10]
            if done_day:
                box.setToolTip(
                    tr("{title}\n完成于 {date}").format(
                        title=card.title, date=done_day))
            box.toggled.connect(self._update_state)
            self._boxes.append((box, card.id))
            lay.addWidget(box)
        lay.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        # 快捷选择 + 计数
        tools = QHBoxLayout()
        tools.setSpacing(6)
        self._all_btn = QPushButton(tr("全选"))
        self._all_btn.setObjectName("bulkToolBtn")
        self._all_btn.setCursor(Qt.PointingHandCursor)
        self._all_btn.clicked.connect(lambda: self._set_all(True))
        self._none_btn = QPushButton(tr("清空选择"))
        self._none_btn.setObjectName("bulkToolBtn")
        self._none_btn.setCursor(Qt.PointingHandCursor)
        self._none_btn.clicked.connect(lambda: self._set_all(False))
        tools.addWidget(self._all_btn)
        tools.addWidget(self._none_btn)
        tools.addStretch(1)
        self._count_label = QLabel()
        self._count_label.setObjectName("bulkCount")
        tools.addWidget(self._count_label)
        root.addLayout(tools)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("取消"))
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        self._ok_btn = QPushButton(tr("归档"))
        self._ok_btn.setDefault(True)
        self._ok_btn.setCursor(Qt.PointingHandCursor)
        self._ok_btn.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(self._ok_btn)
        root.addLayout(btns)

        self._update_state()
        self.reapply_theme()

    # ── 交互 ──────────────────────────────────────────────

    def _set_all(self, checked: bool) -> None:
        """全选/清空：只翻状态，逐项 toggled 会累积刷新计数（可接受）"""
        for box, _cid in self._boxes:
            box.setChecked(checked)

    def _update_state(self) -> None:
        n = len(self.selected_ids())
        self._count_label.setText(tr("已选 {n} 张").format(n=n))
        self._ok_btn.setEnabled(n > 0)
        self._all_btn.setEnabled(n < len(self._boxes))
        self._none_btn.setEnabled(n > 0)

    # ── 结果 ──────────────────────────────────────────────

    def selected_ids(self) -> list[str]:
        return [cid for box, cid in self._boxes if box.isChecked()]

    # ── 主题 ──────────────────────────────────────────────

    def reapply_theme(self) -> None:
        c = AppTheme.colors()
        # 滚动区与勾选行必须显式透明：QScrollArea 默认画白底，深色主题下
        # 会露出整块白板（同日历/归档对话框的处理）
        self.setStyleSheet(
            _input_dialog_style(c)
            + f"""
            QScrollArea, QScrollArea > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
            QWidget#bulkHost {{ background: transparent; }}
            QCheckBox {{
                color: {c['text_primary']};
                {tokens.font_css(12)};
                {tokens.pad(5, 4)};
            }}
            QCheckBox:hover {{ color: {c['accent']}; }}
            """)
        self._ok_btn.setStyleSheet(primary_button_style(c))
