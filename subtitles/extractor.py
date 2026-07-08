"""
字幕提取模块
- MKV/MP4 等容器内置软字幕：FFmpeg 直接提取为 SRT
- 无内置字幕轨道：Whisper 离线识别音频生成 SRT
- 使用 pysrt 解析为结构化 SubtitleEntry 数组
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional

import ffmpeg
import pysrt

from subtitles.models import SubtitleEntry

logger = logging.getLogger(__name__)


class SubtitleExtractionError(Exception):
    """字幕提取过程中的业务异常。"""


class SubtitleExtractor:
    """视频字幕提取与解析器。"""

    def __init__(
        self,
        whisper_model: str = "base",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Args:
            whisper_model: Whisper 模型名称（tiny/base/small/medium/large）
            progress_callback: 进度/状态文本回调，供 UI 显示
        """
        self.whisper_model = whisper_model
        self._progress = progress_callback or (lambda msg: None)

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #

    def extract_and_parse(self, video_path: str | Path) -> tuple[List[SubtitleEntry], str]:
        """
        从视频提取字幕并解析为结构化数组。

        Returns:
            (字幕条目列表, 提取方式描述)

        Raises:
            SubtitleExtractionError: 提取或解析失败
        """
        video_path = Path(video_path).resolve()
        if not video_path.is_file():
            raise SubtitleExtractionError(f"视频文件不存在: {video_path}")

        self._ensure_ffmpeg_available()

        subtitle_streams = self._probe_subtitle_streams(video_path)

        if subtitle_streams:
            # 软字幕路径：优先提取第一条字幕轨道
            stream_index = subtitle_streams[0]["index"]
            codec = subtitle_streams[0].get("codec_name", "unknown")
            self._progress(
                f"检测到 {len(subtitle_streams)} 条内置字幕轨道，"
                f"正在提取轨道 #{stream_index} ({codec})..."
            )
            srt_path = self._extract_embedded_subtitle(video_path, stream_index)
            method = f"FFmpeg 提取内置软字幕 (stream #{stream_index}, {codec})"
        else:
            # 硬字幕/无字幕轨道：Whisper 离线 ASR
            self._progress("未检测到内置字幕轨道，正在使用 Whisper 识别音频...")
            srt_path = self._transcribe_with_whisper(video_path)
            method = f"Whisper 离线识别 ({self.whisper_model})"

        entries = self._parse_srt_file(srt_path)
        if not entries:
            raise SubtitleExtractionError("字幕解析结果为空，可能视频无有效音频或识别失败")

        self._progress(f"字幕加载完成，共 {len(entries)} 条")
        return entries, method

    # ------------------------------------------------------------------ #
    # FFmpeg 软字幕探测与提取
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ensure_ffmpeg_available() -> None:
        """确认系统 PATH 中可用 ffmpeg 与 ffprobe。"""
        for tool in ("ffmpeg", "ffprobe"):
            if shutil.which(tool) is None:
                raise SubtitleExtractionError(
                    f"未找到 {tool}，请安装 FFmpeg 并加入系统 PATH。"
                    "详见 README 中的环境配置说明。"
                )

    def _probe_subtitle_streams(self, video_path: Path) -> list[dict]:
        """
        使用 ffprobe 探测视频中的字幕流。

        软字幕通常以 subtitle 类型流存在于 MKV/MP4 等容器中；
        硬字幕（烧录在画面里）不会有独立字幕轨道，此时返回空列表。
        """
        try:
            probe = ffmpeg.probe(str(video_path))
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            raise SubtitleExtractionError(f"ffprobe 探测视频失败: {stderr}") from exc

        streams = probe.get("streams", [])
        subtitle_streams = [
            stream for stream in streams if stream.get("codec_type") == "subtitle"
        ]
        logger.info("视频 %s 字幕流数量: %d", video_path.name, len(subtitle_streams))
        return subtitle_streams

    def _extract_embedded_subtitle(self, video_path: Path, stream_index: int) -> Path:
        """
        调用 FFmpeg 将指定字幕轨道导出为标准 SRT 文件。

        使用 -map 0:{stream_index} 精确映射字幕流，-c:s srt 强制 SRT 编码。
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="zplayer_sub_"))
        output_path = temp_dir / f"{video_path.stem}.srt"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-map",
            f"0:{stream_index}",
            "-c:s",
            "srt",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise SubtitleExtractionError(f"启动 FFmpeg 失败: {exc}") from exc

        if result.returncode != 0 or not output_path.is_file():
            stderr = (result.stderr or "").strip()
            raise SubtitleExtractionError(
                f"FFmpeg 字幕提取失败 (exit {result.returncode}): {stderr or '未知错误'}"
            )

        return output_path

    # ------------------------------------------------------------------ #
    # Whisper 离线识别（无内置字幕时的兜底方案）
    # ------------------------------------------------------------------ #

    def _transcribe_with_whisper(self, video_path: Path) -> Path:
        """
        使用 OpenAI Whisper 对视频音频进行离线语音识别，生成带毫秒时间戳的 SRT。

        Whisper 会自动从视频中解码音频轨道；若无音频则抛出异常。
        """
        try:
            import whisper
        except ImportError as exc:
            raise SubtitleExtractionError(
                "未安装 openai-whisper，请执行: pip install openai-whisper"
            ) from exc

        self._progress(f"正在加载 Whisper 模型 '{self.whisper_model}'（首次运行需下载）...")

        try:
            model = whisper.load_model(self.whisper_model)
        except Exception as exc:
            raise SubtitleExtractionError(f"Whisper 模型加载失败: {exc}") from exc

        self._progress("Whisper 正在转写音频，耗时取决于视频长度与模型大小...")

        try:
            result = model.transcribe(
                str(video_path),
                verbose=False,
                task="transcribe",
            )
        except RuntimeError as exc:
            # 常见原因：视频无音频轨道、文件损坏
            raise SubtitleExtractionError(f"Whisper 转写失败（可能无音频）: {exc}") from exc
        except Exception as exc:
            raise SubtitleExtractionError(f"Whisper 转写异常: {exc}") from exc

        segments = result.get("segments") or []
        if not segments:
            raise SubtitleExtractionError("Whisper 未识别到任何语音片段，视频可能无音频或静音")

        temp_dir = Path(tempfile.mkdtemp(prefix="zplayer_whisper_"))
        output_path = temp_dir / f"{video_path.stem}.srt"
        self._write_whisper_segments_to_srt(segments, output_path)
        return output_path

    @staticmethod
    def _write_whisper_segments_to_srt(segments: list[dict], output_path: Path) -> None:
        """将 Whisper segments 写入标准 SRT 格式文件。"""

        def _sec_to_srt(seconds: float) -> str:
            total_ms = int(round(seconds * 1000))
            hours = total_ms // 3_600_000
            total_ms %= 3_600_000
            minutes = total_ms // 60_000
            total_ms %= 60_000
            secs = total_ms // 1_000
            millis = total_ms % 1_000
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            start = _sec_to_srt(float(seg.get("start", 0)))
            end = _sec_to_srt(float(seg.get("end", 0)))
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        if not lines:
            raise SubtitleExtractionError("Whisper 识别结果为空")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # pysrt 解析
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_srt_file(srt_path: Path) -> List[SubtitleEntry]:
        """使用 pysrt 解析 SRT 文件为 SubtitleEntry 列表。"""
        if not srt_path.is_file():
            raise SubtitleExtractionError(f"SRT 文件不存在: {srt_path}")

        try:
            subs = pysrt.open(str(srt_path), encoding="utf-8")
        except UnicodeDecodeError:
            subs = pysrt.open(str(srt_path), encoding="utf-8-sig")
        except Exception as exc:
            raise SubtitleExtractionError(f"pysrt 解析 SRT 失败: {exc}") from exc

        entries: List[SubtitleEntry] = []
        for idx, sub in enumerate(subs):
            start_ms = (
                sub.start.hours * 3_600_000
                + sub.start.minutes * 60_000
                + sub.start.seconds * 1_000
                + sub.start.milliseconds
            )
            end_ms = (
                sub.end.hours * 3_600_000
                + sub.end.minutes * 60_000
                + sub.end.seconds * 1_000
                + sub.end.milliseconds
            )
            text = sub.text.replace("\n", " ").strip()
            entries.append(
                SubtitleEntry(
                    index=idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                )
            )

        return entries
