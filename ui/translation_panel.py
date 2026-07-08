"""
固定翻译面板 — 替换 TranslationPopup，作为右侧面板的常驻部件。

布局（垂直）：
  [单词标题] [音标]              [×]
  ─────────────────────────────
  释义区域（QTextBrowser）
  ─────────────────────────────
  提示文字：点击字幕中的单词查看翻译：
  字幕原文（可点击单词的 QTextBrowser）
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

from ui.translator import TranslationResult
from ui.theme import HTML_BODY_STYLE, HTML_ERROR, HTML_LINK, HTML_MUTED, HTML_TEXT, WARNING, icon


class _ClickableTextBrowser(QTextBrowser):
    """
    QTextBrowser 子类：阻止链接点击时的默认导航。

    QTextBrowser 点击 <a href="word:xxx"> 链接时：
    1. 发射 anchorClicked(QUrl("word:xxx")) 信号
    2. 调用 setSource(QUrl) 尝试导航 → 产生 "No document" 警告

    本类通过覆盖 setSource 阻止导航；anchorClicked 由外部连接处理。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setReadOnly(True)

    def setSource(self, url, resourceType=None) -> None:  # noqa: ARG002 — 阻止导航
        """覆盖 setSource，吞掉所有导航请求，消除 'No document' 警告。"""
        pass


class TranslationPanel(QWidget):
    """
    固定翻译面板 — 常驻于右侧面板底部。

    信号:
        word_clicked(str): 用户点击字幕原文中的某个单词
        collection_toggled(object): 用户点击收藏按钮
            — 收藏时发射 CollectedWord 对象；取消收藏时发射 str(单词)
    """

    word_clicked = pyqtSignal(str)
    collection_toggled = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_word: str = ""
        self._current_subtitle_html: str = ""  # 保存字幕原文HTML，翻译时恢复用
        self._current_result: TranslationResult | None = None  # 当前翻译结果
        self._current_subtitle_context: dict = {}  # 字幕上下文（句子、时间、视频名）
        self._is_collected: bool = False  # 当前单词收藏状态
        self._build_ui()
        self.clear()

    # ------------------------------------------------------------------ #
    # 公开方法
    # ------------------------------------------------------------------ #

    def show_subtitle(self, text: str) -> None:
        """
        在面板中显示字幕原文，每个英文单词渲染为可点击链接。
        """
        if not text or not text.strip():
            self._subtitle_browser.setHtml(f"<p style='color:{HTML_MUTED};'>（空字幕）</p>")
            return

        words = self._extract_words(text)
        if words:
            # 有英文单词：渲染为可点击链接
            html_parts = []
            for w in words:
                html_parts.append(
                    f"<a href='word:{w}' style='color:{HTML_LINK}; text-decoration:none; "
                    f"hover:underline;'>{w}</a>"
                )
            # 用空格连接，保留原文大致排版
            content = ' '.join(html_parts)
        else:
            # 无英文单词：显示纯文本（可能是中文）
            content = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        html = (
            f"<html><body style='{HTML_BODY_STYLE}'>"
            f"{content}"
            f"</body></html>"
        )
        self._subtitle_browser.setHtml(html)
        self._current_subtitle_html = html  # 保存字幕原文HTML
        self._hint_label.setVisible(False)
        self._subtitle_browser.setVisible(True)

    def show_translation(self, result: TranslationResult) -> None:
        """显示翻译结果（音标 + 释义）。"""
        if result.is_empty:
            self._show_error("未找到该单词的翻译结果。")
            return

        self._current_word = result.word
        self._current_result = result  # 存储翻译结果供收藏使用

        # 单词标题
        self._word_label.setText(result.word)
        self._word_label.setVisible(True)

        # 音标
        phonetic_parts = []
        if result.us_phonetic:
            phonetic_parts.append(f"美 {result.us_phonetic}")
        if result.uk_phonetic:
            phonetic_parts.append(f"英 {result.uk_phonetic}")
        if phonetic_parts:
            self._phonetic_label.setText("    ".join(phonetic_parts))
            self._phonetic_label.setVisible(True)
        else:
            self._phonetic_label.setText("")
            self._phonetic_label.setVisible(False)

        # 释义
        if result.definitions:
            lines = []
            for pos, meaning in result.definitions:
                if pos:
                    lines.append(f"<b>{pos}</b>  {meaning}")
                else:
                    lines.append(f"• {meaning}")
            def_html = (
                f"<html><body style='{HTML_BODY_STYLE}'>"
                f"{'<br>'.join(lines)}"
                f"</body></html>"
            )
            self._definition_browser.setHtml(def_html)
        else:
            self._definition_browser.setHtml(
                f"<html><body style='color:{HTML_MUTED};'>（无释义数据）</body></html>"
            )
        self._definition_browser.setVisible(True)
        self._separator.setVisible(True)
        # 隐藏提示标签（已有翻译结果显示）
        self._hint_label.setVisible(False)
        # 恢复字幕原文区域的内容和可见性
        if self._current_subtitle_html:
            self._subtitle_browser.setHtml(self._current_subtitle_html)
        self._subtitle_browser.setVisible(True)
        # 显示收藏按钮
        self._collect_btn.setVisible(True)

    def show_loading(self, word: str) -> None:
        """显示加载状态。"""
        self._current_word = word
        self._word_label.setText(word)
        self._word_label.setVisible(True)
        self._phonetic_label.setText("查询中...")
        self._phonetic_label.setVisible(True)
        self._definition_browser.setHtml(
            f"<html><body style='color:{HTML_MUTED};'>正在查询翻译...</body></html>"
        )
        self._definition_browser.setVisible(True)
        self._separator.setVisible(True)
        # 隐藏收藏按钮（等待翻译结果返回后再显示）
        self._collect_btn.setVisible(False)
        # 隐藏提示标签（已有翻译结果显示）
        self._hint_label.setVisible(False)
        # 恢复字幕原文区域的内容和可见性
        if self._current_subtitle_html:
            self._subtitle_browser.setHtml(self._current_subtitle_html)
        self._subtitle_browser.setVisible(True)

    def show_error(self, message: str) -> None:
        """显示错误信息。"""
        self._show_error(message)
        # 隐藏提示标签（已有错误信息显示）
        self._hint_label.setVisible(False)
        # 恢复字幕原文区域的内容和可见性
        if self._current_subtitle_html:
            self._subtitle_browser.setHtml(self._current_subtitle_html)
        self._subtitle_browser.setVisible(True)

    def clear_translation(self) -> None:
        """仅清除翻译结果，保留字幕原文区域。"""
        self._current_word = ""
        self._current_result = None
        self._is_collected = False
        self._word_label.setText("")
        self._word_label.setVisible(False)
        self._phonetic_label.setText("")
        self._phonetic_label.setVisible(False)
        self._definition_browser.setHtml("")
        self._definition_browser.setVisible(False)
        self._separator.setVisible(False)
        # 重置收藏按钮
        self._collect_btn.setVisible(False)
        self._collect_btn.setIcon(icon("fa5.star"))
        self._collect_btn.setToolTip("收藏单词")
        self._collect_btn.setProperty("collected", "false")
        # 显示提示标签
        self._hint_label.setText("点击上方字幕原文中的单词查看翻译")
        self._hint_label.setVisible(True)
        # 不清除字幕原文区域的内容和 _current_subtitle_html

    def clear(self) -> None:
        """清空面板，恢复到初始状态（新视频加载时调用）。"""
        self.clear_translation()
        self._current_subtitle_html = ""  # 清空保存的字幕原文HTML
        self._subtitle_browser.setHtml(
            f"<html><body style='color:{HTML_MUTED}; font-size:13px;'>（字幕原文将在此处显示）</body></html>"
        )
        self._subtitle_browser.setVisible(True)

    def set_subtitle_context(
        self,
        text: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        video_name: str | None = None,
    ) -> None:
        """存储当前字幕上下文，供收藏时关联句子和视频来源。"""
        self._current_subtitle_context = {
            "text": text,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "video_name": video_name,
        }

    def set_collection_state(self, is_collected: bool) -> None:
        """设置收藏按钮状态（已收藏实心星 / 未收藏空心星）。"""
        self._is_collected = is_collected
        if is_collected:
            self._collect_btn.setIcon(icon("fa5s.star", WARNING))
            self._collect_btn.setToolTip("取消收藏")
            self._collect_btn.setProperty("collected", "true")
        else:
            self._collect_btn.setIcon(icon("fa5.star"))
            self._collect_btn.setToolTip("收藏单词")
            self._collect_btn.setProperty("collected", "false")
        # 刷新属性选择器样式
        self._collect_btn.style().unpolish(self._collect_btn)
        self._collect_btn.style().polish(self._collect_btn)

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """构建面板 UI。"""
        self.setObjectName("translationPanel")
        self.setMinimumHeight(200)  # 增加最小高度，确保字幕区域可见

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 标题栏：单词 + 音标 + 关闭按钮
        header = QHBoxLayout()
        header.setSpacing(8)

        self._word_label = QLabel("")
        font = QFont()
        font.setBold(True)
        font.setPointSize(15)
        self._word_label.setFont(font)
        self._word_label.setVisible(False)
        header.addWidget(self._word_label)

        self._phonetic_label = QLabel("")
        self._phonetic_label.setStyleSheet(f"color: {HTML_MUTED}; font-size: 12px;")
        self._phonetic_label.setVisible(False)
        header.addWidget(self._phonetic_label)

        header.addStretch()

        # 收藏按钮（图标切换：空心星 → 实心星）
        self._collect_btn = QPushButton()
        self._collect_btn.setFixedSize(28, 28)
        self._collect_btn.setIcon(icon("fa5.star"))
        self._collect_btn.setIconSize(QSize(16, 16))
        self._collect_btn.setToolTip("收藏单词")
        self._collect_btn.setVisible(False)  # 翻译结果出现后才显示
        self._collect_btn.clicked.connect(self._on_collect_clicked)
        header.addWidget(self._collect_btn)

        # 关闭按钮（X 图标）
        self._close_btn = QPushButton()
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setIcon(icon("fa5s.times"))
        self._close_btn.setIconSize(QSize(14, 14))
        self._close_btn.setToolTip("清除翻译结果")
        self._close_btn.clicked.connect(self._on_close_clicked)
        header.addWidget(self._close_btn)

        layout.addLayout(header)

        # 释义区域
        self._definition_browser = QTextBrowser()
        self._definition_browser.setMinimumHeight(60)
        self._definition_browser.setMaximumHeight(150)
        self._definition_browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )
        layout.addWidget(self._definition_browser)

        # 分隔线
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setStyleSheet("color: #353648;")
        layout.addWidget(self._separator)

        # 提示文字
        self._hint_label = QLabel("")
        self._hint_label.setStyleSheet(f"color: {HTML_MUTED}; font-size: 12px;")
        layout.addWidget(self._hint_label)

        # 字幕原文区域（可点击单词）
        self._subtitle_browser = _ClickableTextBrowser()
        self._subtitle_browser.setObjectName("subtitleArea")
        self._subtitle_browser.setMinimumHeight(50)  # 确保至少显示2-3行
        self._subtitle_browser.anchorClicked.connect(self._on_anchor_clicked)
        layout.addWidget(self._subtitle_browser, 1)  # 拉伸因子1，占据剩余空间

        # Esc 快捷键关闭面板
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut.activated.connect(self._on_esc_pressed)

    def _on_anchor_clicked(self, url) -> None:
        """处理单词点击 — 从 QUrl 中提取单词。"""
        word = url.toString()
        if word.startswith("word:"):
            word = word[5:]
        if word.startswith("//"):
            word = word[2:]
        word = word.strip()
        if word:
            self.word_clicked.emit(word)

    def _on_close_clicked(self) -> None:
        """关闭按钮 → 仅清除翻译结果，保留字幕原文。"""
        self.clear_translation()

    def _on_collect_clicked(self) -> None:
        """收藏/取消收藏按钮点击。"""
        if self._is_collected:
            # 取消收藏 — 发送单词字符串
            self.collection_toggled.emit(self._current_word)
        else:
            # 收藏 — 发送 CollectedWord 对象
            if self._current_result:
                from data.models import CollectedWord

                collected = CollectedWord.from_translation(
                    result=self._current_result,
                    subtitle_text=self._current_subtitle_context.get("text"),
                    subtitle_start_ms=self._current_subtitle_context.get(
                        "start_ms"
                    ),
                    subtitle_end_ms=self._current_subtitle_context.get("end_ms"),
                    video_name=self._current_subtitle_context.get("video_name"),
                )
                self.collection_toggled.emit(collected)

    def _on_esc_pressed(self) -> None:
        """Esc 键 → 仅清除翻译结果，保留字幕原文。"""
        self.clear_translation()

    def _show_error(self, message: str) -> None:
        """在释义区域显示错误信息。"""
        self._definition_browser.setHtml(
            f"<html><body style='color:{HTML_ERROR};'>{message}</body></html>"
        )
        self._definition_browser.setVisible(True)

    @staticmethod
    def _extract_words(text: str) -> list[str]:
        """
        从字幕原文中提取英文单词列表。

        保留大小写，去除首尾标点。
        缩写（don't, it's）保留原形。
        """
        import re
        # 匹配英文单词（含缩写中的撇号）
        return re.findall(r"\b[\w']+\b", text)
