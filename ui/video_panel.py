"""
视频播放区控件
嵌入 VLC 渲染窗口，提供播放/暂停、进度条、音量控制。
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from player.vlc_player import VlcPlayer
from ui.theme import TEXT_SECONDARY, icon


def _ms_to_display(ms: int) -> str:
    """毫秒格式化为 MM:SS 或 HH:MM:SS。"""
    total_sec = ms // 1000
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class VideoPanel(QWidget):
    """
    左侧视频播放面板。

    信号:
        seek_requested(int): 用户拖动进度条，请求跳转到毫秒位置
        volume_changed(int): 音量变化，供状态栏同步显示
    """

    seek_requested = pyqtSignal(int)
    volume_changed = pyqtSignal(int)

    def __init__(self, player: VlcPlayer, parent=None) -> None:
        super().__init__(parent)
        self._player = player
        self._slider_dragging = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # VLC 视频渲染区域（黑色背景）
        self.video_frame = QFrame()
        self.video_frame.setObjectName("videoFrame")
        self.video_frame.setMinimumSize(480, 270)
        layout.addWidget(self.video_frame, stretch=1)

        # 进度条 + 时间标签
        progress_row = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(130)
        progress_row.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.valueChanged.connect(self._on_slider_value_changed)
        progress_row.addWidget(self.progress_slider, stretch=1)
        layout.addLayout(progress_row)

        # 控制按钮 + 音量
        controls = QHBoxLayout()

        self.btn_play = QPushButton()
        self.btn_play.setIcon(icon("fa5s.play"))
        self.btn_play.setIconSize(QSize(18, 18))
        self.btn_play.setFixedSize(36, 32)
        self.btn_play.setToolTip("播放/暂停")
        self.btn_play.clicked.connect(self._toggle_play)
        controls.addWidget(self.btn_play)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(icon("fa5s.stop"))
        self.btn_stop.setIconSize(QSize(18, 18))
        self.btn_stop.setFixedSize(36, 32)
        self.btn_stop.setToolTip("停止")
        self.btn_stop.clicked.connect(self._stop)
        controls.addWidget(self.btn_stop)

        controls.addStretch()

        # 音量图标（随音量值切换 volume-up / volume-mute）
        self._vol_icon_label = QLabel()
        self._vol_icon_label.setPixmap(icon("fa5s.volume-up", TEXT_SECONDARY).pixmap(QSize(16, 16)))
        controls.addWidget(self._vol_icon_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls.addWidget(self.volume_slider)

        self._vol_pct_label = QLabel("80%")
        self._vol_pct_label.setFixedWidth(36)
        controls.addWidget(self._vol_pct_label)

        layout.addLayout(controls)

        # 初始音量
        self._player.set_volume(80)

    def bind_player_to_frame(self) -> None:
        """窗口显示后绑定 VLC 输出到 video_frame。"""
        self._player.bind_widget(self.video_frame)

    def _set_play_button_state(self, playing: bool) -> None:
        """统一切换播放/暂停按钮图标。"""
        if playing:
            self.btn_play.setIcon(icon("fa5s.pause"))
            self.btn_play.setToolTip("暂停")
        else:
            self.btn_play.setIcon(icon("fa5s.play"))
            self.btn_play.setToolTip("播放")

    def _toggle_play(self) -> None:
        if self._player.is_playing():
            self._player.pause()
            self._set_play_button_state(False)
        else:
            self._player.play()
            self._set_play_button_state(True)

    def _stop(self) -> None:
        self._player.stop()
        self._set_play_button_state(False)

    def _on_volume_changed(self, value: int) -> None:
        self._player.set_volume(value)
        self._vol_pct_label.setText(f"{value}%")
        # 音量为 0 时切换为静音图标
        icon_name = "fa5s.volume-mute" if value == 0 else "fa5s.volume-up"
        self._vol_icon_label.setPixmap(icon(icon_name, TEXT_SECONDARY).pixmap(QSize(16, 16)))
        # 通知状态栏更新
        self.volume_changed.emit(value)

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        self._apply_slider_seek()

    def _on_slider_value_changed(self, value: int) -> None:
        if self._slider_dragging:
            duration = self._player.get_duration_ms()
            if duration > 0:
                target_ms = int(duration * value / 1000)
                self.time_label.setText(
                    f"{_ms_to_display(target_ms)} / {_ms_to_display(duration)}"
                )

    def _apply_slider_seek(self) -> None:
        duration = self._player.get_duration_ms()
        if duration <= 0:
            return
        ratio = self.progress_slider.value() / 1000.0
        target_ms = int(duration * ratio)
        self.seek_requested.emit(target_ms)

    def update_progress_ui(self, time_ms: int, duration_ms: int) -> None:
        """由主窗口定时器调用，刷新进度条与时间标签（非拖动状态）。"""
        if self._slider_dragging:
            return

        if duration_ms > 0:
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(time_ms / duration_ms * 1000))
            self.progress_slider.blockSignals(False)

        self.time_label.setText(
            f"{_ms_to_display(time_ms)} / {_ms_to_display(duration_ms)}"
        )

        # 同步播放按钮图标
        self._set_play_button_state(self._player.is_playing())

    def reset_ui(self) -> None:
        self.progress_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")
        self._set_play_button_state(False)
