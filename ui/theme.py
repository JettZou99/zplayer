"""
ZPlayer 暗色主题模块

集中管理：
- 暗色配色常量
- 全局 QSS 样式表 (DARK_STYLESHEET)
- 应用主题初始化 (apply_theme)
- 图标辅助函数 (icon)
- 状态栏组件 (StatusBarItem)
- HTML 颜色常量（供 QTextBrowser 内联样式使用）
"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from utils.platforms import get_font_css, get_font_family


# ================================================================== #
# 暗色配色方案
# ================================================================== #

# 背景层级（由深到浅）
BG_BASE = "#1a1b26"        # 主窗口/应用底色（最深）
BG_SURFACE = "#1f2030"     # 面板、侧栏、字幕列表背景
BG_ELEVATED = "#272838"    # 工具栏、表头、按钮背景
BG_INPUT = "#161720"       # 输入框、文本区域背景
BG_ALTERNATE = "#232434"   # 交替行背景
BG_HOVER = "#313248"       # 悬停态背景

# 文字
TEXT_PRIMARY = "#e4e4e7"   # 主文字
TEXT_SECONDARY = "#9fa0ab" # 次要文字
TEXT_DISABLED = "#5c5d6b"  # 禁用文字

# 边框
BORDER = "#353648"         # 标准边框、分割线
BORDER_LIGHT = "#3f4055"   # 悬停态边框

# 强调色
ACCENT = "#4a9eff"         # 主强调色（蓝色）
ACCENT_HOVER = "#62b0ff"   # 强调悬停
ACCENT_PRESSED = "#3b82f6" # 强调按下

# 高亮（当前播放字幕行）
HIGHLIGHT_BG = "#3d3417"   # 高亮背景（深琥珀色）
HIGHLIGHT_FG = "#ffd966"   # 高亮文字（金色）

# 选择态
SELECTION_BG = "#2a3a5c"  # 选中项背景
SELECTION_FG = "#4a9eff"  # 选中项文字

# 语义色
ERROR = "#ff6b6b"          # 错误文字
WARNING = "#ffa000"        # 警告/收藏星标色
SUCCESS = "#4caf50"        # 成功
VIDEO_BG = "#000000"       # 视频区域纯黑


# ================================================================== #
# HTML 颜色常量（供 QTextBrowser 内联样式使用）
# ================================================================== #

HTML_TEXT = TEXT_PRIMARY
HTML_LINK = ACCENT
HTML_MUTED = TEXT_SECONDARY
HTML_ERROR = ERROR
HTML_WARNING = WARNING

# 跨平台字体 CSS 字串
_FONT_CSS = get_font_css()

# 预格式化的 HTML body style 字符串
HTML_BODY_STYLE = (
    f"font-size:13px; "
    f"font-family:{_FONT_CSS}; "
    f"color:{HTML_TEXT};"
)


# ================================================================== #
# 全局 QSS 样式表
# ================================================================== #

DARK_STYLESHEET = f"""
/* === 基础控件 === */
QMainWindow, QDialog {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
}}

QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: {_FONT_CSS};
    font-size: 9pt;
}}

QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}

/* === 工具栏 === */
QToolBar {{
    background-color: {BG_ELEVATED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    color: {TEXT_PRIMARY};
    font-size: 9pt;
}}
QToolBar QToolButton:hover {{
    background-color: {BG_HOVER};
}}
QToolBar QToolButton:pressed {{
    background-color: {BORDER};
}}
QToolBar QToolButton:disabled {{
    color: {TEXT_DISABLED};
}}

/* === 状态栏 === */
QStatusBar {{
    background-color: {BG_SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 9pt;
}}
QStatusBar QLabel {{
    color: {TEXT_SECONDARY};
    padding: 0px 4px;
}}

/* === 按钮 === */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 9pt;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_LIGHT};
}}
QPushButton:pressed {{
    background-color: {BG_SURFACE};
}}
QPushButton:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_DISABLED};
    border-color: {BG_SURFACE};
}}
QPushButton[collected='true'] {{
    color: {WARNING};
    border-color: {WARNING};
}}

/* === 滑块 === */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::add-page:horizontal {{
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: {ACCENT};
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}

/* === 分割器 === */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* === 列表控件 === */
QListWidget {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    outline: none;
    alternate-background-color: {BG_ALTERNATE};
}}
QListWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {BG_ELEVATED};
}}
QListWidget::item:selected {{
    background: {SELECTION_BG};
    color: {SELECTION_FG};
}}
QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}

/* === 表格 === */
QTableWidget {{
    background-color: {BG_SURFACE};
    alternate-background-color: {BG_ALTERNATE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    gridline-color: {BORDER};
    color: {TEXT_PRIMARY};
    outline: none;
}}
QTableWidget::item {{
    padding: 4px;
}}
QTableWidget::item:selected {{
    background: {SELECTION_BG};
    color: {SELECTION_FG};
}}
QHeaderView::section {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-weight: bold;
    font-size: 9pt;
}}

/* === 输入框 === */
QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {SELECTION_BG};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}

/* === 文本浏览器 === */
QTextBrowser {{
    background: transparent;
    border: none;
    color: {TEXT_PRIMARY};
}}

/* === 滚动条 === */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_LIGHT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    border: none;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER_LIGHT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0;
    border: none;
    background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* === 视频帧 === */
QFrame#videoFrame {{
    background-color: {VIDEO_BG};
    border: 1px solid {BORDER};
}}

/* === 消息框 === */
QMessageBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
}}
QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
}}

/* === 滚动区域 === */
QScrollArea {{
    background: transparent;
    border: none;
}}
"""


# ================================================================== #
# 图标辅助函数
# ================================================================== #

def icon(name: str, color: str | None = None) -> QIcon:
    """
    创建带颜色的 QIcon。

    Args:
        name: qtawesome 图标名，如 'fa5s.play'
        color: 图标颜色 hex 值，不传则使用全局默认色

    Returns:
        QIcon 实例
    """
    kwargs: dict = {"color": color} if color else {}
    return qta.icon(name, **kwargs)


def apply_theme(app: QApplication) -> None:
    """
    应用暗色主题到 QApplication。

    - 设置全局字体
    - 设置应用级 QSS 样式表
    - 设置 qtawesome 默认图标颜色
    - 设置窗口图标
    """
    # 设置全局字体
    font = QFont(get_font_family()[0], 10)
    app.setFont(font)

    # 应用全局 QSS
    app.setStyleSheet(DARK_STYLESHEET)

    # 设置 qtawesome 默认图标颜色
    qta.set_defaults(
        color=TEXT_PRIMARY,
        color_disabled=TEXT_DISABLED,
        color_active=ACCENT_HOVER,
        color_selected=ACCENT,
    )

    # 设置窗口图标
    app.setWindowIcon(icon("fa5s.film", ACCENT))


# ================================================================== #
# 状态栏组件
# ================================================================== #

class StatusBarItem(QWidget):
    """
    状态栏永久组件：图标 + 文字。

    用于在状态栏右侧显示播放状态、字幕计数、收藏数量、音量等信息。
    """

    def __init__(self, icon_name: str = "", text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(16, 16)
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(text)
        layout.addWidget(self._text_label)

        if icon_name:
            self.set_icon(icon_name)

    def set_icon(self, icon_name: str, color: str = TEXT_SECONDARY) -> None:
        """更新图标。"""
        pix = icon(icon_name, color).pixmap(QSize(16, 16))
        self._icon_label.setPixmap(pix)

    def set_text(self, text: str) -> None:
        """更新文字。"""
        self._text_label.setText(text)

    def set_icon_and_text(self, icon_name: str, text: str, color: str = TEXT_SECONDARY) -> None:
        """同时更新图标和文字。"""
        self.set_icon(icon_name, color)
        self.set_text(text)
