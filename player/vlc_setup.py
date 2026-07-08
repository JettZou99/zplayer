"""
libVLC 路径配置模块

必须在 `import vlc` 之前调用 configure_vlc()。
Windows 下 python-vlc 默认从当前工作目录加载 libvlc.dll，
若未安装 VLC 或未配置 PATH，会报 FileNotFoundError。
本模块自动探测常见安装路径并设置环境变量。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

_CONFIGURED = False
_VLC_LIB_PATH: Optional[Path] = None
_VLC_PLUGIN_PATH: Optional[Path] = None


def get_vlc_plugin_path() -> Optional[Path]:
    """返回已探测到的 VLC plugins 目录，供 Instance 初始化使用。"""
    return _VLC_PLUGIN_PATH


def configure_vlc() -> None:
    """探测 libVLC 安装位置并写入 python-vlc 所需的环境变量。"""
    global _CONFIGURED, _VLC_LIB_PATH, _VLC_PLUGIN_PATH
    if _CONFIGURED:
        return

    if os.environ.get("PYTHON_VLC_LIB_PATH"):
        _VLC_LIB_PATH = Path(os.environ["PYTHON_VLC_LIB_PATH"])
        _VLC_PLUGIN_PATH = Path(os.environ["PYTHON_VLC_MODULE_PATH"]) if os.environ.get(
            "PYTHON_VLC_MODULE_PATH"
        ) else _VLC_LIB_PATH.parent / "plugins"
        os.environ["VLC_PLUGIN_PATH"] = str(_VLC_PLUGIN_PATH)
        _apply_windows_dll_path(_VLC_LIB_PATH.parent)
        _CONFIGURED = True
        return

    lib_path, plugins_path = _locate_vlc()

    if lib_path is None:
        raise RuntimeError(_build_install_hint())

    _VLC_LIB_PATH = lib_path
    _VLC_PLUGIN_PATH = plugins_path

    os.environ["PYTHON_VLC_LIB_PATH"] = str(lib_path)
    if plugins_path is not None:
        os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugins_path)
        # VLC_PLUGIN_PATH 是 libVLC 自身读取的环境变量（与 python-vlc 的
        # PYTHON_VLC_MODULE_PATH 不同）。若不显式设置，libVLC 在某些场景下
        # （如通过 add_dll_directory 加载 DLL 时）无法自动定位插件目录，
        # 导致编解码器模块缺失，媒体对象创建失败。
        os.environ["VLC_PLUGIN_PATH"] = str(plugins_path)

    _apply_windows_dll_path(lib_path.parent)
    _CONFIGURED = True


def _locate_vlc() -> tuple[Optional[Path], Optional[Path]]:
    """按平台返回 (libvlc 文件路径, plugins 目录)。"""
    if sys.platform.startswith("win"):
        return _locate_vlc_windows()
    if sys.platform == "darwin":
        return _locate_vlc_macos()
    return _locate_vlc_linux()


def _locate_vlc_windows() -> tuple[Optional[Path], Optional[Path]]:
    candidates: list[Path] = []

    # 1. 用户自定义路径（便于便携版或非标安装）
    for env_key in ("ZPLAYER_VLC_PATH", "VLC_HOME"):
        custom = os.environ.get(env_key)
        if custom:
            candidates.append(Path(custom))

    # 2. 注册表 InstallDir（与 python-vlc 相同逻辑，但更可靠地收集候选）
    reg_dir = _read_vlc_registry_install_dir()
    if reg_dir:
        candidates.append(reg_dir)

    # 3. 常见安装目录
    for env_key in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.environ.get(env_key)
        if base:
            candidates.append(Path(base) / "VideoLAN" / "VLC")

    candidates.extend(
        [
            Path(r"C:\Program Files\VideoLAN\VLC"),
            Path(r"C:\Program Files (x86)\VideoLAN\VLC"),
        ]
    )

    seen: set[str] = set()
    for directory in candidates:
        key = str(directory).lower()
        if key in seen:
            continue
        seen.add(key)

        lib_path = directory / "libvlc.dll"
        if lib_path.is_file():
            plugins = directory / "plugins"
            return lib_path, plugins if plugins.is_dir() else None

    return None, None


def _read_vlc_registry_install_dir() -> Optional[Path]:
    try:
        import winreg as w
    except ImportError:
        return None

    for root in (w.HKEY_LOCAL_MACHINE, w.HKEY_CURRENT_USER):
        try:
            with w.OpenKey(root, r"Software\VideoLAN\VLC") as key:
                install_dir, _ = w.QueryValueEx(key, "InstallDir")
                path = Path(str(install_dir))
                if path.is_dir():
                    return path
        except OSError:
            continue
    return None


def _locate_vlc_macos() -> tuple[Optional[Path], Optional[Path]]:
    app_dir = Path("/Applications/VLC.app/Contents/MacOS")
    lib_path = app_dir / "lib" / "libvlc.dylib"
    if lib_path.is_file():
        for name in ("plugins", "modules"):
            plugins = app_dir / name
            if plugins.is_dir():
                return lib_path, plugins
        return lib_path, None
    return None, None


def _locate_vlc_linux() -> tuple[Optional[Path], Optional[Path]]:
    search_dirs = [
        Path("/usr/lib"),
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/local/lib"),
    ]
    for directory in search_dirs:
        for name in ("libvlc.so.5", "libvlc.so"):
            lib_path = directory / name
            if lib_path.is_file():
                for plugins in (
                    Path("/usr/lib/vlc/plugins"),
                    Path("/usr/local/lib/vlc/plugins"),
                ):
                    if plugins.is_dir():
                        return lib_path, plugins
                return lib_path, None
    return None, None


def _apply_windows_dll_path(vlc_dir: Path) -> None:
    """
    Python 3.8+ 在 Windows 上需要显式 add_dll_directory，
    否则 libvlc.dll 的依赖项（libvlccore.dll 等）无法加载。
    """
    if not sys.platform.startswith("win"):
        return

    vlc_str = str(vlc_dir)
    os.environ["PATH"] = vlc_str + os.pathsep + os.environ.get("PATH", "")

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(vlc_str)


def _build_install_hint() -> str:
    import sys

    if sys.platform == "darwin":
        return (
            "未找到 libVLC（libvlc.dylib）。\n\n"
            "请按以下步骤操作：\n"
            "1. 安装 VLC：https://www.videolan.org/vlc/\n"
            "   或使用 Homebrew: brew install --cask vlc\n"
            "2. 确认存在：/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib\n"
            "3. 若已安装但仍报错，可设置环境变量后重试：\n"
            "   export ZPLAYER_VLC_PATH=/Applications/VLC.app/Contents/MacOS/lib"
        )
    return (
        "未找到 libVLC（libvlc.dll）。\n\n"
        "请按以下步骤操作：\n"
        "1. 安装 VLC 64 位：https://www.videolan.org/vlc/\n"
        "2. 确认存在：C:\\Program Files\\VideoLAN\\VLC\\libvlc.dll\n"
        "3. 若已安装但仍报错，可设置环境变量后重试：\n"
        "   set ZPLAYER_VLC_PATH=C:\\Program Files\\VideoLAN\\VLC\n"
        "4. 确保 Python 与 VLC 同为 64 位"
    )
