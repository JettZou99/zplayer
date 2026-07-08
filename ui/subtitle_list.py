"""
字幕列表控件
展示带时间轴的字幕行，支持高亮当前播放行与点击跳转。
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from subtitles.models import SubtitleEntry
from utils.platforms import get_font_css


class SubtitleListWidget(QListWidget):
    """
    右侧字幕列表区。

    信号:
        subtitle_clicked(int): 用户点击某行字幕，传递行索引
    """

    subtitle_clicked = pyqtSignal(int)

    # 暗色主题高亮常量
    _COLOR_HIGHLIGHT_BG = QColor("#3d3417")  # 深琥珀色
    _COLOR_HIGHLIGHT_FG = QColor("#ffd966")  # 金色文字
    _COLOR_NORMAL_BG = QColor("#1f2030")     # BG_SURFACE
    _COLOR_NORMAL_FG = QColor("#e4e4e7")     # TEXT_PRIMARY

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: List[SubtitleEntry] = []
        self._highlight_index: int = -1
        self._block_scroll_signal = False

        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.setSpacing(2)
        self.itemClicked.connect(self._handle_item_clicked)

        _font_css = get_font_css()
        self.setStyleSheet(
            f"""
            SubtitleListWidget {{
                font-size: 13px;
                font-family: {_font_css};
                background-color: #1f2030;
                border: 1px solid #353648;
                alternate-background-color: #232434;
            }}
            SubtitleListWidget::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #272838;
            }}
            SubtitleListWidget::item:selected {{
                background: #2a3a5c;
                color: #4a9eff;
            }}
            SubtitleListWidget::item:selected:!active {{
                background: #2a3a5c;
                color: #4a9eff;
            }}
            """
        )

    def load_subtitles(self, entries: List[SubtitleEntry]) -> None:
        """填充字幕列表。"""
        self.clear()
        self._entries = list(entries)
        self._highlight_index = -1

        for entry in self._entries:
            item = QListWidgetItem(self._format_item_text(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry.index)
            self.addItem(item)

    def set_highlight_index(self, index: int, auto_scroll: bool = True) -> None:
        """
        高亮指定字幕行。

        index=-1 表示清除所有高亮（播放间隙无匹配字幕时）。
        auto_scroll=True 时将当前行滚动到可视区域垂直中间（跟随播放滑动）。
        """
        if index == self._highlight_index and index >= 0 and not auto_scroll:
            return

        # 取消旧高亮
        if 0 <= self._highlight_index < self.count():
            self._apply_item_style(self._highlight_index, highlighted=False)

        self._highlight_index = index

        if 0 <= index < self.count():
            self._apply_item_style(index, highlighted=True)

            if auto_scroll:
                self._scroll_to_center(index)

    def _apply_item_style(self, row: int, highlighted: bool) -> None:
        item = self.item(row)
        if item is None:
            return
        if highlighted:
            item.setBackground(self._COLOR_HIGHLIGHT_BG)
            item.setForeground(self._COLOR_HIGHLIGHT_FG)
        else:
            item.setBackground(self._COLOR_NORMAL_BG)
            item.setForeground(self._COLOR_NORMAL_FG)

    def _scroll_to_center(self, row: int) -> None:
        """
        字幕同步滚动核心逻辑：
        计算目标行在 viewport 中的位置，使其尽量处于可视区域垂直中央。
        """
        item = self.item(row)
        if item is None:
            return

        # scrollTo 配合 PositionAtCenter 将当前播放字幕居中显示
        self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

    def _handle_item_clicked(self, item: QListWidgetItem) -> None:
        """点击字幕行 → 发射索引信号，由主窗口触发视频 seek。"""
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is not None:
            self.subtitle_clicked.emit(int(index))

    @staticmethod
    def _format_item_text(entry: SubtitleEntry) -> str:
        return f"{entry.format_time_range()}\n{entry.text}"

    def clear_subtitles(self) -> None:
        self.clear()
        self._entries.clear()
        self._highlight_index = -1
