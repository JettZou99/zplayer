"""
VLC 播放器模块
封装 python-vlc，提供播放控制、进度查询（毫秒）与 seek 跳转。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from player.vlc_setup import configure_vlc

try:
    configure_vlc()
    import vlc
except RuntimeError as exc:
    raise RuntimeError(str(exc)) from exc

logger = logging.getLogger(__name__)


class VlcPlayerError(Exception):
    """播放器相关异常。"""


class VlcPlayer:
    """libVLC 播放器封装，供 PyQt6 视频控件嵌入使用。"""

    def __init__(self) -> None:
        instance_args = [
            "--no-video-title-show",
            "--quiet",
            "--intf=dummy",
        ]

        # VLC_PLUGIN_PATH 已在 vlc_setup.configure_vlc() 中显式设置，
        # 无需再通过实例参数传递（--plugin-path 在 VLC 3.0 中已废弃）

        self._instance = vlc.Instance(*instance_args)
        if self._instance is None:
            raise VlcPlayerError(
                "VLC 实例初始化失败，请确认已正确安装 64 位 VLC 并重装 python-vlc"
            )

        self._player = self._instance.media_player_new()
        if self._player is None:
            raise VlcPlayerError("VLC 播放器对象创建失败")

        self._media: Optional[vlc.Media] = None
        self._duration_ms: int = 0

    # ------------------------------------------------------------------ #
    # 媒体加载
    # ------------------------------------------------------------------ #

    def load(self, file_path: str) -> None:
        """
        加载本地视频文件。

        Windows 下依次尝试：原生路径 → file:// URI，兼容中文路径、空格及特殊字符。

        Raises:
            VlcPlayerError: 文件无法打开或解析
        """
        path = Path(file_path).expanduser()
        if not path.is_file():
            # 兼容 file:// URI 形式传入
            if file_path.startswith("file:"):
                parsed = urlparse(file_path)
                path = Path(unquote(parsed.path))
                if sys.platform == "win32" and parsed.path.startswith("/") and len(parsed.path) > 2:
                    path = Path(parsed.path[1:])  # /D:/... → D:/...
            if not path.is_file():
                raise VlcPlayerError(f"视频文件不存在或无法访问: {file_path}")

        path = path.resolve()
        media, create_errors = self._create_media(path)
        if media is None:
            error_detail = "\n".join(f"  • {m}: {e}" for m, e in create_errors)
            raise VlcPlayerError(
                f"无法创建媒体对象: {path.name}\n"
                f"完整路径: {path}\n"
                f"各方式尝试结果:\n{error_detail}\n"
                "可能原因: VLC 插件目录未正确加载、文件损坏、"
                "或路径含特殊字符"
            )

        # 释放上一份 media，避免重复加载时资源泄漏
        if self._media is not None:
            self._media.release()

        try:
            media.parse_with_options(vlc.MediaParseFlag.local, timeout=30_000)
        except Exception as exc:
            logger.warning("媒体预解析失败（不影响播放）: %s", exc)

        self._player.set_media(media)
        self._media = media

        duration = media.get_duration()
        if duration and duration > 0:
            self._duration_ms = duration
        else:
            self._duration_ms = 0

        logger.info("已加载视频: %s, 时长=%d ms", path, self._duration_ms)

    def _create_media(self, path: Path) -> tuple[Optional[vlc.Media], list[tuple[str, str]]]:
        """
        多种路径格式尝试创建 Media 对象。

        libVLC 文档要求路径为 UTF-8；Windows 中文路径用 file:// URI 最稳妥。

        Returns:
            (Media 对象或 None, 各尝试方式的错误描述列表)
        """
        attempts: list[tuple[str, str]] = [
            ("media_new_path(原生路径)", self._normalize_native_path(path)),
            ("media_new_location(file URI)", path.as_uri()),
        ]

        errors: list[tuple[str, str]] = []

        for method, candidate in attempts:
            try:
                if method.startswith("media_new_location"):
                    media = self._instance.media_new_location(candidate)
                else:
                    media = self._instance.media_new_path(candidate)
            except Exception as exc:
                msg = f"异常 {type(exc).__name__}: {exc}"
                logger.warning("media_new 失败 (%s): %s -> %s", method, candidate, msg)
                errors.append((method, msg))
                continue

            if media is not None:
                logger.info("媒体创建成功，方式=%s, path=%s", method, candidate)
                return media, errors

            errors.append((method, "返回 None（VLC 无法解析此路径格式）"))
            logger.warning("media_new 返回 None (%s): %s", method, candidate)

        # 最后兜底：media_new 自动判断 URL / 本地路径
        try:
            uri = path.as_uri()
            media = self._instance.media_new(uri)
            if media is not None:
                logger.info("媒体创建成功（兜底 media_new）, path=%s", uri)
                return media, errors
            errors.append(("media_new(file URI)", "返回 None"))
        except Exception as exc:
            errors.append(("media_new(file URI)", f"异常 {type(exc).__name__}: {exc}"))

        return None, errors

    @staticmethod
    def _normalize_native_path(path: Path) -> str:
        """
        转为 VLC 可用的本地绝对路径字符串。

        超长路径（>260 字符）在 Windows 下加 \\\\?\\ 前缀。
        """
        resolved = str(path.resolve())
        if sys.platform == "win32" and len(resolved) > 260 and not resolved.startswith("\\\\?\\"):
            return "\\\\?\\" + resolved
        return resolved

    def bind_widget(self, widget) -> None:
        """
        将 VLC 视频输出绑定到 PyQt6 控件窗口句柄。

        Windows 使用 set_hwnd，Linux 使用 set_xwindow，macOS 使用 set_nsobject。
        """
        win_id = int(widget.winId())
        if win_id == 0:
            logger.warning("控件 winId 为 0，视频可能无法渲染，请确保窗口已显示")

        if sys.platform.startswith("linux"):
            self._player.set_xwindow(win_id)
        elif sys.platform == "win32":
            self._player.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self._player.set_nsobject(win_id)
        else:
            logger.warning("未知平台 %s，尝试使用 set_hwnd", sys.platform)
            self._player.set_hwnd(win_id)

    # ------------------------------------------------------------------ #
    # 播放控制
    # ------------------------------------------------------------------ #

    def play(self) -> None:
        """开始或继续播放。"""
        self._player.play()

    def pause(self) -> None:
        """暂停播放。"""
        self._player.pause()

    def toggle_pause(self) -> None:
        """切换播放/暂停。"""
        self._player.pause()

    def stop(self) -> None:
        """停止播放。"""
        self._player.stop()

    def is_playing(self) -> bool:
        """当前是否处于播放状态。"""
        return bool(self._player.is_playing())

    def set_volume(self, volume: int) -> None:
        """设置音量 0-100。"""
        self._player.audio_set_volume(max(0, min(100, volume)))

    def get_volume(self) -> int:
        """获取当前音量。"""
        vol = self._player.audio_get_volume()
        return vol if vol >= 0 else 0

    # ------------------------------------------------------------------ #
    # 进度（毫秒精度，供字幕同步使用）
    # ------------------------------------------------------------------ #

    def get_time_ms(self) -> int:
        """
        获取当前播放位置（毫秒）。

        VLC 返回 -1 表示尚不可用（媒体未就绪），此时返回 0。
        """
        t = self._player.get_time()
        return max(0, t) if t >= 0 else 0

    def get_duration_ms(self) -> int:
        """获取媒体总时长（毫秒）。"""
        d = self._player.get_length()
        if d and d > 0:
            self._duration_ms = d
            return d
        return self._duration_ms

    def set_time_ms(self, time_ms: int) -> None:
        """
        Seek 到指定毫秒位置。

        供「点击字幕跳转视频」功能调用。
        """
        self._player.set_time(max(0, int(time_ms)))

    def set_position(self, ratio: float) -> None:
        """按 0.0~1.0 比例设置播放位置（进度条拖动）。"""
        self._player.set_position(max(0.0, min(1.0, ratio)))

    def get_position(self) -> float:
        """获取当前播放比例 0.0~1.0。"""
        pos = self._player.get_position()
        return pos if 0.0 <= pos <= 1.0 else 0.0

    def release(self) -> None:
        """释放播放器资源。"""
        self.stop()
        if self._media is not None:
            self._media.release()
            self._media = None
        self._player.release()
        self._instance.release()
