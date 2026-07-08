"""
字幕同步逻辑模块
- 根据播放器当前毫秒时间戳匹配字幕区间
- 驱动列表高亮与自动滚动（将当前字幕居中）
- 处理点击字幕行时的 seek 跳转请求
"""

from __future__ import annotations

import bisect
from typing import Callable, List, Optional

from subtitles.models import SubtitleEntry


class SubtitleSyncController:
    """
    播放进度与字幕列表的同步控制器。

    本类不直接操作 UI，而是通过回调通知界面更新，便于与 PyQt6 解耦。
    """

    def __init__(
        self,
        on_highlight_changed: Callable[[int], None],
        on_seek_requested: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Args:
            on_highlight_changed: 当前高亮字幕索引变化时回调（-1 表示无匹配）
            on_seek_requested: 用户点击字幕请求跳转时的回调（传入 start_ms）
        """
        self._entries: List[SubtitleEntry] = []
        self._start_ms_list: List[int] = []  # 二分查找用的开始时间数组
        self._current_index: int = -1
        self._on_highlight_changed = on_highlight_changed
        self._on_seek_requested = on_seek_requested
        # 用户手动点击后短暂抑制自动滚动，避免与 seek 冲突
        self._user_click_lock: bool = False

    # ------------------------------------------------------------------ #
    # 字幕数据
    # ------------------------------------------------------------------ #

    def set_subtitles(self, entries: List[SubtitleEntry]) -> None:
        """加载字幕数组并重置同步状态。"""
        self._entries = list(entries)
        self._start_ms_list = [e.start_ms for e in self._entries]
        self._current_index = -1
        self._on_highlight_changed(-1)

    def get_entries(self) -> List[SubtitleEntry]:
        return self._entries

    def get_entry(self, index: int) -> Optional[SubtitleEntry]:
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    # ------------------------------------------------------------------ #
    # 播放进度同步（每帧/定时器调用）
    # ------------------------------------------------------------------ #

    def update_playback_time(self, time_ms: int) -> tuple[int, bool]:
        """
        根据当前播放毫秒时间戳匹配字幕并触发高亮。

        匹配策略：找到 start_ms <= time_ms <= end_ms 的字幕条目。
        若当前时间点无字幕（间隙），返回 (-1, False)。

        Returns:
            (匹配的字幕索引, 索引是否发生变化)
        """
        if not self._entries:
            return -1, False

        matched_index = self._find_subtitle_index_at(time_ms)

        changed = matched_index != self._current_index
        if changed:
            self._current_index = matched_index
            self._on_highlight_changed(matched_index)

        return matched_index, changed

    def _find_subtitle_index_at(self, time_ms: int) -> int:
        """
        查找 time_ms 所在的字幕区间索引。

        先用 bisect 定位可能条目，再向前/向后扫描相邻条目处理重叠或间隙。
        """
        if not self._entries:
            return -1

        # bisect_right: 找第一个 start_ms > time_ms 的位置，候选为 pos-1
        pos = bisect.bisect_right(self._start_ms_list, time_ms)
        candidates = range(max(0, pos - 2), min(len(self._entries), pos + 1))

        for idx in candidates:
            if self._entries[idx].contains_time(time_ms):
                return idx

        return -1

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def should_auto_scroll(self) -> bool:
        """是否允许自动滚动（用户点击后短暂锁定）。"""
        return not self._user_click_lock

    def clear_user_click_lock(self) -> None:
        self._user_click_lock = False

    # ------------------------------------------------------------------ #
    # 点击字幕跳转
    # ------------------------------------------------------------------ #

    def on_subtitle_clicked(self, index: int) -> Optional[int]:
        """
        用户点击字幕行：返回应跳转的 start_ms，并通过回调通知播放器。

        关键逻辑：点击后立即更新高亮索引，并锁定自动滚动直到 seek 完成。
        """
        entry = self.get_entry(index)
        if entry is None:
            return None

        self._current_index = index
        self._user_click_lock = True
        self._on_highlight_changed(index)

        if self._on_seek_requested:
            self._on_seek_requested(entry.start_ms)

        return entry.start_ms

    def format_list_item(self, entry: SubtitleEntry) -> str:
        """格式化字幕列表单行展示文本。"""
        return f"[{entry.index + 1:04d}] {entry.format_time_range()}\n{entry.text}"
