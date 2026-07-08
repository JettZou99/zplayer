"""PyQt6 界面子包。"""

# 延迟导入，避免在非GUI环境下导入PyQt6时报错
def __getattr__(name):
    if name == "MainWindow":
        from ui.main_window import MainWindow
        return MainWindow
    raise AttributeError(f"module 'ui' has no attribute '{name}'")


__all__ = ["MainWindow"]
