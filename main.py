"""
ZPlayer 入口
本地电影字幕同步对照工具
"""

from __future__ import annotations

import logging
import sys


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()

    try:
        from ui.main_window import MainWindow
    except RuntimeError as exc:
        # libVLC 未安装或未找到时给出明确提示（Windows 最常见）
        msg = str(exc)
        print(msg, file=sys.stderr)
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox

            app = QApplication(sys.argv)
            QMessageBox.critical(None, "缺少 VLC 组件", msg)
        except Exception:
            pass
        return 1

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("ZPlayer")
    app.setOrganizationName("ZPlayer")

    # 应用暗色主题（全局字体 + QSS 样式表 + 图标默认色 + 窗口图标）
    from ui.theme import apply_theme
    apply_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
