# ZPlayer — 本地电影字幕同步对照工具

基于 **Python 3.10+ / PyQt6 / libVLC / FFmpeg / Whisper** 的纯本地桌面应用。  
左侧播放视频，右侧展示完整字幕列表，支持实时高亮同步、自动滚动跟随，以及点击字幕跳转播放位置。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 视频播放 | 支持 MP4 / MKV / AVI 等格式，播放、暂停、进度拖动、音量调节 |
| 软字幕提取 | MKV/MP4 内置字幕轨道 → FFmpeg 直接导出 SRT |
| 硬字幕/无轨识别 | 无内置字幕 → Whisper 离线 ASR 生成带毫秒时间戳的 SRT |
| 实时同步 | 监听播放进度，高亮当前字幕行，列表自动滚动居中 |
| 点击跳转 | 点击任意字幕行，视频 seek 到该句 `start_ms` |

---

## 环境要求

- **Python** 3.10 或以上
- **VLC 媒体播放器**（需安装完整版，提供 libvlc.dll）
- **FFmpeg**（含 `ffmpeg` 与 `ffprobe`，已加入系统 PATH）
- （可选）NVIDIA GPU 可加速 Whisper，非必须

---

## 一、依赖安装

### 1. 创建虚拟环境（推荐）

```bash
cd D:\Projects\zplayer
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Windows CMD
.\.venv\Scripts\activate.bat
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

> **说明**：首次使用 Whisper 时会自动下载模型（`base` 约 140MB）。  
> 可在 `ui/main_window.py` 中将 `whisper_model="base"` 改为 `tiny`（更快）或 `small`（更准）。

---

## 二、FFmpeg 环境配置

### Windows

1. 从 [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) 或 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载 **ffmpeg-release-full** 压缩包  
2. 解压到例如 `C:\ffmpeg`  
3. 将 `C:\ffmpeg\bin` 加入系统环境变量 **PATH**  
4. 新开终端验证：

```bash
ffmpeg -version
ffprobe -version
```

### macOS

```bash
brew install ffmpeg
```

### Linux

```bash
sudo apt install ffmpeg   # Debian/Ubuntu
```

---

## 三、VLC（libVLC）配置

### Windows

1. **必须先安装** [VLC 官方客户端 64 位](https://www.videolan.org/vlc/)（仅 pip 安装 `python-vlc` 不够，还需要系统里的 libvlc.dll）
2. 默认安装路径：`C:\Program Files\VideoLAN\VLC\`
3. 安装后确认存在 `libvlc.dll`：

```powershell
Test-Path "C:\Program Files\VideoLAN\VLC\libvlc.dll"   # 应返回 True
```

4. 程序启动时会**自动探测**上述路径；若 VLC 装在非标准位置，可设置环境变量：

```powershell
$env:ZPLAYER_VLC_PATH = "D:\Apps\VLC"
python main.py
```

5. 确保 **Python 与 VLC 同为 64 位**（你当前是 Python 3.13 64 位，请安装 64 位 VLC）

### macOS / Linux

```bash
# macOS
brew install vlc

# Ubuntu
sudo apt install vlc libvlc-dev
```

---

## 四、运行

```bash
python main.py
```

### 使用步骤

1. 点击工具栏 **「打开视频」**，选择本地 MP4/MKV/AVI 等文件  
2. 程序自动检测字幕轨道：  
   - **有内置软字幕** → FFmpeg 提取为 SRT  
   - **无字幕轨道** → Whisper 识别音频（耗时较长，状态栏有进度提示）  
3. 右侧显示全部字幕；播放时当前句 **黄色高亮** 并 **自动滚动到列表中间**  
4. **点击** 任意字幕行 → 左侧视频跳转到该句开始时间  
5. 可用进度条拖动、音量滑块调节播放  

也可手动点击 **「提取字幕」** 重新提取。

---

## 五、项目结构

```
zplayer/
├── main.py                      # 程序入口
├── requirements.txt             # pip 依赖清单
├── README.md                    # 本说明
├── player/
│   └── vlc_player.py            # libVLC 播放器封装（播放/seek/毫秒进度）
├── subtitles/
│   ├── models.py                # SubtitleEntry 数据模型
│   └── extractor.py             # FFmpeg 软字幕提取 + Whisper ASR + pysrt 解析
├── sync/
│   └── subtitle_sync.py         # 播放进度匹配、高亮、点击跳转逻辑
└── ui/
    ├── main_window.py           # 主窗口、分割布局、模块整合
    ├── video_panel.py           # 左侧视频区与播放控件
    ├── subtitle_list.py         # 右侧字幕列表（高亮/滚动/点击）
    └── workers.py               # 字幕提取后台线程
```

---

## 六、关键逻辑说明

### 1. 软字幕 vs 硬字幕/无轨（`subtitles/extractor.py`）

```
ffprobe 探测视频流
    │
    ├─ 存在 codec_type=subtitle 的流 → 软字幕
    │       └─ ffmpeg -map 0:N -c:s srt 导出 SRT
    │
    └─ 无 subtitle 流 → 硬字幕烧录或无字幕
            └─ Whisper 转写音频 → 手写 SRT（毫秒时间戳）
```

硬字幕无法从轨道提取，只能 OCR 或 ASR；本工具对无轨场景采用 **Whisper 语音识别**。

### 2. 播放-字幕同步滚动（`sync/subtitle_sync.py` + `ui/subtitle_list.py`）

- 主窗口 `QTimer` 每 **50ms** 读取 `VlcPlayer.get_time_ms()`  
- `SubtitleSyncController.update_playback_time()` 用 **二分查找 + 区间匹配** 定位当前字幕索引  
- 索引变化时回调 `SubtitleListWidget.set_highlight_index()`  
- 滚动使用 `scrollToItem(item, PositionAtCenter)` 使当前句处于 **可视区域垂直中央**

### 3. 点击字幕跳转（`ui/main_window.py`）

- 列表 `itemClicked` → `SubtitleSyncController.on_subtitle_clicked(index)`  
- 读取该条 `start_ms`，调用 `VlcPlayer.set_time_ms(start_ms)`  
- 若未在播放则自动 `play()`，便于立即对照

---

## 七、异常场景

| 场景 | 处理方式 |
|------|----------|
| 视频文件不存在/损坏 | 弹窗提示「视频加载失败」 |
| FFmpeg 未安装 | 提示安装并配置 PATH |
| 无内置字幕且 Whisper 失败 | 提示可能无音频或模型下载失败 |
| Whisper 识别结果为空 | 提示视频可能静音或无语音 |
| 字幕提取进行中重复点击 | 状态栏提示等待，不重复启动线程 |

---

## 八、常见问题

**Q: 提示找不到 libvlc？**  
A: 安装 64 位 VLC，并确保 Python 同为 64 位。

**Q: Whisper 很慢？**  
A: 换用 `tiny` 模型，或使用更短视频测试；有 NVIDIA 显卡会自动用 CUDA。

**Q: MKV 有字幕但没提取到？**  
A: 确认是 **软字幕**（独立轨道），图片型 PGS 字幕可能需要 OCR，本工具优先提取文本型轨道。

**Q: 高亮与画面不同步？**  
A: SRT 时间轴本身可能有偏移；可后期扩展全局时间偏移调节功能。

---

## License

MIT（可按需修改）
