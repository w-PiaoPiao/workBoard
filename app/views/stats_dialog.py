"""统计对话框：概览 / 30 天完成趋势（自绘柱状图）/ 分布条形 / 番茄统计

照日历视图同款挂载：非模态、控制器惰性创建并保持引用，数据经
set_summary 注入（app/models/stats.py 的 compute_stats 产物），
对话框不自持数据。图表用 QPainter 纯代码绘制（与桌宠同一约定，
不引第三方绘图库）。
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import tr
from app.views import tokens
from app.views.theme import AppTheme, to_qcolor


class _TrendBars(QWidget):
    """最近 N 天完成趋势柱状图（自绘；hover 显示"日期：张数"）

    零值日画 1px 底线灰点而非不画——否则长段空窗与"没数据"不可区分。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[date, int]] = []
        self._hover_idx: int | None = None
        self.setMouseTracking(True)   # 无按下也收 mouseMove，驱动 hover 提示
        self.setMinimumHeight(tokens.size(96))
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setAccessibleName(tr("最近 30 天完成趋势"))

    def set_data(self, data: list[tuple[date, int]]) -> None:
        self._data = list(data)
        self._hover_idx = None
        self.update()

    def paintEvent(self, event) -> None:
        if not self._data:
            return
        c = AppTheme.colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        n = len(self._data)
        pad_top = tokens.size(8)
        bar_area_h = self.height() - pad_top - tokens.size(4)
        slot = self.width() / n
        bar_w = max(2.0, slot * 0.62)
        peak = max(v for _d, v in self._data) or 1

        base_y = self.height() - tokens.size(4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # 基线
        painter.setPen(self._pen(c['border']))
        painter.drawLine(QPointF(0, base_y), QPointF(self.width(), base_y))
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (_d, v) in enumerate(self._data):
            x = i * slot + (slot - bar_w) / 2
            if v <= 0:
                # 零值：底线上的灰点
                painter.setBrush(self._brush(c['border']))
                h = 1.5
            else:
                painter.setBrush(self._brush(c['accent']))
                h = max(2.0, bar_area_h * (v / peak))
            path = QPainterPath()
            radius = min(tokens.radius('chip'), bar_w / 2, h / 2)
            path.addRoundedRect(QRectF(x, base_y - h, bar_w, h),
                                radius, radius)
            painter.drawPath(path)

    # QPainter 需要的是 QPen/QBrush；小包装避免每根柱重复构造同名参数
    @staticmethod
    def _pen(color: str) -> QPen:
        pen = QPen()
        pen.setColor(to_qcolor(color))
        return pen

    @staticmethod
    def _brush(color: str) -> QBrush:
        return QBrush(to_qcolor(color))

    def mouseMoveEvent(self, event) -> None:
        if not self._data:
            return
        idx = min(int(event.position().x() / (self.width()
                                              / len(self._data))),
                  len(self._data) - 1)
        idx = max(0, idx)
        if idx != self._hover_idx:
            self._hover_idx = idx
            d, v = self._data[idx]
            self.setToolTip(tr("{date}：完成 {n} 张").format(
                date=d.isoformat(), n=v))
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover_idx = None
        self.update()
        super().leaveEvent(event)


class _Bar(QWidget):
    """横向比例条（value/max 归一化宽度，自绘圆角矩形）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ratio = 0.0
        self.setMinimumHeight(tokens.size(10))
        self.setMaximumHeight(tokens.size(12))
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event) -> None:
        c = AppTheme.colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 底轨：全宽淡色，让"占比小"有参照而不只是一根短条
        painter.setBrush(QBrush(to_qcolor(c['border'])))
        track = QPainterPath()
        track.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            self.height() / 2, self.height() / 2)
        painter.drawPath(track)
        if self._ratio <= 0:
            return
        w = max(self.height(), self.width() * self._ratio)
        painter.setBrush(QBrush(to_qcolor(c['accent'])))
        bar = QPainterPath()
        bar.addRoundedRect(
            QRectF(0, 0, w, self.height()), self.height() / 2,
            self.height() / 2)
        painter.drawPath(bar)


class _DistributionRow(QWidget):
    """分布行：名称 + 比例条 + 数量"""

    def __init__(self, name: str, count: int, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self._name = QLabel(name)
        self._name.setMinimumWidth(tokens.size(96))
        self._name.setMaximumWidth(tokens.size(160))
        lay.addWidget(self._name, 0)
        self._bar = _Bar()
        lay.addWidget(self._bar, 1)
        self._count = QLabel(str(count))
        self._count.setMinimumWidth(tokens.size(28))
        lay.addWidget(self._count, 0)

    def set_theme_texts(self) -> None:
        c = AppTheme.colors()
        self._name.setStyleSheet(
            f"color: {c['text_primary']}; {tokens.font_css(12)};")
        self._count.setStyleSheet(
            f"color: {c['text_secondary']}; {tokens.font_css(12)};")

    def reapply_theme(self) -> None:
        self._bar.update()
        self.set_theme_texts()


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionTitle")
    return lbl


class StatsDialog(QDialog):
    """统计查看器：概览 + 趋势 + 分布 + 番茄（数据注入式，非模态）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("统计"))
        self.setModal(False)
        self.setMinimumSize(720, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(*tokens.dialog_margins(bottom_trim=2))
        root.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        page = QVBoxLayout(host)
        page.setContentsMargins(2, 2, 2, 2)
        page.setSpacing(6)

        # 概览：一段富文本行（读屏整行念出，无需逐 chip 命名）
        self._overview_label = QLabel()
        self._overview_label.setWordWrap(True)
        self._overview_label.setTextFormat(Qt.TextFormat.RichText)
        page.addWidget(self._overview_label)

        self._week_label = QLabel()
        page.addWidget(self._week_label)

        self._trend_title = _section_title(tr("最近 30 天完成趋势"))
        page.addWidget(self._trend_title)
        self._trend = _TrendBars()
        page.addWidget(self._trend)

        self._label_title = _section_title(tr("标签分布"))
        page.addWidget(self._label_title)
        self._label_host = QVBoxLayout()
        page.addLayout(self._label_host)

        self._list_title = _section_title(tr("列表分布"))
        page.addWidget(self._list_title)
        self._list_host = QVBoxLayout()
        page.addLayout(self._list_host)

        self._pomo_title = _section_title(tr("番茄专注"))
        page.addWidget(self._pomo_title)
        self._pomo_label = QLabel()
        self._pomo_label.setWordWrap(True)
        page.addWidget(self._pomo_label)

        page.addStretch(1)
        self._scroll.setWidget(host)
        root.addWidget(self._scroll, 1)

        self._label_rows: list[_DistributionRow] = []
        self._list_rows: list[_DistributionRow] = []
        self._empty_label: QLabel | None = None
        AppTheme.register(self.reapply_theme)
        self.reapply_theme()

    def retexts(self) -> None:
        self.setWindowTitle(tr("统计"))
        self._trend_title.setText(tr("最近 30 天完成趋势"))
        self._label_title.setText(tr("标签分布"))
        self._list_title.setText(tr("列表分布"))
        self._pomo_title.setText(tr("番茄专注"))
        self.reapply_theme()

    def set_summary(self, summary: dict | None) -> None:
        """注入 compute_stats 产物并重渲染（None = 空态）"""
        if not summary:
            self._render_empty()
            return
        if self._empty_label is not None:   # 空态 → 有数据：还原各分区
            self.layout().removeWidget(self._empty_label)
            self._empty_label.setParent(None)
            self._empty_label.deleteLater()
            self._empty_label = None
            for w in (self._trend_title, self._label_title,
                      self._list_title, self._pomo_title, self._trend,
                      self._overview_label, self._week_label,
                      self._pomo_label):
                w.show()
        ov = summary["overview"]
        self._overview_label.setText(
            tr("总 {total} 张 · 完成 {done} 张 · 逾期 {overdue} 张 · "
               "今日截止 {due_today} 张 · 今日完成 {done_today} 张").format(
                total=ov["total"], done=ov["done"], overdue=ov["overdue"],
                due_today=ov["due_today"], done_today=ov["done_today"]))
        self._week_label.setText(
            tr("本周完成 {this} 张 · 上周 {last} 张").format(
                this=summary["done_this_week"],
                last=summary["done_last_week"]))
        self._trend.set_data(summary["trend"])

        self._fill_rows(self._label_host, self._label_rows,
                        [(AppConfig.LABEL_NAMES.get(key, key), n)
                         for key, n in summary["label_counts"][:6]])
        self._fill_rows(self._list_host, self._list_rows,
                        [(name, active) for name, active, _total
                         in summary["list_counts"]])
        self._pomo_label.setText(self._pomo_text(summary))

    @staticmethod
    def _pomo_text(summary: dict) -> str:
        total = summary["pomo_total"]
        top = summary["pomo_top"]
        if not total:
            return tr("还没有完成的番茄钟：右键卡片「开始专注」即可开始")
        lines = [tr("累计 {n} 个番茄").format(n=total)]
        for title, n in top:
            lines.append(tr("{title} ×{n}").format(title=title, n=n))
        return "\n".join(lines)

    def _fill_rows(self, host: QVBoxLayout, rows: list,
                   items: list[tuple[str, int]]) -> None:
        """重建一组分布行（先清后建，值归一化到最大项）"""
        for row in rows:
            host.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        rows.clear()
        peak = max((n for _name, n in items), default=0) or 1
        for name, n in items:
            row = _DistributionRow(name, n)
            row._bar.set_ratio(n / peak)
            rows.append(row)
            host.addWidget(row)

    def _render_empty(self) -> None:
        """看板为空时的整页空态（隐藏各分区标题）"""
        if self._empty_label is not None:
            return
        for w in (self._trend_title, self._label_title, self._list_title,
                  self._pomo_title, self._trend, self._overview_label,
                  self._week_label, self._pomo_label):
            w.hide()
        self._fill_rows(self._label_host, self._label_rows, [])
        self._fill_rows(self._list_host, self._list_rows, [])
        self._empty_label = QLabel(
            tr("还没有卡片数据：回到看板添加卡片后这里会出现统计"))
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        self.layout().addWidget(self._empty_label)

    def reapply_theme(self) -> None:
        c = AppTheme.colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {c['bg_primary']}; }}
            QLabel {{ color: {c['text_primary']}; }}
            QLabel#sectionTitle {{
                color: {c['text_secondary']};
                {tokens.font_css(12)};
                {tokens.pad_all(6)};
            }}
        """)
        self._overview_label.setStyleSheet(
            f"color: {c['text_primary']}; {tokens.font_css(13)};")
        self._week_label.setStyleSheet(
            f"color: {c['text_secondary']}; {tokens.font_css(12)};")
        self._pomo_label.setStyleSheet(
            f"color: {c['text_secondary']}; {tokens.font_css(12)};")
        self._trend.update()
        for row in (*self._label_rows, *self._list_rows):
            row.reapply_theme()
