#!/usr/bin/env python3
"""
生成 ZPlayer 应用图标 (.icns)。

使用 qtawesome 渲染 fa5s.film 图标为多尺寸 PNG，
然后通过 iconutil 生成 macOS .icns 文件。

用法:
    python scripts/generate_icon.py [--output ZPlayer.icns]

在 CI (macOS) 中运行；Windows 上仅生成 .iconset 目录。
"""

from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path

# macOS .iconset 需要的尺寸规格: (filename, size_px, scale)
_ICON_SIZES = [
    ("icon_16x16.png", 16, 1),
    ("icon_16x16@2x.png", 32, 2),
    ("icon_32x32.png", 32, 1),
    ("icon_32x32@2x.png", 64, 2),
    ("icon_128x128.png", 128, 1),
    ("icon_128x128@2x.png", 256, 2),
    ("icon_256x256.png", 256, 1),
    ("icon_256x256@2x.png", 512, 2),
    ("icon_512x512.png", 512, 1),
    ("icon_512x512@2x.png", 1024, 2),
]


def render_icon(iconset_dir: Path) -> None:
    """用 qtawesome 渲染图标为各尺寸 PNG。"""
    import qtawesome as qta
    from PyQt6.QtGui import QPixmap, QPainter
    from PyQt6.QtCore import QSize, QRectF
    from PyQt6.QtWidgets import QApplication

    # QApplication 必须存在才能创建 QPixmap
    app = QApplication.instance() or QApplication(sys.argv)

    # 背景色 + 图标色（与主题一致）
    bg_color = "#1a1b26"
    icon_color = "#4a9eff"

    iconset_dir.mkdir(parents=True, exist_ok=True)

    for filename, size_px, scale in _ICON_SIZES:
        # 创建带圆角背景的 pixmap
        actual_size = size_px * scale
        pixmap = QPixmap(actual_size, actual_size)
        pixmap.fill()  # 透明背景

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 绘制圆角矩形背景
        from PyQt6.QtGui import QColor, QBrush, QPainterPath
        path = QPainterPath()
        radius = actual_size * 0.22  # 圆角半径约为 22%
        path.addRoundedRect(0, 0, actual_size, actual_size, radius, radius)
        painter.fillPath(path, QBrush(QColor(bg_color)))

        # 绘制图标（居中，占 60% 区域）
        qta_icon = qta.icon("fa5s.film", color=icon_color)
        icon_size = int(actual_size * 0.6)
        icon_x = (actual_size - icon_size) // 2
        icon_y = (actual_size - icon_size) // 2
        qta_icon.paint(painter, icon_x, icon_y, icon_size, icon_size)

        painter.end()

        save_path = iconset_dir / filename
        pixmap.save(str(save_path), "PNG")
        print(f"  生成 {filename} ({actual_size}x{actual_size})")


def convert_to_icns(iconset_dir: Path, output_path: Path) -> bool:
    """使用 iconutil 将 .iconset 转换为 .icns (仅 macOS)。"""
    if sys.platform != "darwin":
        print(f"非 macOS 平台，跳过 iconutil 转换。.iconset 目录: {iconset_dir}")
        return False

    try:
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"iconutil 失败: {result.stderr}", file=sys.stderr)
            return False
        print(f"已生成: {output_path}")
        return True
    except FileNotFoundError:
        print("iconutil 未找到（非 macOS？），跳过 .icns 转换", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 ZPlayer 应用图标")
    parser.add_argument(
        "--output", "-o",
        default="ZPlayer.icns",
        help="输出 .icns 文件路径 (默认: ZPlayer.icns)",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    iconset_dir = output_path.parent / "ZPlayer.iconset"

    print("正在渲染图标...")
    render_icon(iconset_dir)

    print("正在转换为 .icns...")
    success = convert_to_icns(iconset_dir, output_path)

    if not success and sys.platform != "darwin":
        # 非 macOS 上也生成一份 PNG 供其他用途
        print(f"\n.iconset 目录已生成: {iconset_dir}")
        print("在 macOS 上运行此脚本可生成 .icns 文件")

    return 0


if __name__ == "__main__":
    sys.exit(main())
