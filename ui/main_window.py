"""
主窗口模块
水平分割布局：左侧视频播放区 + 右侧字幕列表区。
整合播放器、字幕提取、同步逻辑。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from player.vlc_player import VlcPlayer, VlcPlayerError
from subtitles.models import SubtitleEntry
from sync.subtitle_sync import SubtitleSyncController
from data.models import CollectedWord
from data.wordbook_db import WordBookDB
from ui.subtitle_list import SubtitleListWidget
from ui.theme import StatusBarItem, icon
from ui.translation_panel import TranslationPanel
from ui.translation_worker import TranslationWorker
from ui.translator import normalize_query_word
from ui.video_panel import VideoPanel
from ui.wordbook_dialog import WordBookDialog
from ui.workers import SubtitleExtractWorker

logger = logging.getLogger(__name__)

# 支持的视频格式
VIDEO_EXTENSIONS = (
    "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mpeg *.mpg"
)


def _ms_to_display(ms: int) -> str:
    """毫秒格式化为 MM:SS 或 HH:MM:SS。（MainWindow 自用辅助函数）"""
    total_sec = ms // 1000
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ZPlayer - 本地电影字幕同步对照工具")
        self.resize(1280, 720)

        self._player = VlcPlayer()
        self._video_path: str | None = None
        self._extract_worker: SubtitleExtractWorker | None = None
        self._translation_panel: TranslationPanel | None = None
        self._translation_worker: TranslationWorker | None = None

        # 单词本数据库
        self._wordbook_db = WordBookDB()
        self._wordbook_dialog: WordBookDialog | None = None

        # 同步控制器：高亮变化 → 更新列表；seek 请求 → 跳转播放器
        self._sync = SubtitleSyncController(
            on_highlight_changed=self._on_highlight_changed,
            on_seek_requested=self._on_seek_from_subtitle,
        )

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._setup_sync_timer()

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = toolbar.addAction(icon("fa5s.folder-open"), "打开视频")
        open_action.triggered.connect(self._open_video_dialog)

        self._action_extract = toolbar.addAction(icon("fa5s.closed-captioning"), "提取字幕")
        self._action_extract.setEnabled(False)
        self._action_extract.triggered.connect(self._start_subtitle_extraction)

        wordbook_action = toolbar.addAction(icon("fa5s.bookmark"), "单词收藏")
        wordbook_action.triggered.connect(self._open_wordbook_dialog)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        # 左侧：视频播放区
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        title_left = QLabel("视频播放")
        title_left.setStyleSheet("font-weight: bold; font-size: 12px;")
        left_layout.addWidget(title_left)

        self._video_panel = VideoPanel(self._player)
        self._video_panel.seek_requested.connect(self._on_seek_from_slider)
        self._video_panel.volume_changed.connect(self._update_status_volume)
        left_layout.addWidget(self._video_panel)

        splitter.addWidget(left)

        # 右侧：字幕列表区 + 翻译面板
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        header = QHBoxLayout()
        title_right = QLabel("字幕列表")
        title_right.setStyleSheet("font-weight: bold; font-size: 12px;")
        header.addWidget(title_right)

        self._subtitle_info_label = QLabel("尚未加载字幕")
        self._subtitle_info_label.setObjectName("subtitleInfoLabel")
        self._subtitle_info_label.setStyleSheet("color: #9fa0ab;")
        header.addStretch()
        header.addWidget(self._subtitle_info_label)
        right_layout.addLayout(header)

        # 垂直分割器：字幕列表（上）+ 翻译面板（下）
        self._right_vsplit = QSplitter(Qt.Orientation.Vertical)
        self._right_vsplit.setHandleWidth(4)

        self._subtitle_list = SubtitleListWidget()
        self._subtitle_list.subtitle_clicked.connect(self._on_subtitle_row_clicked)
        self._subtitle_list.subtitle_clicked.connect(self._on_subtitle_row_selected)
        self._right_vsplit.addWidget(self._subtitle_list)

        self._translation_panel = TranslationPanel()
        self._translation_panel.word_clicked.connect(self._on_translation_word_clicked)
        self._translation_panel.collection_toggled.connect(self._on_collection_toggled)
        self._right_vsplit.addWidget(self._translation_panel)

        # 初始比例：字幕列表 : 翻译面板 = 2 : 1
        self._right_vsplit.setStretchFactor(0, 2)
        self._right_vsplit.setStretchFactor(1, 1)

        right_layout.addWidget(self._right_vsplit, 1)

        splitter.addWidget(right)

        # 默认左右比例 3:2
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 500])

        self.setCentralWidget(splitter)

    def _build_statusbar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # 永久组件（按从左到右顺序添加）
        self._status_playback = StatusBarItem("fa5s.play-circle", "00:00 / 00:00")
        self._status.addPermanentWidget(self._status_playback)

        self._status_subtitle = StatusBarItem("fa5s.closed-captioning", "0 条")
        self._status.addPermanentWidget(self._status_subtitle)

        self._status_collection = StatusBarItem("fa5s.bookmark", "0 个")
        self._status.addPermanentWidget(self._status_collection)

        self._status_volume = StatusBarItem("fa5s.volume-up", "80%")
        self._status.addPermanentWidget(self._status_volume)

        self._status.showMessage("就绪 — 请打开本地视频文件")

    def _update_status_playback(self, time_ms: int, duration_ms: int) -> None:
        """更新播放状态图标与时间。"""
        playing = self._player.is_playing()
        icon_name = "fa5s.pause-circle" if playing else "fa5s.play-circle"
        text = f"{_ms_to_display(time_ms)} / {_ms_to_display(duration_ms)}"
        self._status_playback.set_icon_and_text(icon_name, text)

    def _update_status_subtitle(self, count: int) -> None:
        """更新字幕计数。"""
        self._status_subtitle.set_text(f"{count} 条")

    def _update_status_collection(self) -> None:
        """更新收藏计数。"""
        count = self._wordbook_db.count()
        self._status_collection.set_text(f"{count} 个")

    def _update_status_volume(self, value: int) -> None:
        """更新状态栏音量指示。"""
        icon_name = "fa5s.volume-mute" if value == 0 else "fa5s.volume-up"
        self._status_volume.set_icon_and_text(icon_name, f"{value}%")

    def _setup_sync_timer(self) -> None:
        """
        定时器驱动播放-字幕实时同步。
        约 50ms 刷新一次，保证高亮与滚动足够流畅。
        """
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(50)
        self._sync_timer.timeout.connect(self._on_sync_tick)
        self._sync_timer.start()

    # ------------------------------------------------------------------ #
    # 视频加载
    # ------------------------------------------------------------------ #

    def _open_video_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            f"视频文件 ({VIDEO_EXTENSIONS});;所有文件 (*.*)",
        )
        if not file_path:
            return
        self._load_video(file_path)

    def _load_video(self, file_path: str) -> None:
        """加载视频并清空旧字幕，随后自动触发字幕提取。"""
        # 统一转为绝对路径，避免相对路径或混合分隔符导致 VLC 无法识别
        resolved = str(Path(file_path).resolve())

        try:
            self._player.load(resolved)
        except VlcPlayerError as exc:
            QMessageBox.critical(self, "视频加载失败", str(exc))
            self._status.showMessage(f"视频加载失败: {exc}")
            return

        self._video_path = resolved
        self._video_panel.bind_player_to_frame()
        self._video_panel.reset_ui()

        # 清空旧字幕
        self._subtitle_list.clear_subtitles()
        self._sync.set_subtitles([])
        self._subtitle_info_label.setText("尚未加载字幕")
        
        # 清空翻译面板（新视频加载时完全重置）
        if self._translation_panel:
            self._translation_panel.clear()

        self.setWindowTitle(f"ZPlayer - {Path(file_path).name}")
        self._action_extract.setEnabled(True)
        self._status.showMessage(f"已加载: {file_path}")

        # 自动提取字幕
        self._start_subtitle_extraction()

    # ------------------------------------------------------------------ #
    # 字幕提取（后台线程）
    # ------------------------------------------------------------------ #

    def _start_subtitle_extraction(self) -> None:
        if not self._video_path:
            return

        if self._extract_worker and self._extract_worker.isRunning():
            self._status.showMessage("字幕提取进行中，请稍候...")
            return

        self._action_extract.setEnabled(False)
        self._status.showMessage("正在提取/识别字幕...")

        self._extract_worker = SubtitleExtractWorker(
            video_path=self._video_path,
            whisper_model="base",
            parent=self,
        )
        self._extract_worker.progress.connect(self._on_extract_progress)
        self._extract_worker.finished_ok.connect(self._on_extract_success)
        self._extract_worker.finished_error.connect(self._on_extract_error)
        self._extract_worker.finished.connect(lambda: self._action_extract.setEnabled(True))
        self._extract_worker.start()

    def _on_extract_progress(self, message: str) -> None:
        self._status.showMessage(message)

    def _on_extract_success(self, entries: list, method: str) -> None:
        typed_entries: list[SubtitleEntry] = entries
        self._sync.set_subtitles(typed_entries)
        self._subtitle_list.load_subtitles(typed_entries)
        self._subtitle_info_label.setText(f"{len(typed_entries)} 条 | {method}")
        self._status.showMessage(f"字幕就绪: {len(typed_entries)} 条 ({method})")
        self._update_status_subtitle(len(typed_entries))
        logger.info("字幕加载成功: %d 条, method=%s", len(typed_entries), method)

    def _on_extract_error(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "字幕提取失败",
            f"{message}\n\n可能原因：\n"
            "• 视频无内置字幕且 Whisper 识别失败\n"
            "• 视频无音频轨道\n"
            "• FFmpeg 未正确安装\n"
            "• 网络问题导致 Whisper 模型下载失败",
        )
        self._status.showMessage(f"字幕提取失败: {message}")

    # ------------------------------------------------------------------ #
    # 播放-字幕同步（核心功能 2）
    # ------------------------------------------------------------------ #

    def _on_sync_tick(self) -> None:
        """每帧匹配当前进度所在字幕区间，驱动高亮与滚动。"""
        time_ms = self._player.get_time_ms()
        duration_ms = self._player.get_duration_ms()

        self._video_panel.update_progress_ui(time_ms, duration_ms)
        self._update_status_playback(time_ms, duration_ms)

        if not self._sync.get_entries():
            return

        index, changed = self._sync.update_playback_time(time_ms)

        # 高亮变化且允许自动滚动时，列表跟随到中间
        if changed and index >= 0:
            self._subtitle_list.set_highlight_index(
                index,
                auto_scroll=self._sync.should_auto_scroll,
            )

        # 点击跳转后，seek 完成则解除滚动锁定
        if not self._sync.should_auto_scroll:
            # 若播放位置已接近目标字幕起点，解除锁定
            entry = self._sync.get_entry(self._sync.current_index)
            if entry and abs(time_ms - entry.start_ms) < 500:
                self._sync.clear_user_click_lock()

    def _on_highlight_changed(self, index: int) -> None:
        """同步控制器回调：更新列表高亮（不强制滚动，由 _on_sync_tick 决定）。"""
        if index >= 0:
            self._subtitle_list.set_highlight_index(
                index,
                auto_scroll=self._sync.should_auto_scroll,
            )
        else:
            # 间隙时段取消高亮
            self._subtitle_list.set_highlight_index(-1, auto_scroll=False)

    # ------------------------------------------------------------------ #
    # 点击字幕跳转（核心功能 3）
    # ------------------------------------------------------------------ #

    def _on_subtitle_row_clicked(self, index: int) -> None:
        """
        用户点击右侧字幕行 → seek 到 start_ms。
        """
        start_ms = self._sync.on_subtitle_clicked(index)
        if start_ms is not None:
            self._player.set_time_ms(start_ms)
            # 若当前未播放，自动开始播放以便对照
            if not self._player.is_playing():
                self._player.play()
            self._status.showMessage(
                f"已跳转到字幕 #{index + 1} ({start_ms} ms)"
            )

    def _on_seek_from_subtitle(self, time_ms: int) -> None:
        """同步控制器内部 seek 回调（与点击逻辑配合）。"""
        self._player.set_time_ms(time_ms)

    def _on_seek_from_slider(self, time_ms: int) -> None:
        """进度条拖动 seek。"""
        self._player.set_time_ms(time_ms)

    # ------------------------------------------------------------------ #
    # 单词翻译（双击字幕 → 弹窗 → 点击单词 → 有道词典查询）
    # ------------------------------------------------------------------ #

    def _on_subtitle_row_selected(self, index: int) -> None:
        """单击或双击字幕行 → 在翻译面板中显示该行字幕原文。"""
        entries = self._sync.get_entries()
        if entries and 0 <= index < len(entries):
            entry = entries[index]
            if self._translation_panel:
                self._translation_panel.show_subtitle(entry.text)
                # 传递字幕上下文，供收藏时关联句子和视频来源
                video_name = (
                    Path(self._video_path).name if self._video_path else None
                )
                self._translation_panel.set_subtitle_context(
                    text=entry.text,
                    start_ms=entry.start_ms,
                    end_ms=entry.end_ms,
                    video_name=video_name,
                )

    def _on_translation_word_clicked(self, word: str) -> None:
        """用户在翻译面板中点击单词 → 启动后台翻译 Worker。"""
        query_word = normalize_query_word(word)
        if not query_word:
            return

        # 终止上一个 Worker
        if self._translation_worker and self._translation_worker.isRunning():
            self._translation_worker.quit()
            self._translation_worker.wait(3000)

        # 显示加载状态
        if self._translation_panel:
            self._translation_panel.show_loading(query_word)

        # 创建并启动 Worker
        self._translation_worker = TranslationWorker(query_word, parent=self)
        self._translation_worker.finished_ok.connect(self._on_translation_success_panel)
        self._translation_worker.finished_error.connect(self._on_translation_error)
        self._translation_worker.start()

    def _on_translation_success_panel(self, data: dict) -> None:
        """翻译完成 → 翻译面板显示结果。"""
        if self._translation_panel:
            from ui.translator import TranslationResult
            result = TranslationResult.from_dict(data)
            self._translation_panel.show_translation(result)
            # 查询并设置收藏状态
            is_collected = self._wordbook_db.is_collected(result.word)
            self._translation_panel.set_collection_state(is_collected)

    def _on_translation_error(self, message: str) -> None:
        """翻译失败 → 翻译面板显示错误。"""
        if self._translation_panel:
            self._translation_panel.show_error(message)
        self._status.showMessage(f"翻译失败: {message}")

    # ------------------------------------------------------------------ #
    # 单词收藏
    # ------------------------------------------------------------------ #

    def _on_collection_toggled(self, data: object) -> None:
        """处理收藏/取消收藏操作。"""
        if isinstance(data, CollectedWord):
            # 收藏操作
            success = self._wordbook_db.add(data)
            if success and self._translation_panel:
                self._translation_panel.set_collection_state(True)
                self._status.showMessage(f"已收藏单词: {data.word}", 3000)
        elif isinstance(data, str):
            # 取消收藏操作
            success = self._wordbook_db.remove(data)
            if success and self._translation_panel:
                self._translation_panel.set_collection_state(False)
                self._status.showMessage(f"已取消收藏: {data}", 3000)
        # 更新状态栏收藏计数
        self._update_status_collection()

    def _open_wordbook_dialog(self) -> None:
        """打开单词本对话框（非模态）。"""
        if self._wordbook_dialog is None:
            self._wordbook_dialog = WordBookDialog(self._wordbook_db, parent=self)
            # 对话框关闭后重置引用，下次打开时重建以保证数据新鲜
            self._wordbook_dialog.finished.connect(
                lambda: setattr(self, "_wordbook_dialog", None)
            )
        self._wordbook_dialog.refresh()
        self._wordbook_dialog.show()
        self._wordbook_dialog.raise_()
        self._wordbook_dialog.activateWindow()

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 确保窗口句柄有效后再绑定 VLC
        self._video_panel.bind_player_to_frame()

    def closeEvent(self, event) -> None:
        self._sync_timer.stop()
        if self._extract_worker and self._extract_worker.isRunning():
            self._extract_worker.quit()
            self._extract_worker.wait(3000)
        if self._translation_worker and self._translation_worker.isRunning():
            self._translation_worker.quit()
            self._translation_worker.wait(3000)
        self._wordbook_db.close()
        self._player.release()
        super().closeEvent(event)
