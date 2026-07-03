#!/usr/bin/env python3
"""
测量 TTS 音频时长并回写到 script.json
用于 Step 5 完成后、Step 7 视频生成前的时间轴准备。

用法:
  python measure_durations.py --project-dir my-audiobook
  python measure_durations.py --script script.json --audio-dir audio/lines
"""

import argparse
import json
import os
import subprocess
import sys


def get_duration(path: str) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return -1.0
    return float(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="测量 TTS 音频时长并回写 script.json")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--script", default="script.json", help="script.json 路径")
    parser.add_argument("--audio-dir", default="audio/lines", help="TTS 音频目录")
    parser.add_argument("--output", help="输出路径（默认覆盖原文件）")
    args = parser.parse_args()

    if args.project_dir:
        base = args.project_dir
        if args.script == "script.json":
            args.script = os.path.join(base, "script.json")
        if args.audio_dir == "audio/lines":
            args.audio_dir = os.path.join(base, "audio", "lines")

    with open(args.script) as f:
        script = json.load(f)

    updated = 0
    missing = 0

    for section in script["sections"]:
        for line in section["lines"]:
            line_id = line.get("id", "")
            audio_path = os.path.join(args.audio_dir, f"{line_id}.mp3")

            if not os.path.exists(audio_path):
                missing += 1
                continue

            duration = get_duration(audio_path)
            if duration > 0:
                line["duration_ms"] = round(duration * 1000)
                updated += 1

    # 写回
    output = args.output or args.script
    with open(output, "w") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✓ 更新了 {updated} 行的 duration_ms")
    if missing > 0:
        print(f"  {missing} 行缺少音频文件（跳过）")
    print(f"  输出: {output}")


if __name__ == "__main__":
    main()
