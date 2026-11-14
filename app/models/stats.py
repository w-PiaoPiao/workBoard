"""看板统计聚合：概览 / 完成趋势 / 标签·列表·优先级分布 / 番茄 Top（纯函数）

数据源只用 Card 既有字段（done_at/pomodoros/labels/priority/archived），
不读盘不改盘；不依赖 Qt，可独立单测。展示层在 views/stats_dialog.py。

口径约定：
- 完成趋势与周对比按 done_at 的**本地日期**计数、含归档卡（与
  Board.today_stats 的 done_today / weekly_done_count 同口径）
- 标签/列表/优先级分布与番茄统计只算未归档卡（归档是沉淀池，
  混进来会让"现在的看板长什么样"失真）
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models.board import Board


def compute_stats(board: Board, today: date, days: int = 30) -> dict:
    """聚合统计摘要（展示层一次取齐，避免每个视图各自扫板）

    days 为完成趋势的天数窗口（含今天，向前回溯）。所有计数都基于
    单趟遍历；trend 以 ISO 日期字符串为键，便于展示层直接对轴。
    """
    overview = board.today_stats(today)
    start = today - timedelta(days=days - 1)
    trend: dict[str, int] = {
        (start + timedelta(days=i)).isoformat(): 0 for i in range(days)}

    label_counts: dict[str, int] = {}
    list_counts: list[tuple[str, int, int]] = []   # (列名, 未归档数, 总数)
    priority_counts: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
    pomo_total = 0
    pomo_top: list[tuple[str, int]] = []

    for lst in board.lists:
        active = 0
        for c in lst.cards:
            if c.done and c.done_at:
                try:
                    d = datetime.fromisoformat(c.done_at).date()
                except ValueError:
                    d = None
                if d is not None and d.isoformat() in trend:
                    trend[d.isoformat()] += 1
            if c.archived:
                continue
            active += 1
            for key in c.labels:
                label_counts[key] = label_counts.get(key, 0) + 1
            priority_counts[c.priority] = \
                priority_counts.get(c.priority, 0) + 1
            if c.pomodoros:
                pomo_total += c.pomodoros
                pomo_top.append((c.title, c.pomodoros))
        list_counts.append((lst.title, active, len(lst.cards)))

    # 本周 / 上周完成对比（周一起算；30 天窗口足够覆盖两周）
    week_start = today - timedelta(days=today.weekday())
    this_week = last_week = 0
    for iso, n in trend.items():
        d = date.fromisoformat(iso)
        if d >= week_start:
            this_week += n
        elif d >= week_start - timedelta(days=7):
            last_week += n

    pomo_top.sort(key=lambda pair: pair[1], reverse=True)
    labels_sorted = sorted(label_counts.items(),
                           key=lambda pair: pair[1], reverse=True)
    return {
        "overview": overview,
        "trend": [(date.fromisoformat(iso), n) for iso, n in trend.items()],
        "label_counts": labels_sorted,
        "list_counts": list_counts,
        "priority_counts": priority_counts,
        "pomo_total": pomo_total,
        "pomo_top": pomo_top[:3],
        "done_this_week": this_week,
        "done_last_week": last_week,
    }
