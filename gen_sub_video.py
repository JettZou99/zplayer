"""
生成带字幕的测试视频
- 使用 ffmpeg flite 生成英文语音
- 创建对应的 SRT 字幕文件
- 将 SRT 嵌入视频作为软字幕轨道
- 最终视频可用于测试 ZPlayer 的字幕提取和 Whisper 识别
"""

import subprocess
import json
import sys
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
TEMP_DIR = PROJECT_DIR / "temp_sub_build"
TEMP_DIR.mkdir(exist_ok=True)

# 语音文本（英文，flite 仅支持英文）
SENTENCES = [
    "Hello everyone, welcome to this test video.",
    "This video is used for testing subtitle recognition.",
    "The ZPlayer application supports subtitle extraction.",
    "It also supports Whisper speech recognition.",
    "Thank you for watching this test video.",
]

GAP_SECONDS = 0.5  # 句子间隔（秒）
OUTPUT_VIDEO = PROJECT_DIR / "test_video_with_subs.mp4"


def run(cmd, check=True):
    """运行命令并返回结果"""
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def generate_speech_clips():
    """为每个句子生成独立的 WAV 音频文件"""
    clips = []
    for i, text in enumerate(SENTENCES):
        wav_path = TEMP_DIR / f"clip_{i:02d}.wav"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"flite=text='{text}'",
            "-ar", "44100", "-ac", "1",
            str(wav_path),
        ]
        run(cmd)
        duration = get_audio_duration(wav_path)
        clips.append({"index": i, "text": text, "path": wav_path, "duration": duration})
        print(f"  [{i}] {duration:.2f}s | {text}")
    return clips


def get_audio_duration(wav_path):
    """用 ffprobe 获取音频时长（秒）"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(wav_path)],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def build_srt(clips):
    """根据实际音频时长生成 SRT 字幕文件"""
    srt_path = TEMP_DIR / "subtitles.srt"
    current_time = 0.0
    lines = []

    for i, clip in enumerate(clips):
        start = current_time
        end = start + clip["duration"]
        lines.append(str(i + 1))
        lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        lines.append(clip["text"])
        lines.append("")
        current_time = end + GAP_SECONDS

    srt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"SRT created: {srt_path} ({len(clips)} entries)")
    return srt_path, current_time  # 返回 SRT 路径和总时长


def format_srt_time(seconds):
    """秒数 -> SRT 时间格式 HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    h = total_ms // 3_600_000
    total_ms %= 3_600_000
    m = total_ms // 60_000
    total_ms %= 60_000
    s = total_ms // 1_000
    ms = total_ms % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def concatenate_audio(clips, total_duration):
    """拼接音频片段（中间插入静音间隔）"""
    # 使用 concat filter
    inputs = []
    for clip in clips:
        inputs.extend(["-i", str(clip["path"])])
        # 在每个片段后添加静音间隔（最后一段除外）
        if clip["index"] < len(clips) - 1:
            silence_path = TEMP_DIR / f"silence_{clip['index']:02d}.wav"
            run([
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=channel_layout=mono:sample_rate=44100",
                "-t", str(GAP_SECONDS),
                "-c:a", "pcm_s16le",
                str(silence_path),
            ])
            inputs.extend(["-i", str(silence_path)])

    # concat
    filter_parts = ""
    n_inputs = len(clips) * 2 - 1  # clips + silences between them
    filter_parts = "".join(f"[{i}:a]" for i in range(n_inputs))
    filter_complex = f"{filter_parts}concat=n={n_inputs}:v=0:a=1[outa]"

    output_path = TEMP_DIR / "full_audio.wav"
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    run(cmd)

    actual_duration = get_audio_duration(output_path)
    print(f"Concatenated audio: {actual_duration:.2f}s")
    return output_path, actual_duration


def build_video(audio_path, srt_path, duration):
    """创建最终视频：SMPTE 彩条 + 语音音频 + 嵌入 SRT 字幕轨道"""
    # 多留 3 秒余量，避免 -shortest 截断最后一条字幕
    video_duration = int(duration) + 3

    cmd = [
        "ffmpeg", "-y",
        # 视频：SMPTE 彩条
        "-f", "lavfi",
        "-i", f"smptebars=duration={video_duration}:size=1920x1080:rate=30",
        # 音频
        "-i", str(audio_path),
        # 字幕
        "-i", str(srt_path),
        # 视频叠加文字
        "-vf", "drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
               "text='ZPlayer Subtitle Test':fontcolor=white:fontsize=56:"
               "box=1:boxcolor=black@0.6:x=(w-text_w)/2:y=30,"
               "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
               "text='Frame %{n}':fontcolor=yellow:fontsize=36:"
               "box=1:boxcolor=black@0.5:x=(w-text_w)/2:y=h-60",
        # 映射流
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-map", "2:s:0",
        # 视频编码
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        # 音频编码
        "-c:a", "aac", "-b:a", "128k",
        # 字幕编码（mov_text 用于 MP4 容器）
        "-c:s", "mov_text",
        # 元数据
        "-metadata:s:s:0", "language=eng",
        "-metadata:s:s:0", "title=English Subtitles",
        # 输出（不用 -shortest，避免截断最后一条字幕）
        "-t", str(video_duration),
        str(OUTPUT_VIDEO),
    ]

    print(f"Building video: {OUTPUT_VIDEO.name}")
    run(cmd)
    print(f"Video created: {OUTPUT_VIDEO}")


def verify_video():
    """用 ffprobe 验证视频包含字幕轨道"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(OUTPUT_VIDEO)],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])

    print(f"\n--- Video Info ---")
    print(f"File: {OUTPUT_VIDEO.name}")
    print(f"Size: {OUTPUT_VIDEO.stat().st_size / 1024:.0f} KB")

    for s in streams:
        codec_type = s.get("codec_type")
        codec_name = s.get("codec_name")
        if codec_type == "video":
            print(f"  Video: {codec_name} {s.get('width')}x{s.get('height')} "
                  f"@ {eval(s.get('r_frame_rate', '0/1')):.0f}fps")
        elif codec_type == "audio":
            print(f"  Audio: {codec_name} {s.get('sample_rate')}Hz "
                  f"{s.get('channels')}ch")
        elif codec_type == "subtitle":
            print(f"  Subtitle: {codec_name} (lang={s.get('tags', {}).get('language', 'N/A')})")


def eval(expr):
    """简单计算 a/b 格式的帧率"""
    if "/" in str(expr):
        a, b = str(expr).split("/")
        return float(a) / float(b)
    return float(expr)


def cleanup():
    """清理临时文件"""
    import shutil
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    # 也清理之前的 flite 测试文件
    test_wav = PROJECT_DIR / "temp_flite_test.wav"
    if test_wav.exists():
        test_wav.unlink()
    print(f"Temp files cleaned up")


def main():
    print("=== Step 1: Generate speech clips ===")
    clips = generate_speech_clips()

    print("\n=== Step 2: Build SRT subtitle file ===")
    srt_path, _ = build_srt(clips)

    print("\n=== Step 3: Concatenate audio ===")
    audio_path, total_duration = concatenate_audio(clips, 0)

    print("\n=== Step 4: Build final video ===")
    build_video(audio_path, srt_path, total_duration)

    print("\n=== Step 5: Verify ===")
    verify_video()

    print("\n=== Step 6: Cleanup ===")
    cleanup()

    print(f"\nDone! Output: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()
