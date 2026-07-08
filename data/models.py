"""收藏单词数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.translator import TranslationResult


def _format_timestamp(ms: int) -> str:
    """将毫秒格式化为 SRT 时间轴格式 HH:MM:SS,mmm。"""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


@dataclass
class CollectedWord:
    """收藏的单词数据模型，关联字幕句子和视频来源。"""

    word: str
    definitions: list[tuple[str, str]] = field(default_factory=list)
    us_phonetic: str | None = None
    uk_phonetic: str | None = None
    subtitle_text: str | None = None
    subtitle_start_ms: int | None = None
    subtitle_end_ms: int | None = None
    video_name: str | None = None
    collected_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    id: int | None = None

    @property
    def subtitle_time_range(self) -> str | None:
        """格式化为 'HH:MM:SS,mmm --> HH:MM:SS,mmm'。"""
        if self.subtitle_start_ms is None or self.subtitle_end_ms is None:
            return None
        return (
            f"{_format_timestamp(self.subtitle_start_ms)} --> "
            f"{_format_timestamp(self.subtitle_end_ms)}"
        )

    @property
    def definitions_text(self) -> str:
        """将释义列表合并为单字符串，如 'vt. 认出；n. 识别'。"""
        parts: list[str] = []
        for pos, meaning in self.definitions:
            if pos:
                parts.append(f"{pos} {meaning}")
            else:
                parts.append(meaning)
        return "；".join(parts)

    @classmethod
    def from_translation(
        cls,
        result: TranslationResult,
        subtitle_text: str | None = None,
        subtitle_start_ms: int | None = None,
        subtitle_end_ms: int | None = None,
        video_name: str | None = None,
    ) -> CollectedWord:
        """从 TranslationResult 和字幕上下文创建实例。"""
        return cls(
            word=result.word,
            definitions=list(result.definitions),
            us_phonetic=result.us_phonetic,
            uk_phonetic=result.uk_phonetic,
            subtitle_text=subtitle_text,
            subtitle_start_ms=subtitle_start_ms,
            subtitle_end_ms=subtitle_end_ms,
            video_name=video_name,
        )

    @classmethod
    def from_db_row(cls, row: dict) -> CollectedWord:
        """从数据库行字典恢复实例（definitions 需从 JSON 反序列化）。"""
        defs_raw = row.get("definitions", "[]")
        if isinstance(defs_raw, str):
            defs = [tuple(item) for item in json.loads(defs_raw)]
        else:
            defs = [tuple(item) for item in defs_raw]
        return cls(
            id=row.get("id"),
            word=row.get("word", ""),
            definitions=defs,
            us_phonetic=row.get("us_phonetic"),
            uk_phonetic=row.get("uk_phonetic"),
            subtitle_text=row.get("subtitle_text"),
            subtitle_start_ms=row.get("subtitle_start_ms"),
            subtitle_end_ms=row.get("subtitle_end_ms"),
            video_name=row.get("video_name"),
            collected_at=row.get("collected_at", ""),
        )

    def to_db_dict(self) -> dict:
        """转为数据库可写入的字典（definitions 序列化为 JSON 字符串）。"""
        return {
            "word": self.word,
            "us_phonetic": self.us_phonetic,
            "uk_phonetic": self.uk_phonetic,
            "definitions": json.dumps(
                [list(d) for d in self.definitions], ensure_ascii=False
            ),
            "subtitle_text": self.subtitle_text,
            "subtitle_start_ms": self.subtitle_start_ms,
            "subtitle_end_ms": self.subtitle_end_ms,
            "video_name": self.video_name,
            "collected_at": self.collected_at,
        }
