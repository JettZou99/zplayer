"""
字幕数据模型模块
定义结构化字幕条目，供解析、同步与界面展示使用。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleEntry:
    """单条字幕的结构化表示。"""

    index: int          # 行索引（从 0 开始）
    start_ms: int       # 开始时间（毫秒）
    end_ms: int         # 结束时间（毫秒）
    text: str           # 字幕文本内容

    def contains_time(self, time_ms: int) -> bool:
        """判断给定播放时间是否落在此字幕的时间区间内。"""
        return self.start_ms <= time_ms <= self.end_ms

    @property
    def duration_ms(self) -> int:
        """字幕持续时长（毫秒）。"""
        return max(0, self.end_ms - self.start_ms)

    def format_time_range(self) -> str:
        """格式化为 HH:MM:SS,mmm 时间轴字符串，便于列表展示。"""
        return f"{_ms_to_srt_time(self.start_ms)} --> {_ms_to_srt_time(self.end_ms)}"


def _ms_to_srt_time(ms: int) -> str:
    """毫秒转 SRT 标准时间格式 HH:MM:SS,mmm。"""
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1_000
    millis = ms % 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
