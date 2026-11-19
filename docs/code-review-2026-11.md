# 桌宠看板 · 全代码库审计报告（2026-11-18）

> 方法：六路并行子系统审计（A 看板核心 / B 控制器与启动 / C 主窗口与桌宠 /
> D 对话框族 / E 数据层 / F 基础设施），覆盖 `app/` 全部 43 个模块 + `main.py` +
> 打包与 CI 脚本，约 2.3 万行全文通读（审计型任务，按仓库规约走 read/grep，
> 不用 codegraph 摘录）。
>
> 分级：P0 正确性缺陷（行为与设计意图不符/丢数据/崩溃）；P1 健壮性风险
> （边界条件、失败模式、可达性缺口）；P2 架构与可维护性；P3 性能；
> P4 清理（死代码、误导注释、口径漂移）。
>
> 配套路线图见 `docs/optimization-plan.md`（按本报告编号引用）。
>
> 复核口径：根代理对**全部 P0/P1 共 17 条逐条亲读引用行复核，零误报**；
> 另亲验 P2 四条（E-02/E-03/E-04/C-4）与 P4 两条（C-7/F-14）；其余 P2/P3/P4
> 沿用子审计证据（各行号均为审计者本人通读所得）。

## 0. 摘要

- **发现总计 95 条**：P0×1、P1×16、P2×28、P3×14、P4×36。
- **总体评价**：数据层（原子写/损坏隔离/恢复链/迁移一次性）与主题/token/皮肤
  体系实现质量高，历次「审查修复批次」的修复点复核全部在位；债务集中在三处——
  ①巨型文件继续膨胀（board_view **4986 行**、app_controller **3574 行**、
  config **1515 行**，均比 README 口径多 300~500 行）；②撤销栈「空操作 pop」
  族缺口与若干失败路径收口漏网；③**计划文档声称已修但从未落地**的口径漂移
  （见 §7，共 12 条）。
- **规模修正**：board_view.py 4466→4986 行；config.py 1380→1515 行；
  card_dialog.py 1142→1249 行；i18n.py 951→999 行；calendar_view.py 714→807 行；
  settings_dialog.py 657→710 行；pet_view.py 858→979 行；main_window.py 793→887 行。
- **测试基线**：DSH 沙箱内离屏跑全量 = **757 项，13F / 104E / 12S，1734s**。
  逐条抽查可见失败头，全部归两类环境噪音：沙箱拒绝临时目录写入
  （test_workspace×17、test_lists_templates×8、test_single_instance×5、
  test_workspace_backup×4、test_stats×2、test_autostart×2、test_restore_flow×1，
  均为 `WinError 5 / Errno 13` 拒绝 `%TEMP%\dsh-*` 下的写入/清理）与
  d46afb5 已登记的 2 项离屏无字体 flaky（多选栏、工具栏溢出恢复）。
  **无产品级新增红灯**；但 discover 实收 757 项与 README「约 930 项」不符
  （无 import 失败，见 §7 口径漂移）。无沙箱终端的基线仍以 CI 口径为准。

## 1. P0（1 条）

### C-1 展开态的位置持久化/隐藏恢复与桌宠原位语义错位（三条旁路）

`main_window.py:527-531`（另 584-592、634）｜三条旁路均偏离 137-139 注释
声明的设计意图（「折叠落点以 `_pet_home_geo` 为准」）。

- 证据：展开态拖动看板后 `_save_position()` 持久化的是**看板左上角**；
  hideEvent 折叠分支（584-592）只切视图 + `setFixedSize`，**不落位也不保存**；
  `_on_animation_finished` 折叠分支（634）只有 `_snap_to_screen_edge()` 无保存。
  而 137-139 注释明确设计意图：「折叠落点以 `_pet_home_geo` 为准」。
- 影响三条路径：①展开态 ✕/托盘隐藏 → 重显时桌宠停在看板左上角而非原位；
  ②展开态拖动后退出 → 重启桌宠出现在看板旧址；③展开动画中隐藏 → 停在中间帧。
- 修复方向：hideEvent 折叠分支与动画收尾按 `_pet_home_geo` 落位并补保存，
  或 `_save_position` 仅在 collapsed 模式调用。
- 测试：无（`CollapseInterruptTest` 只断言尺寸）。补「展开→拖动→hide→show
  →位置==home」「展开→拖动→collapse→save_window_pos 收到 home」两用例。

## 2. P1（16 条）

### B-1 退出路径最后一次落盘失败的托盘通知发在托盘已隐藏之后

`app_controller.py:3563-3571`（关联 497-499）｜`_on_quit` 先 `self._tray.hide()`
再 `QApplication.quit()`；落盘失败通知在 aboutToQuit 里才发——隐藏后的托盘
气泡（Windows）不显示。磁盘满时退出 = 编辑丢失且无提示，README「保存失败
不会静默丢写」在退出路径失效。修：`hide()` 挪到落盘成功之后，或改非模态
QMessageBox。测试：`test_flush_failure_notifies_user` 只盖异步路径，补 quit
强 flush 抛 StoreError 的通知出口断言。

### B-2 空操作 pop 只弹撤销栈不清 `_pending_undo_doc`，其后一次语言切换误清重做栈

`app_controller.py:1123` 等 12 处 pop 站点｜`_push_undo`（2670-2672）设立
pending；`_after_data_change`（2106-2112）见 pending 即清 redo；pop 站点
（1123、1454、1471、1591、1612、1633、1655、1671、1691、1725、3191、3310）
全部不重置 pending；`_on_language_changed`（2373）是全文件唯一不先 push 的
`_after_data_change` 调用方。触发链：撤销 → 空操作（如拖卡回原位 pop@1471）→
切语言 → **重做历史被清空** + 一次无意义落盘（联动 B-9）。修：抽
`_cancel_pending_undo()` 统一 12 处。测试：补「undo → 拖回原位 → 切语言 →
redo 仍可用」。

### B-3 `_on_import_backup` 不处理 `_activate_board` 失败，`current_id` 悬空

`app_controller.py:3408-3411`｜`Workspace.create_board` 已把 `current_id` 指向
新板（`workspace.py:287`），激活失败时索引与 store 脱钩——此后任何
`_apply_board_to_ui` 把旧板内容挂新板名下、重命名改错 meta、重启后「编辑
丢失」（写进旧板文件）。同仓两个调用方（636-641、804-808）都有
`set_current(self._store_board_id)` 回滚，唯此调用点漏。修：同款回滚。
测试：patch `_activate_board` 返回 False，断言回滚。

### B-4 批量编辑在对话框后沿用会话前的 card 对象写入（孤儿写入）

`app_controller.py:3156-3194`｜`board = self._store.load()` 取引用 →
`dlg.exec()` 嵌套事件循环（托盘撤销 / macOS ⌘Z 期间可达）→ `for card in cards`
未按 id 重定位。改动写进孤儿对象、UI 从新板刷新不可见、toast 却报成功。
批次 3 已给 `_on_card_edit`（1270）与批量归档（1713）补同款守卫，此处漏网。
修：exec 后按 id 重取，缺席即取消。测试：补「exec 期间 replace_board」用例。

### A-1 `motion._drop_effect` 对已销毁控件的 getattr 未包 try

`motion.py:49`｜shiboken 包装器 C++ 对象销毁后属性访问抛 `RuntimeError`，
`getattr` 默认值只兜 `AttributeError`；`try` 恰好包在下一行。fade_in 完成与
`singleShot(0)` 回调之间控件被销毁（160ms 窗口内过滤切换 `_dispose_card_widgets`）
→ 未处理异常。修：getattr 挪进 try 或先 `shiboken6.isValid`。测试：补
「fade 完成 → deleteLater → 事件循环一轮不抛」。

### A-2 外部 MIME 单卡/整列 payload 解码无异常护栏（组拖有、单卡没有）

`board_view.py:3191、3206、3255-3256`（对照 3174-3177、3250-3254 有护栏）｜
自定义 MIME 名无认证，任意外部进程可携带畸形字节拖入；`UnicodeDecodeError`
在原生拖拽循环中逸出。同文件对 MIME_CARDS 已设防，说明是遗漏非设计。
同族：`calendar_view.py:468` 同样裸解码。修：统一 decode 助手收口四处。
测试：`test_drag_extras.py:135` 只测组拖，补单卡/整列/日历畸形用例。

### A-3 `_drop_mids` 快照假设拖拽期间布局不变，与同文件自认的 exec 循环矛盾

`board_view.py:3094` vs `1629-1633`｜3094 注释宣称「快照全程有效」，1629-1633
自认「exec 的原生模态循环仍处理 Qt 事件、刷新可能已销毁本卡」。拖拽中途任何
refresh（跨天自动归档、拖拽中 Ctrl+Z）后快照过期，bisect 落点整体偏一位。
数据不丢、可撤销。修：dragMove 时 O(n) 校验快照一致，不一致就地重建。

### C-2 nudge 与 celebrate 并发竞态：提醒跳起可闯入庆祝动画（原判 P0，按影响调为 P1）

`pet_view.py:758-759`｜`nudge` 只查 `_active_action` 不查 `_celebrating`
（798-803 独立挂牌）；提醒每分钟检查（`app_controller.py:2913-2914`）+
全部完成庆祝（1405-1406）同折叠态可达。两组动画并发驱动 `offsetY` 约 1.3s，
逐帧互覆盖、视觉抖动。影响为亚秒级视觉瑕疵、无数据面，故调 P1。修：nudge
开头加 `if self._celebrating is not None: return`。测试：全 tests 无 nudge/
celebrate 用例，补一条。

### C-3 桌宠禁用（Windows）隐藏→重显后边缘光标轮询不再启动

`main_window.py:355-356`（关联 326、567-568、570-583）｜轮询唯一启动点在
`expand()`；pet 禁用时 hideEvent 保持 expanded 模式，托盘重显走
`_open_in_default_view` → `expand()` 在 326 因已是 expanded **提前返回** →
`_edge_cursor_timer` 从此停摆。该轮询是系统缩放循环后 hover 链重建的兜底。
触发面窄（Windows + 桌宠关 + 隐藏再显），修正机制静默失效。修：显隐路径按
「Windows 且展开态」重启轮询。测试：补 pet-disabled 重显后
`_edge_cursor_timer.isActive()` 断言。

### D-1 日历拖放落点高亮不清除：同日落点后格子永久保持「待落点」样式

`calendar_view.py:463-470` + `app_controller.py:1858-1859`｜`dropEvent` 只发
信号不复位样式（对照 `dragLeaveEvent:472-473` 有 `_apply_style()`）；控制器
同日早退不触发重建。拖到同一天 → accent 边框 + 填充的「松手就落这里」高亮
**永久残留**，用户无法判断改期是否生效。ui-ux-plan §7 阶段 6 曾 ⚠ 立项，
批次 4 只修了翻月定时器那一半（§7-1）。修：dropEvent 末尾补一行
`_apply_style()`，顺带补改期 toast。测试：补「同日 drop 后无 drop 高亮」。

### D-2 「打开数据目录」无失败收口

`settings_dialog.py:607-609`｜`ensure_data_dir()` 裸调用（mkdir 权限/磁盘
异常直抛槽内）+ `openUrl` 返回值忽略。11 个对话框里唯一未收口的落盘类按钮
（对照工作目录路径 `app_controller.py:3207-3208` 有校验+轻提示）。修：
try/except OSError → 轻提示；openUrl False 同样提示。测试：mock 负路径两例。

### D-3 卡片对话框无脏检查：Esc 直接丢弃整份清单与长备注

`card_dialog.py:670-678`｜`done()` 对非 Accepted 仅清粘贴临时文件照常关闭，
无 closeEvent 拦截、无确认；Esc 是本应用高频键，清单/长备注尚未入撤销栈、
无从恢复。ui-ux-plan §7 阶段 7 曾 ⚠ 立项，从未落地（§7-1）。修：记录初始
result_card 指纹，reject 前有差异弹确认。测试：补有改动/无改动两例。

### E-01 Markdown 行内链接 href 无协议白名单（纵深防御缺口）

`markdown_lite.py:29、50`｜`_RE_LINK` 的 URL 组只受「非空格非括号」约束，
`javascript:`/`file:` 可写入渲染结果。html.escape 防住了属性注入（引号已
转义），且**全仓无 `openExternalLinks`、无 QTextBrowser**——当前无点击面，
属纵深防御缺口：任何调用方将来一行开启即变攻击面，而 CSV 导入已有同强度的
公式注入防护，链接协议理应对齐。修：sub 回调校验前缀，仅放行 http(s)。
测试：补「非 http(s) 协议渲染为纯文本」断言。

### F-01 五套视觉皮肤名硬编码中文、绕过 tr()

`settings_dialog.py:236、241` + `config.py:914`｜`QPushButton(spec.get("name",
key))` 直出中文名，`_zh_en` 无这些词条（grep 证实）；`test_i18n` 的 AST
扫描只看 `tr()` 调用点，此路径在护栏口径之外——英文界面下五枚皮肤按钮
整排露中文，README 双语宣称失效。修：词条入库 + `tr()`（与
`skin_display` 同范式）。测试：补「UI_SKINS 每个 name 必须有词条或经显示函数」。

### F-02 打 tag 只触发发布、不触发测试，发布链无测试门禁

`.github/workflows/test.yml:5`（仅 `branches: ["**"]`）+ `release.yml:3-6`（tags
触发、无 `needs:`/测试步骤）｜直接推 tag 可发布未测代码；且 git tag 止于
v0.2.3 而 APP_VERSION 已 0.5.0——0.3.x~0.5.x 三轮从未走过发布链，脚本本身
长期未被执行验证。修：release.yml 前置测试 job（或 test.yml 补 tags 触发）。

### F-03 冒烟退出门槛不查英文截图、en 阶段无 safe 包裹，可假绿

`smoke_test.py:86-88、146-148`｜`take_board_en` 未包 `safe`，en 截图不在
missing 清单——en 链任何异常 → 12s 硬超时退出、`failures` 空、**退出码 0**。
README 宣称的 en 截图实际无把关。修：en 截图入清单、grab 包 safe。

## 3. P2（28 条，其中 E-02/E-03/E-04/C-4 经根代理亲验）

**架构 / 可维护性**

- **A-4** `board_view.py`（4986 行 / 16 类）：五条自然拆分缝已清晰——
  `_board_qss` 皮肤样式生成（212-586）、`CardWidget`（676-1660）、列头族
  （1722-2102）、工具栏按钮族（2105-2277）、`ListColumn`（2280-3218）、
  `BoardView` 壳（3321-4986）；类边界已互相摸私有（`cw._fingerprint`、
  `col._card_widgets`）。拆分是纯移动、行为零变化，131 项测试 + test_drag_extras
  可兜底。
- **A-5** 卡片信号三层纯转发：`signal_card_save_template` 一条链 6 处
  （696→2304→2527→4719→3368→控制器）；新增卡片级能力改动面 ×5~6。修：卡片
  信号直连 BoardView，列层只留真正加工的。
- **B-5** 控制器 3574 行承担约 18 类职责（生命周期/恢复、信号矩阵、建卡五入口、
  附件、CRUD、刷新管线、15 项偏好同步、macOS 菜单、撤销、跨天提醒、番茄、
  归档、四导入四导出、托盘退出）。按 seams 拆：`import_export.py`、
  `reminders.py`、`settings_bridge.py`、`dialog_coordinator.py`。拆分前先补
  「公共入口仅经信号」接线测试。
- **B-6** 控制器直伸 PetView 私有成员换肤：`_pet_view._pet_canvas.set_skin(key)`
  （2363-2366）。修：PetView 增公开 `set_skin`。
- **B-7** 导出格式化器（MD/CSV/防注入约 70 行 `@staticmethod`）留在控制器
  （3413-3480），与 models/importers.py 分层不对称。修：下沉
  models/exporters.py 获得独立单测。
- **F-08** `config.py` 1515 行 8 类职责；`UI_SKINS` 大表独占 545 行（909-1453）。
  拆 `config/skins.py`（护栏 test_ui_skins/test_contrast 动态取表，拆分零测试
  改动）、`prefs.py`、`paths.py`。
- **C-5** Esc 链对 BoardView 是无契约 duck-typing（393-397），方法改名即静默
  跳级、且同链防御风格混用；现有测试用桩、真实接口无钉。修：契约化方法名。
- **D-8** 跨模块私有样式导入：`batch_edit/batch_archive` 从 `quick_add_dialog`
  导入 `_input_dialog_style`；`card_dialog` 的 `QLabel[cap]` 规则逐字节重复。
  ui-ux-plan §7 立项的 `theme.form_dialog_style` 从未建立。修：提升为
  `theme.form_dialog_style(c)`。
- **D-9** `_ElidedLabel` 困在归档，其余四处（card_dialog 附件名/环节名、
  batch_archive 勾选行、stats 分布名）裸 QLabel 硬裁无 tooltip。ui-ux-plan §7
  立项的提升从未落地。修：提升进 controls 并四处替换。
- **D-10** 11 个对话框无公共外壳：按钮行/主题注册样板 8~10 处重复，模态性、
  最小宽各凭手感。修：抽 `dialog_button_row`/`register_theme`/延伸
  `dialog_margins`。
- **F-07** 焦点环边框 1.5px 五处 Python 侧硬编码（theme.py:94、101、414、443、
  475），`border-width` 不在 test_design_tokens 口径；粗野皮肤（描边 2.5）下
  焦点环仍是 1.5px 且无注释说明是否刻意。修：提为常量并注明口径。

**健壮性 / 一致性**

- **B-8** 删除当前看板后漏刷历史/统计对话框（740-743，对照
  `_activate_board:609-612` 四件套）。修：补 `_refresh_history/_refresh_stats`。
- **C-4** 交通灯/窗口键缺 `setAccessibleName`（全仓 46 处设置，两文件零命中），
  红绿灯命中区 22px 低于自家 24px 标准（`_HIT_PAD=5`，12+2×5=22）；
  `test_focus_a11y` 审计名单未纳入两控件——ui-ux-plan:255 承诺失约。
- **C-6** `WindowControls` 无 `reapply_texts`（board_view 只刷红绿灯
  3912-3914）：悬停中切语言，窗口键 tooltip 停旧语言；两套 tooltip 机制不一致。
- **D-4** 批量编辑/批量归档对话框漏注册主题回调（构造末只 `reapply_theme()`），
  「跟随系统」日落自动换肤时半新半旧——兄弟对话框全部已注册，D-10 重复维护的
  自然产物。
- **D-5** `text_disabled` 仍被当提示文字用（浅色约 2:1），对话框侧余 8 处
  （card_dialog「未设置」×3、calendar 非本月号与完成 chip、notes 功能提示、
  archive/today 空态行）；ui-ux-plan §7 阶段 2 点名三处未迁；且
  `test_contrast.py:244-249` 只审计 primary/secondary/muted——text_disabled
  组合零审计，正是存活原因。
- **E-02** workspace 索引落盘失败完全静默（`workspace.py:363-372` 只 log）：
  README「不静默丢写」不覆盖 workspace.json；最坏组合 = delete 后 `_save` 失败 →
  重启后索引含已删板 id → 板文件不存在 → 空板回填 flush → **已删看板以幽灵
  空板复活**（孤儿收编只处理反向）。**本报告最高优先级 P2。** 修：失败上抛/
  通知 + 启动时清理指向不存在文件的条目。
- **E-03** 索引失联重建/孤儿收编时损坏板静默出列（212-214、233-235）：板从
  切换器无痕消失，隔离副本在盘上但无任何提示。
- **E-04** 卡片标题与列表标题 QLabel 无 `setTextFormat(PlainText)` 也无转义
  （board_view.py:1030、1870；grep 证实全文件无调用）——以 `<` 开头的标题
  （速记/Trello/MD/CSV 导入直通）按富文本渲染：吞字/加粗/伪链接。备注与清单
  都有防线，唯独标题裸奔。修：两处 `setTextFormat(Qt.PlainText)`。

**护栏口径**

- **F-05** `_zh_en` 重复键「看板仍在保存…」两条不同译文，dict last-wins 静默
  覆盖（i18n.py:586 vs 898）。修：AST 断言键唯一（顺带解决 F-12 死词条方向）。
- **F-06** `UI_SPACE` 八档间距阶梯零消费：实际 padding 全在阶梯外
  （`tokens.pad(5,8)`、`UI_PAD_PRIMARY="7px 22px"`），护栏只验存在性——
  「有护栏的空转」。修：收编或删。
- **F-09** 生成 QSS 合法性护栏只审 3 个生成源，其余视图级 QSS 无
  「重复声明/插值残留/Qt 拒收」检查（该测试自己的 docstring 说明这类错误
  会让样式表整份静默失效）。修：sanity 扫全部生成源。
- **F-10** 托盘仅 2 用例：`reapply_texts`（语言切换用户可见）、`_on_activated`
  显隐切换、`show_notification` 均无护栏（此文件注释恰记录过一次英文文案
  比对事故）。
- **A-6** 高风险路径零护栏：方向键导航三入口、`refresh(build_limit)` 分帧
  不变量、列尾落点、插入线几何、`_auto_scroll_tick`、Toast 行为——grep 全
  tests 证实。优先补方向键与分帧。

**文档口径**

- **F-04** 打包产物名口径漂移：README:186 仍写「桌宠看板v{版本号}.exe」，
  实际 82a1b05 已刻意改为 `peTTrello-v{版本}`（build_app.py:222）；AGENTS.md
  称测试脚本在 `scripts/`，实际在 `tests/` 与根目录。

## 4. P3（14 条）

**性能**

- **A-7** 每次 refresh 无条件读 QSettings+JSON（`get_collapsed_lists`，
  board_view:4180），结果仅建新列时使用——进 `col is None` 分支再读即可。
- **A-8** `_lower_cache` 驱逐阈值按可见卡数计算，无过滤时退化为
  `len(cache)>0`（4171）：用过一次搜索后，每次无过滤 refresh 恒多一遍
  O(全板) alive 集构建且永不自愈。分母改总卡数即可。
- **A-9** 文件拖拽 dragMove 热路径每次对每个 URL 重做 `Path.is_file()`
  （3135-3141）：60-125Hz × 文件数，dragEnter 已验证过同一 payload。缓存判定。
- **B-9** 语言切换借道 `_after_data_change` 标脏落盘（2368-2373）：白转一次
  .prev 轮转，且是 B-2 的触发器。抽 `_refresh_views_only()`。
- **B-10** 整仓 zip 备份在 UI 线程同步打包（3366-3384）：几百 MB 附件时冻结
  数秒且无忙提示（对照 QSS 重 polish 都挂了等待光标）。
- **B-11** 附件入库 `shutil.copy2` 在 UI 线程（1105-1114、1296-1319）：大文件
  拖入卡顿。超阈值走线程池。
- **D-11** 日历在每次数据变更与每个 resize tick 全量重建 42 格
  （330-342、707-737）：几百卡+拖边框可见卡顿；today_popover 同类路径已改
  行复用。resize 加一帧节流。
- **E-17** 批量删除逐卡触发全索引重建 O(K·n)（board.py:683-691 ×
  controller 3305）：批量入口先失效索引。

**健壮性 / 数据卫生**

- **E-05** Trello 导入的卡/列 id 透传绕过 `_clean_id` 白名单且不去重
  （importers.py:151、106-107、175）：脏 id 落盘后重载时静默漂移。构造后过
  一遍 `Board.from_dict` 归一。
- **E-06** Markdown 导出标记回读：`📅` 日期只查形状不查语义、`🍅×N` 无上限
  （importers.py:410-413、435-438）；对比 CSV 路径有双重校验。对齐+夹紧。
- **E-07** 「暂时不可读」(OSError) 与损坏同走空板覆盖路径（json_io.py:83-90 +
  controller 281-282）：同步盘瞬时锁文件时拒绝恢复即覆盖原文件。unreadable
  分流为不置 dirty 不落盘。
- **E-09** 重命名的文件同步失败只 warning 且 store 不置脏（workspace.py:305-308
  + controller 670-673）：磁盘 name 无自愈通道。失败后 `mark_dirty()`。
- **E-10** 三种导入均无文件大小上限、MemoryError 不在收口列表
  （controller 753、769、785）：误选数 GB 文件全量载入。stat 预检 + 收口。

**测试缺口**

- **B-12** 核心懒加载路径（折叠态启动不建看板控件）零回归护栏：
  `tests/__init__.py:69` 共享控制器立即建满，`_board_ui_built` 守卫任何一处被
  误删测试照绿。补独立控制器折叠态全流程用例。

## 5. P4（36 条，按主题分组）

**死代码 / 死配置**

| 编号 | 位置 | 一句话 |
|---|---|---|
| A-10 | board_view.py:17 | `import zlib` 全文件零使用 |
| A-11 | board_view.py:4595-4597 | `_today_count_from` 忽略入参的历史转发残留 |
| F-11 | icons.py:288-307 | 18 个图标 7 个无调用；board_view 迁移只完成一半，docstring 与实际不符 |
| F-12 | i18n.py:520-521、636、645 | 4 条 emoji 前缀死词条（视图已改矢量图标） |
| F-13 | config.py:841-846 vs 851 | 桌宠皮肤名三份真相，`PET_SKINS[*]["name"]` 无消费者 |
| D-18 | stats_dialog.py:254-260 | `stats.retexts` 生产零调用，语言刷新双轨（销毁重建 vs retexts）并存 |
| F-15 | tokens.py:11-13、42-44 | 「阶段 7 之前恒等变换」注释已过期，getattr 兜底成死防御 |

**误导注释 / 文档矛盾**

| 编号 | 位置 | 一句话 |
|---|---|---|
| C-7 | traffic_lights.py:5 | docstring「红 = 退出应用」实为最小化到托盘（README:150-153 正确口径） |
| C-8 | pet_view.py:715-716 | 注释依赖「stop() 会发 finished」的不存在行为 |
| C-9 | pet_view.py:814-815 | `update_count` docstring 说总数实为今日聚焦数 |
| D-20 | card_dialog.py:380-384 | 注释称非法 due 改写 2000-01-01，实为清除；混淆资金哨兵 |
| F-18 | release.yml:63、84 | 注释硬编码 v0.1.0 示例版本号 |
| B-13 | app_controller.py:154、179-180 | 注解引用未导入类名，仅靠 future-annotations 侥幸成立；改 TYPE_CHECKING |
| A-13 | board_view.py:1793-1798 | 资金监视功能齐全但 README 通篇未提（v0.2.3 发布过的功能文档漂移） |

**一致性 / 小行为**

| 编号 | 位置 | 一句话 |
|---|---|---|
| B-14 | app_controller.py:2625 vs 1918 | 文本控件白名单三处不一致（两处少 QTextEdit），潜伏 ⌘V 误路由 |
| B-15 | main.py:60-64 | 数据目录报错框早于 `set_lang`，英文用户看中文报错 |
| D-12 | quick_add_dialog.py:264 | 批量添加 160px 定高只够校对 8 行（上限 100 行）；改 minHeight |
| D-13 | card_dialog.py:421-428 | `_due_toggle_btn` setFlat 却不入 `_flat_buttons`，「第三物种」按钮 |
| D-14 | card_dialog.py:473 vs batch_edit:93-97 | 优先级文案两套口径（「无/高」vs「P1 高」） |
| D-15 | card_dialog.py:1209-1216 | 空标题只有红边无文字，quick_add 注释虚标「同一套反馈」 |
| D-16 | archive_dialog.py:218-220 | 排序下拉 accessibleName 未接线，而「排序」词条 3b9ec4e 已入库 |
| D-17 | card_dialog.py:744-749 | 清单进度把未填空行计入 total，与落库口径打架 |
| D-19 | calendar_view.py:140-151、87 | `_Chip` 拖拽无拖影；chip 文案写死 96px 提前省略 |
| D-21 | card_dialog.py:431-464 | 「重复=每天 + 无截止日」静默失效（roll_repeat 首行即 return），对话框无提示 |
| E-11 | json_io.py:139-140 等 | 崩溃遗留 `*.tmp.<pid>.<uuid>` 无人清扫、删板清理不含它 |
| E-12 | json_io.py:298-299 | 快照摘要对非 list 的 cards 字段 `len()` 任意对象 |
| E-13 | importers.py:309 | CSV 重复列名后者遮蔽前者；`setdefault` 保留首列 |
| E-14 | workspace.py:219-222 | rebuild 用 saved_at 冒充 created_at |
| E-15 | backup.py:57-60 | zip 直写无 tmp+rename、无 testzip 校验 |
| E-16 | json_io.py:324-328 | restore 的校验深度与 list_snapshots 不一致（仅 dict、不查 lists） |
| F-16 | config.py:664 + tray:156-163 | 通知时长常量在 Windows 被 showMessage 忽略，口径失真 |
| F-17 | fund_export.py:19-23 | 列序切片魔法数 15 与 18 项模板隐耦合 |
| A-12 | toast.py:24-31 | Toast 固定配色游离于 test_contrast 之外（取值可接受，护栏看不见它） |
| A-14 | board_view.py:1701-1702 | 列头起拖路径的 `_header` getattr 恒 None，写歪的防御 |
| F-14 | 根目录 5 份 .spec + build/ + dist/ | 全部为本地残留（gitignore 已覆盖、未提交）；实际打包走 build_app.py 动态 spec；删本地残留防手滑用旧 spec 打旧包 |

## 6. 测试基线详情

- 命令：`QT_QPA_PLATFORM=offscreen` + `.venv` python，`-m unittest discover -s tests -t .`（与 README 相同），DSH 沙箱内后台执行，耗时 1734s。
- 结果：`Ran 757 tests ... FAILED (failures=13, errors=104, skipped=12)`。
- 逐条归类可见失败头：沙箱拒绝 `%TEMP%\dsh-*` 写入/清理 34 条（workspace 17、
  lists_templates 8、single_instance 5、workspace_backup 4、stats 2、autostart 2、
  restore_flow 1）；离屏无字体既有 flaky 2 条（`test_batch_delete_button_emits_and_clears`、
  `test_overflow_recovers_on_widening`，与 d46afb5 提交信息登记一致）。
  其余错误头在被截断输出中未逐条可见，从已见类别推断同源。
- 无 `Failed to import`：收集完整。**757 与 README「约 930 项」的差额本身
  是一处口径漂移**（README 计数过期或口径不同），建议在无沙箱终端复核一次
  并更新 README。
- 无沙箱复跑建议：开发者终端 `python -m unittest discover -s tests -t .`
  + `python smoke_test.py`，作为后续优化各阶段的验收门禁。

## 7. 元发现：计划文档与代码的口径漂移

`docs/ui-ux-plan.md` 八个阶段全部标 ✅，但其 §7「并入对应阶段」清单里有
**12 条经当前审计三方核实（git log -L + 逐提交 stat + 现行代码）从未落地**：

| 计划声称 | 实际状态 | 对应发现 |
|---|---|---|
| 阶段 6：日历拖放落点清除（⚠） | dropEvent 从未复位样式 | D-1 |
| 阶段 6：今日浮窗打开卡片键盘可达（⚠） | `_TitleLabel` 仍纯鼠标 | D-6 |
| 阶段 6：备注浮层键盘路径（⚠） | 无 keyPressEvent / 无 Esc | D-7 |
| 阶段 2：`text_disabled` 三处迁移 | 三处点名位仍在用 | D-5 |
| 阶段 7：卡片对话框脏检查（⚠） | 无任何实现 | D-3 |
| 阶段 1：`theme.form_dialog_style` 提取 | 从未建立 | D-8 |
| 阶段 1：`controls.ElidedLabel` 提升 | 困在归档未提升 | D-9 |
| 阶段 7：批量添加改 `setMinimumHeight` | 仍 setFixedHeight(160) | D-12 |
| 阶段 7：`_due_toggle_btn` 入 `_flat_buttons` | 未入 | D-13 |
| 阶段 7：优先级文案统一 | 两套口径并存 | D-14 |
| 阶段 7：空标题统一带文字说明 | card_dialog 仍只有红边 | D-15 |
| 阶段 6：`_Chip` 拖影 | 无 setPixmap/setHotSpot | D-19 |

**教训**：「计划标 ✅ ≠ 代码已修」。建议把 §7 里每一条 ⚠ 项回查一遍仓库
现状，未落地项移回待办；后续计划文档的验收行应直接引用测试名，使完成态
可被机器验证。此外 README 口径漂移 4 处：产物名（F-04）、资金监视功能缺失
（A-13）、`scripts/` 目录描述（F-04）、测试计数 757 vs 约 930（§6）。

## 8. 刻意设计确认（审计后不立项）

六路审计共确认以下为刻意设计且实现与声明一致，**不得作为问题修复**：
完成态不用删除线（d46afb5 锁死 + 回归断言）；三层拖拽各自接管按下事件；
拖放目标语言（2px 列边框 / 3px 插入线 / dropTarget / 成组拖影张数）；过滤
反馈与 `_pinned_ids`；Esc 逐级链顺序；`motion.enabled()` 全量门控（各动画
入口逐一核过无漏检）；`_WheelIgnoreMixin`；`ToggleSwitch` 44×26/右开/120ms；
`_CardCheckButton` 140ms 勾选动画（非死代码，today_popover 在用）；拖到折叠列
自动展开；列高「跟内容长、超视口内部滚动」模型；✕/红灯=最小化到托盘不退出
（托盘不可用退化路径完整）；皮肤名不翻译的产品口径仅限**桌宠皮肤**（F-01
的 UI_SKINS 是另一回事）；日历/统计语言切换销毁重建为既定策略（D-18 只针对
死代码）；归档清空保留模态确认的论证；导入一律生成新看板清撤销栈；撤销栈
体量自适应 20→10→5；原子写链路顺序（fsync 失败不 rename、.prev 轮转在
replace 前）；恢复不污染 .prev；旧数据迁移一次性；数据目录解析链与 QSettings
按数据目录隔离；单实例锁权限误报分流；0 字节文件当占位；显式空 `lists: []`
尊重用户意图；`today_stats` 口径与 README 逐字段等价；月末/闰日钳制全分支
验证；速记「尾部分数」吞词为测试明示的预期口径。

## 9. 覆盖说明

| 审计 | 范围（全文通读） | 根代理亲验条目 |
|---|---|---|
| A 看板核心 | board_view.py（4986 行 7 块）、controls.py、motion.py、toast.py | A-1、A-2、A-3 |
| B 控制器 | app_controller.py（3574 行 5 块）、main.py | B-1、B-2、B-3、B-4（+B-9 证据） |
| C 窗口桌宠 | main_window.py、pet_view.py、window_controls.py、traffic_lights.py | C-1、C-2、C-3、C-4、C-7 |
| D 对话框族 | 11 个对话框/浮窗（约 5600 行） | D-1、D-2、D-3 |
| E 数据层 | 9 个 models 文件逐行（json_io/board 全文精读） | E-01、E-02、E-03、E-04（+openExternalLinks 全仓验证） |
| F 基础设施 | config/i18n/theme/tokens/icons、services×6、platform×2、5 份 spec、build 脚本、workflows、smoke | F-01、F-02、F-03 |

根代理另自查：git 跟踪文件卫生（仓库干净，垃圾全在本地且已被 ignore）、
`.gitignore` 覆盖、`scripts/theme_preview.py` 与 `requirements.txt`（3 依赖
锁定，健康）。

## 10. 存疑待验证（不进分级，留待实机/产品确认）

1. **B-4 触发窗口**：模态对话框期间托盘撤销/macOS ⌘Z 可达性基于 Qt 惯例
   推断，修复时顺手双平台真机验证一次。
2. **C-1 存疑（审计 C）**：`set_always_on_top` 动画中调用、`startSystemResize`
   失败回退、多边角 resize 平台行为、macOS 缩放把手键盘可达——均需真机。
3. **D 存疑（审计 D）**：日历拖拽悬停翻月期间源 chip 被销毁的 OLE 平台行为
   （board_view 同场景有 shiboken 守卫，_Chip 没有对称处理）；Windows drop
   后 DragLeave 是否派发；`test_notes_popover` 鼠标巡检既有 flaky 的 CI 观察。
4. **E 存疑（审计 E）**：`Card.apply` 的 due_date 无类型校验（取决于
   result_card 恒传 str|None，视图侧未见违例）；`flush_async` 微秒级理论竞窗
   （有 seq 自愈，倾向不立项）；`_maybe_offer_empty_restore` 恢复失败即置
   ack（产品口径待定）。
5. **F 存疑（审计 F）**：`win_integrity` 在 macOS 的 `ctypes.wintypes` 可导入性
   （推断 py3 OK，需实机一次 import 验证）；QLockFile PID 复用场景；TCP 唤醒
   无对端身份校验（窗口极窄）；0.3.x~0.5.x 从未打 tag 是否仅本地自用。
6. **A 存疑（审计 A）**：COLLAPSED_HEIGHT=52 与最高密度档的正交性需离屏实测；
   wheelEvent 取整对触控板小步长事件可能「轻扫无响应」需真机。
7. **E-08（P3，暂不立项修改）**：速记「3月5个方案」式吞词与测试
   `test_month_day_tight_with_text_still_parsed` 的现行口径绑定——**先确认
   产品口径再动**，动则同步改该测试。
