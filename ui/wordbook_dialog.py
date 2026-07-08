"""单词本对话框 — 查看、搜索、删除和导出收藏的单词。"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from data.models import CollectedWord
from data.wordbook_db import WordBookDB
from ui.theme import HTML_LINK, HTML_MUTED, icon

logger = logging.getLogger(__name__)

# 列定义: (标题, 宽度)
_COLUMNS = [
    ("单词", 120),
    ("音标", 130),
    ("释义", 200),
    ("字幕句子", 250),
    ("视频文件名", 120),
    ("收藏时间", 150),
]


class WordBookDialog(QDialog):
    """单词本对话框（非模态），查看/搜索/删除/导出收藏的单词。"""

    def __init__(self, db: WordBookDB, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("单词本")
        self.resize(1000, 550)
        self._db = db
        self._all_words: list[CollectedWord] = []
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- 搜索栏 ---
        search_bar = QHBoxLayout()
        search_bar.setSpacing(6)
        search_bar.addWidget(QLabel("搜索:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入单词进行筛选...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_bar.addWidget(self._search_edit, 1)
        self._count_label = QLabel("共 0 个单词")
        self._count_label.setStyleSheet("color: #9fa0ab;")
        search_bar.addWidget(self._count_label)
        layout.addLayout(search_bar)

        # --- 表格 ---
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(True)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        for i, (_, width) in enumerate(_COLUMNS):
            self._table.setColumnWidth(i, width)
        # 字幕句子列可拉伸
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, 1)

        # --- 底部按钮栏 ---
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self._delete_btn = QPushButton(icon("fa5s.trash-alt"), " 删除选中")
        self._delete_btn.setIconSize(QSize(16, 16))
        self._delete_btn.clicked.connect(self._on_delete)
        btn_bar.addWidget(self._delete_btn)
        self._export_btn = QPushButton(icon("fa5s.file-export"), " 导出 CSV")
        self._export_btn.setIconSize(QSize(16, 16))
        self._export_btn.clicked.connect(self._on_export)
        btn_bar.addWidget(self._export_btn)
        self._close_btn = QPushButton(icon("fa5s.times"), " 关闭")
        self._close_btn.setIconSize(QSize(16, 16))
        self._close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(self._close_btn)
        layout.addLayout(btn_bar)

    # ------------------------------------------------------------------ #
    # 数据加载
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """从数据库重新加载数据并刷新表格。"""
        keyword = self._search_edit.text().strip()
        if keyword:
            self._all_words = self._db.search(keyword)
        else:
            self._all_words = self._db.get_all()
        self._fill_table()
        self._count_label.setText(f"共 {len(self._all_words)} 个单词")

    def _fill_table(self) -> None:
        """将 _all_words 填充到表格中。"""
        self._table.setRowCount(0)
        for row_idx, w in enumerate(self._all_words):
            self._table.insertRow(row_idx)

            # 单词
            word_item = QTableWidgetItem(w.word)
            word_item.setData(Qt.ItemDataRole.UserRole, w.id)
            font = word_item.font()
            font.setBold(True)
            word_item.setFont(font)
            self._table.setItem(row_idx, 0, word_item)

            # 音标（美/英合并）
            phonetic_parts: list[str] = []
            if w.us_phonetic:
                phonetic_parts.append(f"美 {w.us_phonetic}")
            if w.uk_phonetic:
                phonetic_parts.append(f"英 {w.uk_phonetic}")
            self._table.setItem(
                row_idx, 1, QTableWidgetItem("  ".join(phonetic_parts))
            )

            # 释义
            self._table.setItem(row_idx, 2, QTableWidgetItem(w.definitions_text))

            # 字幕句子
            self._table.setItem(
                row_idx, 3, QTableWidgetItem(w.subtitle_text or "")
            )

            # 视频文件名
            self._table.setItem(
                row_idx, 4, QTableWidgetItem(w.video_name or "")
            )

            # 收藏时间
            self._table.setItem(
                row_idx, 5, QTableWidgetItem(w.collected_at)
            )

    # ------------------------------------------------------------------ #
    # 事件处理
    # ------------------------------------------------------------------ #

    def _on_search_changed(self, text: str) -> None:
        """搜索框文本变化时实时过滤。"""
        self.refresh()

    def _on_delete(self) -> None:
        """删除选中的单词。"""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "请先选中要删除的单词行。")
            return

        word_count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {word_count} 个单词吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 收集要删除的 ID
        ids_to_delete: list[int] = []
        for index in selected_rows:
            row = index.row()
            item = self._table.item(row, 0)
            if item:
                word_id = item.data(Qt.ItemDataRole.UserRole)
                if word_id is not None:
                    ids_to_delete.append(word_id)

        # 批量删除
        deleted = 0
        for wid in ids_to_delete:
            if self._db.remove_by_id(wid):
                deleted += 1

        if deleted > 0:
            self.refresh()
            QMessageBox.information(
                self, "删除成功", f"已删除 {deleted} 个单词。"
            )

    def _on_export(self) -> None:
        """导出全部收藏单词到 CSV 文件。"""
        if self._db.count() == 0:
            QMessageBox.information(self, "提示", "单词本为空，无需导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            "zplayer_wordbook.csv",
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not file_path:
            return

        if self._db.export_csv(file_path):
            QMessageBox.information(
                self, "导出成功", f"已导出到:\n{file_path}"
            )
        else:
            QMessageBox.warning(self, "导出失败", "导出 CSV 时出错，请重试。")

    def _on_double_click(self, index) -> None:
        """双击行查看详情。"""
        row = index.row()
        if row < 0 or row >= len(self._all_words):
            return
        w = self._all_words[row]
        self._show_detail(w)

    def _show_detail(self, w: CollectedWord) -> None:
        """弹出单词详情对话框。"""
        lines: list[str] = []
        lines.append(f"<h2 style='color:{HTML_LINK};'>{w.word}</h2>")
        if w.us_phonetic:
            lines.append(f"<p>美 {w.us_phonetic}</p>")
        if w.uk_phonetic:
            lines.append(f"<p>英 {w.uk_phonetic}</p>")
        if w.definitions:
            lines.append("<hr>")
            for pos, meaning in w.definitions:
                if pos:
                    lines.append(f"<p><b>{pos}</b> {meaning}</p>")
                else:
                    lines.append(f"<p>{meaning}</p>")
        if w.subtitle_text:
            lines.append("<hr>")
            lines.append(f"<p style='color:{HTML_MUTED};'>字幕原句: {w.subtitle_text}</p>")
            if w.subtitle_time_range:
                lines.append(
                    f"<p style='color:{HTML_MUTED}; font-size:12px;'>"
                    f"时间轴: {w.subtitle_time_range}</p>"
                )
        if w.video_name:
            lines.append(
                f"<p style='color:{HTML_MUTED}; font-size:12px;'>来源: {w.video_name}</p>"
            )
        lines.append(
            f"<p style='color:{HTML_MUTED}; font-size:12px;'>收藏于: {w.collected_at}</p>"
        )

        msg = QMessageBox(self)
        msg.setWindowTitle("单词详情")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText("".join(lines))
        msg.exec()
