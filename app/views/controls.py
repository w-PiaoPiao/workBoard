"""设置界面通用控件：滑动开关 / 分段按钮

配色实时取 AppTheme（paintEvent 内取色），样式风格与看板 accent
体系一致。控件不自行注册主题回调——由持有一个 SettingsDialog 单例
的宿主在主题回调里统一调 reapply_theme()，避免一次性对话框泄漏监听。
"""

from __future__ import annotations

import logging
import math

from PySide6.QtCore import (QPointF, QEasingCurve, QEvent, QRect, QRectF, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox,
                               QDateEdit, QFrame, QHBoxLayout, QPushButton,
                               QSpinBox)

from app.config import AppConfig
from app.i18n import tr
from app.views import motion, tokens
from app.views.theme import AppTheme, to_qcolor

logger = logging.getLogger(__name__)


class _WheelIgnoreMixin:
    """滚轮/触控板滑动不再改值，事件穿透给父级（滚动区继续滚动）

    Qt 的 QAbstractSpinBox/QComboBox 默认对**悬停**（无需焦点）的滚轮
    事件直接增减值——mac 触控板双指滑动划过资金环节列表时，18 个办理
    日期框会被误改（Windows 鼠标滚轮同理，行为在 Qt 层跨平台一致）。
    日历弹窗、键盘上下键、下拉列表仍是完整的调值入口。
    """

    def wheelEvent(self, event) -> None:
        event.ignore()   # 不消费：父级（如对话框的滚动区）接手继续滚动


class DateEdit(_WheelIgnoreMixin, QDateEdit):
    """带日历弹窗的日期框（yyyy-MM-dd），滚轮/触控板滑动不改值"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setCurrentSection(QDateEdit.MonthSection)


class ComboBox(_WheelIgnoreMixin, QComboBox):
    """滚轮/触控板滑动不切项的下拉框（点开列表选择）"""


class SpinBox(_WheelIgnoreMixin, QSpinBox):
    """滚轮/触控板滑动不改值的数字框（键盘上下键/直接输入可用）"""


def _lerp_rect(a: QRectF, b: QRectF, t: float) -> QRectF:
    """高亮块滑动插值（QVariantAnimation 只给进度，几何自己算）"""
    return QRectF(a.x() + (b.x() - a.x()) * t,
                  a.y() + (b.y() - a.y()) * t,
                  a.width() + (b.width() - a.width()) * t,
                  a.height() + (b.height() - a.height()) * t)


class ToggleSwitch(QAbstractButton):
    """iOS 风格滑动开关（自绘轨道 + 圆形滑块，120ms 滑动动画）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0        # 滑块位置 0..1（动画插值）
        # 动画单实例复用（构造一次，随控件析构）：此前每次切换临时新建
        # QVariantAnimation 并 deleteLater，而点击路径在 C++ click() 内部
        # 同步走到这里——真机 cocoa 下会触发 PySide6 的 override 失效段
        # 错误（点击开关整只闪退，表现为"圆点没反应"），复用从结构上消除
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.setFixedSize(44, 26)

    def _set_pos(self, v: float) -> None:
        self._pos = v
        self.update()

    def reapply_theme(self) -> None:
        self.update()

    def set_accessible_text(self, name: str, description: str = "") -> None:
        """读屏文本入口：名称（设置行标题）+ 描述（行说明）

        `QWidget.setAccessibleName` 本身就能用，这里再包一层是因为设置页
        每一行都是"标题 + 说明"两段，调用点需要一次给全（见
        `settings_dialog._Section.add_row`）。
        """
        self.setAccessibleName(name)
        if description:
            self.setAccessibleDescription(description)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = AppTheme.colors()
        # 色值可能含半透明 rgba()（mask/mask_hover），须走 to_qcolor：
        # QColor 直接构造解析失败会画成纯黑（关闭态轨道曾整条发黑）
        track = to_qcolor(c["accent"] if (self.isChecked() or self._pos > 0.5)
                          else c["mask_hover"])
        if not self.isEnabled():
            track = to_qcolor(c["mask"])
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                                self.height() / 2, self.height() / 2)
        # 滑块：左右各留 3px 边距，直径 = 高 - 6
        d = self.height() - 6
        x = 3 + self._pos * (self.width() - d - 6)
        # 滑块取 accent_on：写死白色时，浅色皮肤关闭态（浅灰轨道）
        # 对比度仅约 1.4:1，几乎看不见
        painter.setBrush(to_qcolor(c["accent_on"]))
        painter.drawEllipse(QRectF(x, 3, d, d))
        # 焦点环：自绘控件没有系统焦点提示，键盘用户看不出焦点落在哪个开关
        if self.hasFocus():
            painter.setPen(QPen(to_qcolor(c["focus_ring"]), 1.5))
            painter.setBrush(Qt.NoBrush)
            ring = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
            painter.drawRoundedRect(ring, ring.height() / 2, ring.height() / 2)
        painter.end()

    def _animate_to(self, target: float) -> None:
        if self._anim.state() == QVariantAnimation.Running:
            self._anim.stop()
        if not motion.enabled():
            # "暂停动画"总开关：开关滑块同样瞬时落位（此前只有本控件漏检）
            self._set_pos(target)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def setChecked(self, on: bool) -> None:   # type: ignore[override]
        # super() 在状态变化时自动 emit toggled，这里只负责滑动动画
        super().setChecked(on)
        self._animate_to(1.0 if on else 0.0)


class SegmentedControl(QFrame):
    """分段按钮组（单选）：胶囊容器 + checkable 按钮 + 会滑动的选中高亮块

    options: [(value, label), ...]；label 可后续经 retexts() 更新
    （语言切换）。按钮自身样式由宿主下发（#segmentBtn 选择器）。

    **高亮块由本控件自绘**：QSS 只能给按钮贴静态样式，选中态是"原地出现
    的边框"，点另一侧时看不出选中项换了哪边（选项只有两三个字、挨在一起
    时尤其像没反应）。故按钮一律透明、只负责文字，容器在它们背后画一块
    会滑过去的药丸，切换方向一眼可见。宿主须把 #segmentBtn:checked 的
    背景与边框置空（见 settings_dialog._build_qss），否则与自绘块叠两层。

    滑动只在**用户点击**时播（点哪儿滑哪儿）；set_value 是同步真实偏好、
    布局变化是重排，都必须瞬时落位——否则"打开设置"这个动作本身就在动画。

    几何**不缓存**：静止时每次绘制现取选中按钮的 geometry，只在动画期间用
    插值。缓存过一次就错过——Qt 可能先把容器的 resize 事件发出来、之后才
    activate 布局（macOS 实测如此），在 resizeEvent 里读按钮几何拿到的是中间
    态，高亮块会偏差几个像素；而布局落位按钮本身不会惊动容器的 resizeEvent，
    没有任何时机能补上这一笔。改为监听按钮自身的 Move/Resize 触发重绘（见
    eventFilter），绘制时现取，偏差从结构上不可能发生。

    **键盘可达**：容器是这一组的唯一 tab 站（`Qt.StrongFocus`），左右/上下
    方向键在选项间移动并广播 `changed`，Home/End 跳首尾；焦点在容器或任一
    按钮上时画一圈 focus_ring。按钮自身是 `Qt.ClickFocus`——点击后焦点会落到
    按钮上（读屏按单个按钮播报），但不各占一个 tab 站，否则三组设置会把 Tab
    链切得又长又碎。
    """

    changed = Signal(str)   # 新选中的 value

    def __init__(self, options: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self._values = [v for v, _ in options]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for value, label in options:
            btn = QPushButton(label)
            btn.setObjectName("segmentBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.ClickFocus)
            btn.setAccessibleName(label)     # 读屏按按钮播报选项名
            btn.clicked.connect(lambda _=False, v=value: self._on_clicked(v))
            btn.installEventFilter(self)   # 布局落位 → 重绘（见 eventFilter）
            self._group.addButton(btn)
            self._buttons[value] = btn
            lay.addWidget(btn)
        self._pill = QRectF()            # 仅动画期间有效：插值中的高亮块几何
        self._pill_from = QRectF()       # 动画插值的起/终点（_move_pill 设定）
        self._pill_to = QRectF()
        self._selected: str | None = None
        # 同 ToggleSwitch：动画单实例复用，不在 C++ 点击路径内新建/销毁
        # QObject（PySide6 真机 cocoa 下会触发 override 失效段错误）
        self._pill_anim = QVariantAnimation(self)
        self._pill_anim.setDuration(AppConfig.SEGMENT_PILL_MS)
        self._pill_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._pill_anim.valueChanged.connect(self._on_pill_tick)
        self._pill_anim.finished.connect(self._on_pill_done)

    # ── 高亮块 ────────────────────────────────────────────

    def _on_clicked(self, value: str) -> None:
        self._move_pill(value, animate=True)
        self.changed.emit(value)

    # ── 键盘可达 ──────────────────────────────────────────

    def _focused(self) -> bool:
        """焦点在容器上或任一按钮上

        按钮是 ClickFocus：点一下焦点就进了按钮，此时焦点环不能消失。
        """
        if self.hasFocus():
            return True
        return any(b.hasFocus() for b in self._buttons.values())

    def _select(self, value: str, animate: bool) -> None:
        """置为选中（含按钮 checked 态与高亮块）

        点击路径由 Qt 先翻转 checked，键盘/程序路径必须自己补这一步——
        少了它高亮块会动、按钮文字色却还停在旧项上。
        """
        btn = self._buttons.get(value)
        if btn is None:
            return
        if not btn.isChecked():
            btn.setChecked(True)
        self._move_pill(value, animate=animate)

    def _step(self, step: int) -> None:
        """按 step 移动选中项（首尾环绕）并广播 changed"""
        if not self._values:
            return
        current = self.value()
        if current in self._values:
            idx = self._values.index(current)
        else:
            idx = -step      # 尚未选中任何一项：下一步落在首项
        self._emit_select(self._values[(idx + step) % len(self._values)])

    def _emit_select(self, value: str) -> None:
        self._select(value, animate=True)
        self.changed.emit(value)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Up):
            self._step(-1)
        elif key in (Qt.Key_Right, Qt.Key_Down):
            self._step(1)
        elif key == Qt.Key_Home and self._values:
            self._emit_select(self._values[0])
        elif key == Qt.Key_End and self._values:
            self._emit_select(self._values[-1])
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def _paint_rect(self) -> QRectF:
        """本次绘制该画的高亮块几何

        静止时现取选中按钮的 geometry——**不缓存**：布局落位按钮的时机既不在
        容器的 resizeEvent 里、也不保证任何时点能补上，缓存值会停在中间态
        （macOS 实测偏 2px，CI 抓到）。动画期间才用插值。
        """
        if self._pill_anim.state() == QVariantAnimation.Running:
            return QRectF(self._pill)
        btn = self._buttons.get(self._selected) if self._selected else None
        return QRectF(btn.geometry()) if btn is not None else QRectF()

    def _move_pill(self, value: str, animate: bool) -> None:
        btn = self._buttons.get(value)
        if btn is None:
            return
        start = self._paint_rect()          # 此刻 _selected 仍是旧值
        self._selected = value
        target = QRectF(btn.geometry())
        if self._pill_anim.state() == QVariantAnimation.Running:
            self._pill_anim.stop()
        # 无起点（布局还没跑过）/ 原地 / 非用户点击 / "暂停动画"总开关：
        # 一律瞬时落位，把几何交回"绘制时现取"
        if (start.isNull() or start == target or not animate
                or not motion.enabled()):
            self._pill = QRectF()
            self.update()
            return
        self._pill_from, self._pill_to = start, target
        self._pill = start          # 起播首帧就有几何，不留空窗
        self._pill_anim.start()

    def _on_pill_tick(self, t: float) -> None:
        """动画推进：只改插值几何"""
        self._pill = _lerp_rect(self._pill_from, self._pill_to, float(t))
        self.update()

    def _on_pill_done(self) -> None:
        # 终点交还给按钮自己：动画的值只是过渡，最终几何以布局为准
        self._pill = QRectF()
        self.update()

    def paintEvent(self, event) -> None:
        # 基类先画（宿主将来若给容器下发底色，高亮块才不会压在它下面）
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = AppTheme.colors()
        r = tokens.radius('pill')
        rect = self._paint_rect()
        if rect.isEmpty():
            # 还没选中任何一项：焦点环画在整组外框上，否则键盘用户看不到焦点
            if self._focused():
                self._paint_focus_ring(painter, QRectF(self.rect()), r)
            painter.end()
            return
        # accent_soft 是半透明 rgba() 色值：QColor 直接构造会解析失败画成
        # 纯黑（选中高亮块曾整块发黑），必须走 to_qcolor
        painter.setPen(QPen(to_qcolor(c["accent"]), 1.5))
        painter.setBrush(to_qcolor(c["accent_soft"]))
        painter.drawRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), r, r)
        if self._focused():
            self._paint_focus_ring(painter, rect, r)
        painter.end()

    @staticmethod
    def _paint_focus_ring(painter: QPainter, rect: QRectF, radius: float) -> None:
        """焦点环：贴着选中块外沿描一圈 focus_ring

        与高亮块同一套圆角（tokens.radius('pill')），只描边不填充；
        容器四周留了 3px 内边距，外扩 1.2px 不会画出控件之外。
        """
        ring = rect.adjusted(-1.2, -1.2, 1.2, 1.2)
        painter.setPen(QPen(to_qcolor(AppTheme.colors()["focus_ring"]), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(ring, radius + 1.2, radius + 1.2)

    def eventFilter(self, obj, event) -> bool:
        """按钮被布局挪动/改尺寸 → 重绘高亮块；焦点进出 → 重绘画焦点环

        容器自身的 resizeEvent 不是可靠时机（Qt 可能先发它、之后再 activate
        布局，见类注释），盯按钮自己的 Move/Resize 才对得上。
        """
        etype = event.type()
        if etype in (QEvent.Move, QEvent.Resize) and self._selected is not None:
            self.update()
        elif etype in (QEvent.FocusIn, QEvent.FocusOut):
            # 按钮是 ClickFocus：点击后焦点进按钮，焦点环得跟着亮/灭
            self.update()
        elif etype == QEvent.KeyPress and obj in self._buttons.values():
            # 焦点已在某个按钮上时方向键仍由容器处理（否则按了没反应）
            self.keyPressEvent(event)
            return event.isAccepted()
        return super().eventFilter(obj, event)

    def set_value(self, value: str) -> None:
        """同步真实偏好：静音（不发 changed）+ 瞬时落位

        未知值回退首项。此前直接 return，控件会停在"零选中"——高亮块留在
        上一次的位置、没有任何按钮是 checked，界面呈现的是一个**假状态**；
        偏好被手工改坏或新旧版本取值不一致时就会看到它。
        """
        if value not in self._buttons:
            logger.warning("SegmentedControl 收到未知取值 %r（合法值 %r），回退首项",
                           value, self._values)
            if not self._values:
                return
            value = self._values[0]
        self._select(value, animate=False)   # 同步路径不播动画

    def value(self) -> str | None:
        for v, btn in self._buttons.items():
            if btn.isChecked():
                return v
        return None

    def retexts(self, options: list[tuple[str, str]]) -> None:
        """语言切换后更新按钮文案（value 顺序须与构造时一致）"""
        for value, label in options:
            btn = self._buttons.get(value)
            if btn is not None:
                btn.setText(label)
                btn.setAccessibleName(label)   # 读屏名与显示文案同源

    def reapply_theme(self) -> None:
        # 样式表由 SettingsDialog 统一下发（子控件继承），此处仅重绘
        self.update()


class CardCheckButton(QPushButton):
    """自绘勾选框（替代 ☐/☑ 字形，跨平台渲染一致）

    完成瞬间对勾按路径描画（140ms）：勾选完成是最高频的正反馈动作，
    瞬时划线的满足感不足；描画进度由 _check_progress 驱动，可被
    "暂停动画"开关跳过。
    """

    _P0 = (3.6, 8.2)     # 对勾折点序列（相对勾选框左上角）
    _P1 = (7.0, 11.4)
    _P2 = (12.6, 4.6)
    # 两段折线长度为常量（P 序列恒定）：paintEvent 每帧 math.hypot 纯浪费
    _P01 = math.hypot(_P1[0] - _P0[0], _P1[1] - _P0[1])
    _P12 = math.hypot(_P2[0] - _P1[0], _P2[1] - _P1[1])

    # 完整对勾路径缓存（(0,0) 原点，绘制时 translate 到框左上角）：
    # 完成态 progress 恒为 1，逐帧新建 QPainterPath 纯重复
    _CHECK_PATH_FULL: QPainterPath | None = None

    # 对勾色：压在 success 填充上。深色主题的 success 是亮绿，白对勾只有
    # 1.99:1——勾选框的整个意义就是那个对勾，却在深色下几乎看不见。
    # 与主按钮同思路：填充亮时文字反相。
    @staticmethod
    def _check_color() -> QColor:
        return QColor(AppTheme.colors()["success_on"])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlat(True)
        # 命中区 24×24（可点击标准），视觉勾选框仍是 16px 居中绘制——
        # 这是全板最高频的操作，此前 20×20 是整个界面上最小的目标之一
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("点击切换完成状态"))
        # 可 check：QPushButton 不可 check 时读屏只报 "button"，
        # 永远不报勾选状态——完成与否只由绿底对勾承载（标题不做删除线），
        # 非视觉用户拿不到这个信息。setCheckable 让 QAccessible 暴露 checked。
        self.setCheckable(True)
        self.setAccessibleName(tr("切换完成状态"))
        self._done = False
        self._check_anim: QVariantAnimation | None = None
        self._check_progress = 1.0   # 对勾描画进度 0..1（1=完整对勾）

    def retexts(self) -> None:
        """语言切换：读屏名与 tooltip 是构造期定格的，需要重设"""
        self.setToolTip(tr("点击切换完成状态"))
        self.setAccessibleName(tr("切换完成状态"))

    def enterEvent(self, event) -> None:
        """悬停变色必须自己请求重绘

        paintEvent 里按 `underMouse()` 取 accent 色，但没有 enter/leave
        时不会有人来触发重绘——悬停高亮要等别的控件恰好让本卡重画才出现，
        而这是全板最高频的操作，反馈不能是"看运气"。
        """
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()

    def set_done(self, done: bool) -> None:
        if self._done == done:
            return
        self._done = done
        self.setChecked(done)       # 同步给无障碍层
        self.update()
        if done and motion.enabled():
            self._start_check_anim()
        else:
            self._stop_check_anim()

    def _start_check_anim(self) -> None:
        self._stop_check_anim()
        anim = QVariantAnimation(self)
        anim.setDuration(140)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_check_tick)
        anim.finished.connect(lambda: self._stop_check_anim())
        self._check_anim = anim
        self._check_progress = 0.0
        anim.start()

    def _stop_check_anim(self) -> None:
        anim = self._check_anim
        if anim is not None:
            anim.stop()
            anim.deleteLater()
            self._check_anim = None
        self._check_progress = 1.0
        self.update()

    def _on_check_tick(self, value) -> None:
        self._check_progress = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = AppTheme.colors()
        box = QRect((self.width() - 16) // 2, (self.height() - 16) // 2, 16, 16)
        # 勾选框外形随皮肤：rounded 圆角方框（默认）/ square 直角方框
        # （终端、粗野：这两个皮肤里任何圆角都会显得"没换干净"）。
        radius = 4.5 if AppTheme.shape()["check_style"] != "square" else 0.0
        if self._done:
            # 完成：主题色填充 + 对勾（按描画进度截取路径）
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(c["success"]))
            painter.drawRoundedRect(box, radius, radius)
            # 对勾色随主题：深色的 success 是亮绿，白对勾只有 1.99:1
            pen = _CHECK_PENS.get(c["success_on"])
            if pen is None:
                pen = QPen(self._check_color(), 1.8)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                _CHECK_PENS[c["success_on"]] = pen
            painter.setPen(pen)
            total = self._P01 + self._P12
            d = self._check_progress * total
            if d >= total:
                # 动画结束后的常态：直接用缓存完整路径
                if CardCheckButton._CHECK_PATH_FULL is None:
                    path = QPainterPath(QPointF(*CardCheckButton._P0))
                    path.lineTo(QPointF(*CardCheckButton._P1))
                    path.lineTo(QPointF(*CardCheckButton._P2))
                    CardCheckButton._CHECK_PATH_FULL = path
                painter.save()
                painter.translate(box.topLeft())
                painter.drawPath(CardCheckButton._CHECK_PATH_FULL)
                painter.restore()
            else:
                bx, by = box.left(), box.top()
                p0 = QPointF(bx + self._P0[0], by + self._P0[1])
                p1 = QPointF(bx + self._P1[0], by + self._P1[1])
                p2 = QPointF(bx + self._P2[0], by + self._P2[1])
                path = QPainterPath()
                path.moveTo(p0)
                if d <= self._P01:
                    t = (d / self._P01) if self._P01 > 0 else 1.0
                    path.lineTo(p0 + (p1 - p0) * t)
                else:
                    t = ((d - self._P01) / self._P12) if self._P12 > 0 else 1.0
                    path.lineTo(p1)
                    path.lineTo(p1 + (p2 - p1) * t)
                painter.drawPath(path)
        else:
            # 未完成：圆角方框，悬停变主题色
            hex_color = c["accent"] if self.underMouse() else c["text_disabled"]
            pen = _CHECK_BOX_PENS.get(hex_color)
            if pen is None:
                pen = QPen(QColor(hex_color), 1.5)
                _CHECK_BOX_PENS[hex_color] = pen
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(box, radius, radius)
        painter.end()


# 完成态对勾画笔按颜色缓存：颜色随主题变（success_on），
# 每帧新建 QPen + 设 cap/join 是纯重复；QPen 值语义，多控件共享安全
_CHECK_PENS: dict = {}

# 未完成态勾选框画笔按颜色 hex 缓存：paintEvent 每帧新建 QPen 纯重复
# （hex 键随主题切换自动换 key，同 _CHECK_PEN 的类常量范式，但颜色取自
# 主题调色板，不能一次性定为类常量）
_CHECK_BOX_PENS: dict[str, QPen] = {}
