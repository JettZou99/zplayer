"""
跨平台工具模块。
统一管理字体名称、数据目录等平台差异。
"""

from __future__ import annotations

import sys
from pathlib import Path


# ================================================================== #
# 字体配置
# ================================================================== #

_FONT_MAP: dict[str, list[str]] = {
    "win32": ["Microsoft YaHei UI", "Segoe UI", "sans-serif"],
    "darwin": ["PingFang SC", "Helvetica Neue", "sans-serif"],
    "linux": ["Noto Sans CJK SC", "DejaVu Sans", "sans-serif"],
}


def get_font_family() -> list[str]:
    """返回当前平台推荐的字体名称列表（按优先级排列）。"""
    return _FONT_MAP.get(sys.platform, _FONT_MAP["linux"])


def get_font_css() -> str:
    """返回 CSS font-family 字符串（如 "PingFang SC","Helvetica Neue",sans-serif）。"""
    fonts = get_font_family()
    # 含空格的字体名用引号包裹，通用字体（sans-serif 等）不加引号
    parts: list[str] = []
    for f in fonts:
        if " " in f or "." in f:
            parts.append(f'"{f}"')
        else:
            parts.append(f)
    return ",".join(parts)


# ================================================================== #
# 数据目录
# ================================================================== #

_APP_NAME = "ZPlayer"


def get_app_data_dir() -> Path:
    """
    返回应用数据存储目录。

    - macOS: ~/Library/Application Support/ZPlayer/
    - 其他: ~/.zplayer/
    """
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / _APP_NAME
    else:
        path = Path.home() / ".zplayer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    """返回单词本数据库路径。"""
    return get_app_data_dir() / "wordbook.db"
