# ZPlayer — 本地电影字幕同步对照工具

基于 **Python 3.10+ / PyQt6 / libVLC / FFmpeg** 的纯本地桌面应用。  
左侧播放视频，右侧展示完整字幕列表，支持实时高亮同步、自动滚动跟随、点击字幕跳转播放位置。  
内置单词翻译与收藏功能，看片学英语两不误。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 视频播放 | 支持 MP4 / MKV / AVI / MOV 等格式，播放、暂停、进度拖动、音量调节 |
| 软字幕提取 | MKV/MP4 内置字幕轨道 → FFmpeg 直接导出 SRT |
| 硬字幕/无轨识别 | 无内置字幕 → Whisper 离线 ASR 生成带毫秒时间戳的 SRT（可选） |
| 实时同步 | 监听播放进度，高亮当前字幕行，列表自动滚动居中 |
| 点击跳转 | 点击任意字幕行，视频 seek 到该句 `start_ms` |
| 单词翻译 | 点击字幕中的英文单词 → 有道词典 API 查询释义与音标 |
| 词形还原 | 智能识别复数、过去式、比较级等变形词，自动查询原型 |
| 单词收藏 | 收藏生词到本地词库（SQLite），关联字幕句子与视频来源 |
| 单词本管理 | 搜索、删除、导出 CSV，支持双击查看详情 |
| 深色主题 | 现代化暗色 UI，qtawesome 矢量图标，状态栏多指标实时显示 |
| 跨平台 | Windows / macOS / Linux 三平台字体与数据目录自动适配 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| GUI 框架 | PyQt6（含 QtSvg 矢量渲染） |
| 图标库 | qtawesome（Font Awesome 5 矢量图标） |
| 视频播放 | libVLC（python-vlc 绑定） |
| 字幕提取 | FFmpeg / FFprobe |
| 语音识别 | OpenAI Whisper（可选，独立安装） |
| 翻译服务 | 有道词典公开 JSON API（无需 API Key） |
| 数据存储 | SQLite（WAL 模式，线程安全） |
| 打包分发 | PyInstaller + GitHub Actions CI（macOS .dmg） |

---

## 环境要求

- **Python** 3.10 或以上
- **VLC 媒体播放器**（需安装完整版，提供 libvlc 动态库）
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

# macOS / Linux
source .venv/bin/activate
```

### 2. 安装 Python 依赖

```bash
# 核心依赖（不含 Whisper）
pip install -r requirements.txt
```

### 3. 安装 Whisper（可选）

Whisper + torch 体积约 2GB+，仅在需要**无内置字幕视频的语音识别**功能时安装。不安装也不影响 ZPlayer 其他功能正常使用。

```bash
pip install -r requirements-optional.txt
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

程序启动时会**自动探测** VLC 安装路径（注册表 / 常见目录 / Homebrew），通常无需手动配置。

### Windows

1. **必须先安装** [VLC 官方客户端 64 位](https://www.videolan.org/vlc/)（仅 pip 安装 `python-vlc` 不够，还需要系统里的 libvlc.dll）
2. 默认安装路径：`C:\Program Files\VideoLAN\VLC\`
3. 若 VLC 装在非标准位置，可设置环境变量：

```powershell
$env:ZPLAYER_VLC_PATH = "D:\Apps\VLC"
python main.py
```

4. 确保 **Python 与 VLC 同为 64 位**

### macOS

```bash
brew install --cask vlc
```

确认存在 `/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib`。

### Linux

```bash
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
   - **无字幕轨道** → Whisper 识别音频（需安装可选依赖；状态栏有进度提示）  
3. 右侧显示全部字幕；播放时当前句 **金色高亮** 并 **自动滚动到列表中间**  
4. **点击** 任意字幕行 → 左侧视频跳转到该句开始时间  
5. **点击/双击** 字幕行 → 下方翻译面板显示该行字幕原文，每个英文单词可点击  
6. **点击单词** → 有道词典查询释义与音标，显示在翻译面板  
7. 点击 **星标按钮** 收藏单词（关联字幕句子与视频来源）  
8. 工具栏 **「单词收藏」** 打开单词本对话框，可搜索、删除、导出 CSV  

也可手动点击工具栏 **「提取字幕」** 重新提取。

---

## 五、项目结构

```
zplayer/
├── main.py                        # 程序入口，初始化 QApplication 与主题
├── requirements.txt               # 核心依赖
├── requirements-optional.txt      # 可选依赖（Whisper + torch）
├── ZPlayer.spec                   # PyInstaller 打包配置（macOS .app）
├── README.md
│
├── player/
│   ├── vlc_player.py               # libVLC 播放器封装（播放/seek/毫秒进度）
│   └── vlc_setup.py               # libVLC 路径自动探测（Win/Mac/Linux）
│
├── subtitles/
│   ├── models.py                   # SubtitleEntry 数据模型
│   └── extractor.py                # FFmpeg 软字幕提取 + Whisper ASR + pysrt 解析
│
├── sync/
│   └── subtitle_sync.py            # 播放进度匹配、高亮、点击跳转逻辑
│
├── ui/
│   ├── main_window.py              # 主窗口、分割布局、模块整合
│   ├── video_panel.py              # 左侧视频区与播放控件（图标按钮）
│   ├── subtitle_list.py            # 右侧字幕列表（高亮/滚动/点击）
│   ├── translation_panel.py        # 翻译面板（常驻右侧底部）
│   ├── translation_worker.py       # 翻译后台线程（QThread）
│   ├── translator.py               # 有道词典 API + 词形还原 + 单词提取
│   ├── wordbook_dialog.py          # 单词本对话框（搜索/删除/导出）
│   ├── workers.py                  # 字幕提取后台线程
│   └── theme.py                    # 暗色主题（QSS 样式 + 图标 + 状态栏组件）
│
├── data/
│   ├── models.py                   # CollectedWord 收藏单词数据模型
│   └── wordbook_db.py              # SQLite 数据库层（CRUD + CSV 导出）
│
├── utils/
│   └── platforms.py                 # 跨平台工具（字体名、数据目录、DB 路径）
│
├── scripts/
│   └── generate_icon.py            # 应用图标生成（qtawesome → PNG → .icns）
│
└── .github/
    └── workflows/
        └── build-macos.yml         # GitHub Actions CI（macOS .dmg 自动构建）
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

### 4. 单词翻译流程（`ui/translator.py` + `ui/translation_panel.py`）

```
用户点击字幕中的单词
    │
    ├─ normalize_query_word() — 去标点 + 转小写
    │
    ├─ lemmatize() — 词形还原
    │     ├─ 不规则动词/名词/形容词映射表
    │     ├─ -ies → -y, -ied → -y
    │     ├─ -es → 原型, -s → 原型
    │     ├─ -ing → 原型（处理双写辅音、去 e 加 ing）
    │     ├─ -ed → 原型
    │     ├─ -er / -est → 原型
    │     └─ 查询原型词获得更准确的词典结果
    │
    ├─ YoudaoTranslator.translate() — 有道词典 API
    │     ├─ 类级内存缓存（最多 500 条，避免重复请求）
    │     ├─ 5 秒超时
    │     └─ 防御式 JSON 解析（多路径容错）
    │
    └─ TranslationPanel.show_translation()
          ├─ 单词标题 + 音标（美/英）
          ├─ 释义列表（词性 + 释义）
          └─ 字幕原文区域保留可点击单词
```

### 5. 单词收藏（`data/wordbook_db.py` + `data/models.py`）

- `CollectedWord` 数据模型关联翻译结果、字幕原句、时间轴、视频来源  
- `WordBookDB` 使用 SQLite WAL 模式，线程安全（`threading.Lock` + 每次操作创建新连接）  
- 写入策略：`INSERT OR REPLACE`（同单词重复收藏时更新最新上下文）  
- 支持模糊搜索、按 ID 删除、批量删除  
- CSV 导出包含 UTF-8 BOM（Excel 兼容）

---

## 七、UI 主题系统

### 暗色配色方案（`ui/theme.py`）

- **6 级背景层次**：BG_BASE → BG_SURFACE → BG_ELEVATED → BG_ALTERNATE → BG_INPUT → BG_HOVER
- **强调色**：蓝色系 `#4a9eff`（主交互）/ 琥珀色 `#ffd966`（字幕高亮）
- **全局 QSS**：覆盖所有控件（工具栏、按钮、滑块、列表、表格、滚动条等）
- **跨平台字体**：Windows 用 Microsoft YaHei UI / macOS 用 PingFang SC / Linux 用 Noto Sans CJK SC

### 状态栏组件（`StatusBarItem`）

状态栏右侧 4 个永久组件，实时显示：

| 组件 | 图标 | 内容 |
|------|------|------|
| 播放状态 | play-circle / pause-circle | 当前时间 / 总时长 |
| 字幕计数 | closed-captioning | 已加载字幕条数 |
| 收藏计数 | bookmark | 已收藏单词数 |
| 音量 | volume-up / volume-mute | 当前音量百分比 |

---

## 八、异常场景

| 场景 | 处理方式 |
|------|----------|
| 视频文件不存在/损坏 | 弹窗提示「视频加载失败」 |
| FFmpeg 未安装 | 提示安装并配置 PATH |
| libVLC 未找到 | 弹窗提示安装 VLC 及环境变量配置方法 |
| 无内置字幕且 Whisper 未安装 | 提示安装可选依赖 `pip install -r requirements-optional.txt` |
| 无内置字幕且 Whisper 失败 | 提示可能无音频或模型下载失败 |
| Whisper 识别结果为空 | 提示视频可能静音或无语音 |
| 字幕提取进行中重复点击 | 状态栏提示等待，不重复启动线程 |
| 翻译网络请求失败 | 翻译面板显示错误信息 |
| 翻译结果为空 | 提示「未找到该单词的翻译结果」 |

---

## 九、常见问题

**Q: 提示找不到 libvlc？**  
A: 安装 64 位 VLC，并确保 Python 同为 64 位。程序会自动探测常见安装路径。

**Q: Whisper 很慢？**  
A: 换用 `tiny` 模型，或使用更短视频测试；有 NVIDIA 显卡会自动用 CUDA。

**Q: MKV 有字幕但没提取到？**  
A: 确认是 **软字幕**（独立轨道），图片型 PGS 字幕可能需要 OCR，本工具优先提取文本型轨道。

**Q: 高亮与画面不同步？**  
A: SRT 时间轴本身可能有偏移；可后期扩展全局时间偏移调节功能。

**Q: 翻译查不到某些词？**  
A: 词形还原可能不完全准确（如专业术语），程序会先尝试还原再查询原型。

**Q: 收藏的单词存在哪里？**  
A: SQLite 数据库，路径为：
- Windows: `~/.zplayer/wordbook.db`
- macOS: `~/Library/Application Support/ZPlayer/wordbook.db`

---

## 十、macOS 打包（.dmg）

### 自动构建（GitHub Actions）

推送 `v*` 标签时自动触发 CI 构建：

```bash
git tag v1.0.0
git push origin v1.0.0
```

CI 流程：
1. macOS runner 安装 VLC + FFmpeg + Python 依赖
2. 生成 .icns 应用图标
3. PyInstaller 打包为 .app bundle
4. 临时签名（ad-hoc codesign）
5. 生成 .dmg 安装镜像
6. 上传为 GitHub Release 资产

也可在 GitHub 仓库 **Actions** 页面手动触发构建（指定分支/tag）。

### 手动构建

```bash
# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 生成图标
python scripts/generate_icon.py --output ZPlayer.icns

# 打包
pyinstaller ZPlayer.spec --noconfirm

# 生成 .dmg
hdiutil create -volname "ZPlayer" \
  -srcfolder dist/ZPlayer.app \
  -ov -format UDZO ZPlayer.dmg
```

> **注意**：打包不含 Whisper / torch（体积过大），用户如需语音识别功能请在目标机器另行安装。  
> VLC 和 FFmpeg 不打包进 .dmg，需用户预装。

---

## License

MIT
