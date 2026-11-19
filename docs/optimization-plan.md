# 桌宠看板 · 优化计划（2026-11）

> 输入：`docs/code-review-2026-11.md`（95 条发现，P0×1 / P1×16 / P2×28 /
> P3×14 / P4×36）。
> 节奏：沿用仓库「阶段 N」小步提交文化——每条（或每组同主题条目）独立提交，
> 提交信息中文、写明对应发现编号；**测试先行**：先让新护栏红、再修绿。
> 门禁（每阶段收尾必过）：`python -m unittest discover -s tests -t .`（无沙箱
> 终端）+ `python smoke_test.py` 五图 + 四道设计护栏
> （test_contrast / test_design_tokens / test_focus_a11y / test_i18n）。
> 本文档是路线图：落地时按条目自带验收标准执行，可在任一阶段暂停/裁剪。

## 0. 阶段总览

| 阶段 | 主题 | 条目 | 预计提交 | 依赖 |
|---|---|---|---|---|
| 1 | 正确性收口（P0 + 全部 P1） | 17 | 17 | 无 |
| 2 | 护栏补强（纯测试新增） | 9 | 2~3 | 与 1 并行 |
| 3 | 健壮性与一致性收口 | 17 | 8~10 | 1 |
| 4 | 架构拆分（行为零变化） | 11 | 6~8 | 1、2（护栏足了才动大文件） |
| 5 | 性能 | 8 | 5~6 | 独立，可穿插 |
| 6 | 清理与文档 | 38 | 6~8 | 独立，可穿插 |

> 「修复 + 护栏」合并型条目（如 D-5、E-02~E-07）只计一次，护栏随条目所在
> 阶段一并交付；阶段 2 只列纯护栏新增项。

## 1. 阶段 1 · 正确性收口（17 条，每条独立小提交，改动量以 S 为主）

| # | 发现 | 位置 | 量 | 修复方向与验收 |
|---|---|---|---|---|
| 1.1 | C-1 | `app/views/main_window.py:527-531,584-592,634` | M | hideEvent 折叠分支与动画收尾按 `_pet_home_geo` 落位并补 `_save_position`（或仅 collapsed 保存）。验收：新增「展开→拖动→hide→show 位置==home」「展开→拖动→collapse→save_window_pos 收到 home」两用例绿 |
| 1.2 | B-1 | `app/controllers/app_controller.py:3563-3571` | S | `_tray.hide()` 挪到 aboutToQuit 落盘成功后；失败路径改非模态框。验收：quit 强 flush 抛 StoreError 时通知出口被调用且发生在 hide 之前 |
| 1.3 | B-2 | `app_controller.py` 12 处 pop 站点 | S | 抽 `_cancel_pending_undo()`（pop + 置空 pending）统一 12 处。验收：「undo→拖回原位→切语言→redo 仍可用」绿 |
| 1.4 | B-3 | `app_controller.py:3408-3411` | S | 与 `_activate_imported_board`（804-808）同款回滚 `set_current(self._store_board_id)`。验收：patch 激活失败断言回滚 |
| 1.5 | B-4 | `app_controller.py:3156-3194` | S | exec 后按 id 重取板与卡，缺席走「看板已变更，操作取消」。验收：「exec 期间 replace_board」用例绿 |
| 1.6 | A-1 | `app/views/motion.py:49` | S | getattr 挪进 try（或 shiboken6.isValid 预判）。验收：「fade 完成→deleteLater→一轮事件循环不抛」 |
| 1.7 | A-2 | `board_view.py:3191,3206,3255-3256` + `calendar_view.py:468` | S | 统一 `_decode_mime` 助手四处收口。验收：单卡/整列/日历畸形 payload 各一用例 |
| 1.8 | A-3 | `board_view.py:3094` 对照 `1629-1633` | M | dragMove 校验快照 id 序一致，不一致就地重建 `_drop_mids`；同步改写 3094 误导注释。验收：「拖拽中变更目标列后落点」断言 |
| 1.9 | C-2 | `pet_view.py:758-759` | S | nudge 开头补 `_celebrating is not None` 早退。验收：「celebrate 进行中 nudge 不产生第二动画组」 |
| 1.10 | C-3 | `main_window.py:355-356` 关联 326 | S | 显隐路径按「Windows 且展开态」重启 `_edge_cursor_timer`。验收：pet-disabled 重显后 isActive() |
| 1.11 | D-1 | `calendar_view.py:463-470` | S | dropEvent 末尾补 `_apply_style()`；顺带补改期 toast。验收：「同日 drop 后无 drop 高亮」 |
| 1.12 | D-2 | `settings_dialog.py:607-609` | S | try/except OSError → 轻提示；openUrl False 同提示。验收：mock 负路径两例 |
| 1.13 | D-3 | `card_dialog.py:670-678` | M | 初始 result_card 指纹 + reject 前差异确认（≥1 字符才问，避免新建卡打扰）。验收：有改动弹确认/无改动直接关两例 |
| 1.14 | E-01 | `markdown_lite.py:29,50` | S | `_RE_LINK.sub` 改回调，仅放行 http(s)，其余剥纯文本。验收：「javascript: 渲染为纯文本」 |
| 1.15 | F-01 | `settings_dialog.py:236,241` + 5 词条 | S | 皮肤名入 `_zh_en` 走 `tr()`。验收：test_i18n 增「UI_SKINS 每个 name 有词条」断言 |
| 1.16 | F-02 | `.github/workflows/*` | S | release.yml 前置 test job（`needs: test`），或 test.yml 补 `tags: ["v*"]`。验收：推 tag 的 workflow 日志可见测试先行 |
| 1.17 | F-03 | `smoke_test.py:86-88,146-148` | S | en 截图入 missing 清单、grab 包 safe。验收：人为让 en 阶段抛错 → 退出码 1 |

提交顺序建议：先 1.1~1.5（控制器/窗口主链），再 1.6~1.11（交互面），后
1.12~1.17。B-4 落地时在 Windows/macOS 真机各验证一次触发窗口（报告 §10-1）。

## 2. 阶段 2 · 护栏补强（9 条纯测试，可与阶段 1 并行）

| # | 发现 | 内容 | 验收 |
|---|---|---|---|
| 2.1 | A-6 | 方向键导航三入口（move_card_focus / move_focus_horizontally / 无焦点聚焦首列）+ `refresh(build_limit)` 分帧不变量 + 列尾落点 + 插入线几何 | 新用例先红后绿的注入验证各一次 |
| 2.2 | B-12 | 懒加载路径护栏：独立控制器折叠态增删改/跨天/提醒断言 view 未被触碰，随后 `_ensure_board_ui` 建满且与模型一致 | 同上 |
| 2.3 | C-10 | 交通灯信号/按住拖出反悔/圆间中点归属，镜像 test_window_controls 范式 | 同上 |
| 2.4 | D-5（护栏半） | `text_disabled` × 各表面组合纳入 `test_contrast.py` 审计键（修复前先登记豁免清单，棘轮式收紧） | 现值入豁免、修后出豁免 |
| 2.5 | A-12 | Toast 固定色对纳入 test_contrast 基线 | 护栏看见即过 |
| 2.6 | F-05 | AST 断言 `_zh_en` 键唯一 + 死词条反向扫描（顺手清 F-12 的 4 条） | 重复键/死键各注入一次抓红 |
| 2.7 | F-09 | 生成 QSS 合法性 sanity 扫全部生成源（不止 3 个） | 注入 `padding: padding:` 一次抓红 |
| 2.8 | F-10 | 托盘 reapply_texts 文案断言 + `_on_activated` 显隐切换 + show_notification 路径 | 同上 |
| 2.9 | F-13 | `SKIN_NAMES` 与 `_SKIN_EN` 键集一致断言；`test_i18n.test_display_functions` 扩全键 | 删一个词条抓红 |

## 3. 阶段 3 · 健壮性与一致性收口（17 条）

数据安全优先（每项配负路径用例）：

| # | 发现 | 位置 | 量 | 方向 |
|---|---|---|---|---|
| 3.1 | **E-02** | `workspace.py:363-372` | M | `_save` 失败上抛或挂回调（与 BoardStore 同通知通道）；启动加载索引时剔除指向不存在文件的条目。验收：「delete 后 _save 失败→重启无幽灵板」 |
| 3.2 | E-03 | `workspace.py:212-235` | S | rebuild/收编收集损坏路径 → 启动提示「N 块看板文件损坏已隔离」 |
| 3.3 | E-07 | `json_io.py:83-90` + controller:281 | S | unreadable 与 corrupted 分流：前者内存空态启动不置 dirty 不落盘 |
| 3.4 | E-10 | `app_controller.py:753,769,785` | S | 导入前 stat 上限（>64MB 拒绝提示）+ except 加 MemoryError |
| 3.5 | E-05 | `importers.py:151,106-107,175` | S | 导入构造后过 `Board.from_dict` 归一（id 清洗+去重）。验收：重复 id/非法字符两用例 |
| 3.6 | E-06 | `importers.py:410-413,435-438` | S | 日期标记形状+语义双校验；pomodoros 夹紧 |
| 3.7 | E-09 | `workspace.py:305-308` + controller:670 | S | rename 文件同步失败后 `mark_dirty()` 自愈 |
| 3.8 | E-04 | `board_view.py:1030,1870` | S | 两处 `setTextFormat(Qt.PlainText)`。验收：「标题含 `<b>` 显示字面文本」 |
| 3.9 | B-8 | `app_controller.py:740-743` | S | 删当前板补 `_refresh_history/_refresh_stats` 与 `_activate_board` 对齐 |
| 3.10 | B-14 | `app_controller.py:2625` vs 1918 | S | 抽 `_TEXT_WIDGET_TYPES` 三处共用；补 QTextEdit 聚焦 paste 不建卡 |
| 3.11 | B-15 | `main.py:60-64` | S | `set_lang` 提前到首个报错框前 |
| 3.12 | C-4 | `traffic_lights.py` / `window_controls.py` | S | 补 accessibleName（随 reapply_texts 刷新）+ HIT_PAD 5→6（22→24px）+ 护栏名单纳入两控件 |
| 3.13 | C-6 | `window_controls.py` | S | 补 `reapply_texts()` 并接入 board_view 刷新 |
| 3.14 | D-4 | `batch_edit/batch_archive_dialog` | S | 各补一行 `AppTheme.register(self.reapply_theme)`；验收主题切换 QSS 变化 |
| 3.15 | D-5（取值半） | 8 处提示文字 | S | 迁 `text_muted`（board 同范式）；真禁用态保留 text_disabled |
| 3.16 | D-6 | `today_popover.py:104-117` | S | `_TitleLabel` StrongFocus + Enter/Space 发 clicked（calendar `_Chip` 同范式） |
| 3.17 | D-7 | `notes_popover.py` + 锚点徽章 | M | 徽章可聚焦 + Enter 弹固定态浮层 + Esc 关闭；或产品决定走替代路径则在速查面板注明（决策项） |

## 4. 阶段 4 · 架构拆分（11 条，行为零变化，纯移动纪律）

> 前置：阶段 1、2 完成（护栏足）。每拆一步跑全量 + 冒烟截图比对。
> 大文件是热点，**按文件串行**：4.1 → 4.3 → 4.4 依次进行，4.2/4.5~4.11 穿插。

| # | 发现 | 动作 | 量 | 拆分缝 |
|---|---|---|---|---|
| 4.1 | A-4 | board_view.py → 包内多模块 | L | `_board_qss`（212-586）→ board_qss.py；`CardWidget`（676-1660）+列头族+工具栏按钮族 → card_widget.py / list_header.py / toolbar.py；`ListColumn` → list_column.py；`BoardView` 壳留守。五步纯移动，每步一提交 |
| 4.2 | A-5 | 卡片信号直连 BoardView | M | 列层 ~31 个零加工信号删除，建卡处直连；列层只留 move/collapse/files_dropped。`test_pomo_archive_signals_forward` 等守护 |
| 4.3 | B-5 + B-7 | app_controller 按职责拆 | L | `controllers/import_export.py`（四导入四导出 + `_write_export_*` 下沉 models/exporters.py 获独立单测）、`controllers/reminders.py`（提醒/贪睡/跨天快照）、`controllers/settings_bridge.py`（15 项偏好同步）、`controllers/dialog_coordinator.py`（惰性对话框生命周期）。先补「公共入口仅经信号」接线测试 |
| 4.4 | F-08 | config.py 拆 | M | `config/skins.py`（UI_SKINS 545 行 + SKIN_LABEL_COLORS）、`config/prefs.py`（约 25 组键读写）、`config/paths.py`（数据目录解析链）。test_ui_skins/test_contrast 动态取表零改动 |
| 4.5 | B-6 | PetView 公开 `set_skin(key)` | S | 控制器改走公开 API |
| 4.6 | D-8 | `theme.form_dialog_style(c)` | S | 三对话框复用，card_dialog 仅附加 fund/error 规则 |
| 4.7 | D-9 | `controls.ElidedLabel` 提升 | S | 归档实现上提，四处替换（batch_archive 改 checkbox+ElidedLabel 行结构） |
| 4.8 | D-10 | 对话框外壳三件套 | M | `dialog_button_row` / `register_theme` / spacing 统一；D-4 类漏注册从此结构性消失 |
| 4.9 | C-5 | Esc 链契约化 | S | 显式方法名常量 + 统一访问风格；补接真实 BoardView 的冒烟 |
| 4.10 | F-07 | `FOCUS_RING_WIDTH` 常量 | S | 五处收编；粗野皮肤口径加注释说明 |
| 4.11 | A-11 | `_today_count_from` 删除 | S | 直连 `_today_focus_total()` |

## 5. 阶段 5 · 性能（8 条，基准先行）

> 文化沿用：每项修前先在代码注释里落一个实测数字（参照密度切换 665ms 的先例）。
> 基准：300 卡板 + 100 MB 附件目录（临时构造）。

| # | 发现 | 位置 | 量 | 方向 |
|---|---|---|---|---|
| 5.1 | B-9 | `app_controller.py:2368-2373` | S | 抽 `_refresh_views_only()`，语言切换不再标脏落盘（同时消灭 B-2 触发器残余面）。验收：切语言后 store 不脏、无落盘 |
| 5.2 | A-7 | `board_view.py:4180` | S | `get_collapsed_lists` 惰性化到 `col is None` 分支 |
| 5.3 | A-8 | `board_view.py:4171` | S | 驱逐阈值分母改总卡数；补「清搜索后 refresh 不进驱逐分支」调用计数 |
| 5.4 | A-9 | `board_view.py:3135-3141` | S | dragEnter 缓存 payload 判定，dragMove 复用 |
| 5.5 | B-10 | `app_controller.py:3366-3384` | S | 备份 zip：等待光标起步，挪单线程池 + 完成通知 |
| 5.6 | B-11 | `app_controller.py:1105-1114` | M | 附件 >16MB 走线程池 + 回调，失败沿用 pending 机制 |
| 5.7 | D-11 | `calendar_view.py:330-342,707-737` | M | resize 一帧节流；数据变更行高不变短路 |
| 5.8 | E-17 | `board.py:683-691` + controller:3305 | S | 批量删除先失效索引再逐列 remove |

## 6. 阶段 6 · 清理与文档（38 条，按主题分组提交）

| 组 | 条目 | 内容 |
|---|---|---|
| 6.1 死代码批 | A-10、A-11(若 4.11 未做)、F-11、F-12(若 2.6 未清)、F-13、D-18、F-15 | 死导入/死图标画法/死词条/死 name 字段/retexts 双轨收敛（二选一）/过期注释；每删一处 grep 复核 |
| 6.2 误导注释批 | C-7、C-8、C-9、D-20、F-18、B-13 | docstring 与实现对齐（交通灯语义、stop() 行为、角标语义、due 处置、CI 示例版本）+ TYPE_CHECKING 导入 |
| 6.3 一致性批 | B-14(若 3.10 未做)、D-12、D-13、D-14、D-15、D-16、D-17、D-19、D-21、F-16、F-17、E-12、E-13、E-14、E-16、A-12(若 2.5 未做)、A-14 | 各 1~5 行小修；每组一次提交，测试随行 |
| 6.4 数据卫生批 | E-11、E-15 | 启动清扫陈旧 `*.tmp.*`；zip 导出 tmp+testzip+rename |
| 6.5 文档批 | F-04、A-13、F-18(文档半)、README 测试计数 757、ui-ux-plan §7 回查 | README 四处口径对齐；§7 未落地 12 条移回待办并逐条标注「已由本计划阶段 N 修复」 |
| 6.6 本地清理 | F-14 | 删除本地 5 份旧 spec（含乱码名副本）与陈旧 build/、dist/（gitignore 已覆盖，仅磁盘清理，防手滑用旧 spec 打旧包） |
| 6.7 决策项 | E-08、F-06、D-7(若 3.17 选文档化) | 速记「3月5个方案」吞词口径先与产品确认；UI_SPACE 收编或删并同步注释；备注浮层键盘路径深修或文档化 |

## 7. 依赖、风险与不做的事

**依赖**：阶段 1 先行（正确性问题不解决，后续重构会搬着 bug 走）；阶段 2 与
1 并行（护栏越早落地，1/3 的验收越省）；阶段 4 硬依赖 1+2（动 4986 行文件前
护栏必须足）；5、6 独立可穿插，6.5 文档批建议随各阶段收尾同步小步更新。

**风险与回退**：每条一提交、可独立 revert；4.1~4.4 大拆分用「纯移动」纪律
（不改逻辑、不改签名），拆分前后 smoke 截图人工比对；B-5 拆控制器前先补
接线测试，拆分中保持 `self.c._on_*` 既有测试入口兼容（或一次性机械改名并
同步测试）。

**不做**：不换技术栈、不引第三方库（继续 QSS + 自绘）；不动数据模型与存储
格式；不动报告 §8 的刻意设计清单；不做像素级截图 diff（沿用 ui-ux-plan 的
既有结论：跨平台字体渲染会假红）；阶段 4 不与任何功能开发并行于同一文件。

**验收总结账**：全部落地后预期账面 = 95 条清零、README/计划文档口径与代码
一致、CI 发布链有测试门禁、巨型文件降到 <2000 行/模块。最终门禁：全量
测试（无沙箱终端）+ 冒烟五图 + 四道设计护栏全绿。
