"""
字幕提取后台线程
避免 FFmpeg / Whisper 阻塞 UI 主线程。
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from subtitles.extractor import SubtitleExtractionError, SubtitleExtractor
from subtitles.models import SubtitleEntry


class SubtitleExtractWorker(QThread):
    """在后台执行字幕提取的 QThread。"""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(list, str)  # entries, method_description
    finished_error = pyqtSignal(str)

    def __init__(self, video_path: str, whisper_model: str = "base", parent=None) -> None:
        super().__init__(parent)
        self._video_path = video_path
        self._whisper_model = whisper_model

    def run(self) -> None:
        extractor = SubtitleExtractor(
            whisper_model=self._whisper_model,
            progress_callback=lambda msg: self.progress.emit(msg),
        )
        try:
            entries, method = extractor.extract_and_parse(Path(self._video_path))
            # frozen dataclass 需转为普通对象列表传递（Qt 信号兼容性）
            payload: List[SubtitleEntry] = list(entries)
            self.finished_ok.emit(payload, method)
        except SubtitleExtractionError as exc:
            self.finished_error.emit(str(exc))
        except Exception as exc:
            self.finished_error.emit(f"未知错误: {exc}")
