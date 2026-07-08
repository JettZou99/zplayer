"""
翻译后台 Worker —— 在 QThread 中调用有道 API，通过信号返回结果。

遵循 SubtitleExtractWorker 的信号模式。
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from ui.translator import TranslationError, YoudaoTranslator

logger = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """
    后台查询单词翻译的 QThread。

    信号:
        finished_ok(dict): 翻译成功，传递 TranslationResult.to_dict()
        finished_error(str): 翻译失败，传递错误信息
    """

    finished_ok = pyqtSignal(dict)
    finished_error = pyqtSignal(str)

    def __init__(self, word: str, parent=None) -> None:
        super().__init__(parent)
        self._word = word

    def run(self) -> None:
        """执行翻译查询。"""
        try:
            result = YoudaoTranslator.translate(self._word)
            self.finished_ok.emit(result.to_dict())
        except TranslationError as exc:
            logger.warning("翻译失败: %s -> %s", self._word, exc)
            self.finished_error.emit(str(exc))
        except Exception as exc:
            logger.exception("翻译未知异常: %s", self._word)
            self.finished_error.emit(f"翻译查询失败: {exc}")
