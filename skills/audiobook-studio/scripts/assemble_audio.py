#!/usr/bin/env python3
"""
有声书音频装配脚本
读取 script.json + characters.json，自动完成音频装配：
  - 按 script.json 的行顺序拼接音频
  - 在行间插入 gap_after_ms 时长的静音
  - 按 section 合并为 section-N.mp3
  - 最终合并为 audio/final.mp3
  - 对 final.mp3 做 EBU R128 响度归一化 → final_normalized.mp3

用法:
  python assemble_audio.py --project-dir my-audiobook
  python assemble_audio.py --script script.json --chars characters.json --audio-dir audio/lines --output audio/final.mp3
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile


def run_ffmpeg(args: list[str], check=True):
    """运行 ffmpeg 命令。"""
    result = subprocess.run(
        ["ffmpeg", "-y"] + args,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"[ffmpeg ERROR] {' '.join(args)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def get_duration(path: str) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def generate_silence(duration_sec: float, output: str, sample_rate: int = 24000):
    """生成指定时长的静音 MP3。"""
    run_ffmpeg([
        "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(duration_sec),
        "-q:a", "9",
        output,
    ])


def assemble_section(lines: list[dict], audio_dir: str, output: str, sample_rate: int = 24000):
    """
    拼接一个 section 的所有行，行间插入静音 gap。
    lines: [{"id": "...", "gap_after_ms": 500}, ...]
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        list_path = f.name
        for line in lines:
            line_id = line["id"]
            line_path = os.path.join(audio_dir, f"{line_id}.mp3")
            if not os.path.exists(line_path):
                print(f"[WARN] 缺少音频文件: {line_path}", file=sys.stderr)
                continue
            f.write(f"file '{os.path.abspath(line_path)}'\n")

            # 生成并插入静音 gap
            gap_ms = line.get("gap_after_ms", 500)
            if gap_ms > 0:
                gap_path = os.path.join(os.path.dirname(list_path), f"_gap_{gap_ms}ms.mp3")
                if not os.path.exists(gap_path):
                    generate_silence(gap_ms / 1000.0, gap_path, sample_rate)
                f.write(f"file '{os.path.abspath(gap_path)}'\n")

    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output])
    os.unlink(list_path)
    dur = get_duration(output)
    print(f"✓ {output} ({dur:.1f}s)")


def assemble_all(section_outputs: list[str], final_output: str):
    """合并所有 section 为最终音频。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        list_path = f.name
        for path in section_outputs:
            f.write(f"file '{os.path.abspath(path)}'\n")

    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", final_output])
    os.unlink(list_path)
    dur = get_duration(final_output)
    print(f"✓ {final_output} ({dur:.1f}s, 总时长)")


def loudness_normalize(input_path: str, output_path: str, target_lufs: float = -23, 
                       true_peak: float = -2, lra: float = 7):
    """
    EBU R128 响度归一化。
    - I (integrated loudness): 整体响度，默认 -23 LUFS
    - TP (true peak): 真实峰值，默认 -2 dB
    - LRA (loudness range): 响度范围，默认 7 LU（压缩动态差异）
    """
    print(f"→ 响度归一化: I={target_lufs} LUFS, TP={true_peak} dB, LRA={lra} LU")
    
    # 第一步：分析
    result = subprocess.run(
        ["ffmpeg", "-i", input_path, 
         "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json",
         "-f", "null", "-"],
        capture_output=True,
        text=True
    )
    
    # 从 stderr 提取 JSON
    import re
    json_match = re.search(r'\{[^}]*"input_i"[^}]*\}', result.stderr, re.DOTALL)
    if not json_match:
        print("[WARN] 响度分析失败，跳过归一化", file=sys.stderr)
        return False
    
    measured = json.loads(json_match.group())
    print(f"  测量值: I={measured.get('input_i')} LUFS, TP={measured.get('input_tp')} dB, LRA={measured.get('input_lra')} LU")
    
    # 第二步：应用
    run_ffmpeg([
        "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}" +
               f":measured_I={measured['input_i']}" +
               f":measured_TP={measured['input_tp']}" +
               f":measured_LRA={measured['input_lra']}" +
               f":measured_thresh={measured['input_thresh']}" +
               f":offset={measured.get('target_offset', '0')}" +
               f":linear=true:print_format=summary",
        "-ar", "48000",
        output_path
    ])
    
    dur = get_duration(output_path)
    print(f"✓ {output_path} ({dur:.1f}s, 归一化版本)")
    return True


def main():
    parser = argparse.ArgumentParser(description="有声书音频装配")
    parser.add_argument("--project-dir", help="项目目录（自动查找 script.json / characters.json）")
    parser.add_argument("--script", default="script.json", help="script.json 路径")
    parser.add_argument("--chars", default="characters.json", help="characters.json 路径（校验用）")
    parser.add_argument("--audio-dir", default="audio/lines", help="TTS 音频文件目录")
    parser.add_argument("--output", default="audio/final.mp3", help="最终输出路径")
    parser.add_argument("--sample-rate", type=int, default=24000, help="采样率")
    parser.add_argument("--no-normalize", action="store_true", help="跳过响度归一化")
    args = parser.parse_args()

    # 如果指定了 project-dir，调整所有路径
    if args.project_dir:
        base = args.project_dir
        if args.script == "script.json":
            args.script = os.path.join(base, "script.json")
        if args.chars == "characters.json":
            args.chars = os.path.join(base, "characters.json")
        if args.audio_dir == "audio/lines":
            args.audio_dir = os.path.join(base, "audio", "lines")
        if args.output == "audio/final.mp3":
            args.output = os.path.join(base, "audio", "final.mp3")

    # 读取 script.json
    with open(args.script) as f:
        script = json.load(f)

    # 校验角色名一致性
    char_names = set()
    if os.path.exists(args.chars):
        with open(args.chars) as f:
            for c in json.load(f):
                char_names.add(c["name"])

    for section in script["sections"]:
        for line in section["lines"]:
            if char_names and line["character"] not in char_names:
                print(f"[WARN] 角色 '{line['character']}' 不在 characters.json 中 (行: {line['id']})")

    # 按 section 装配
    section_outputs = []
    for section in script["sections"]:
        lines = section["lines"]
        sec_num = section.get("order", 0) + 1
        sec_output = os.path.join(os.path.dirname(args.output), f"section-{sec_num}.mp3")
        assemble_section(lines, args.audio_dir, sec_output, args.sample_rate)
        section_outputs.append(sec_output)

    # 全剧合并
    if len(section_outputs) > 1:
        assemble_all(section_outputs, args.output)
    elif len(section_outputs) == 1:
        import shutil
        shutil.copy2(section_outputs[0], args.output)
        dur = get_duration(args.output)
        print(f"✓ {args.output} ({dur:.1f}s)")
    else:
        print("[ERROR] 没有 section 需要处理", file=sys.stderr)
        sys.exit(1)

    # 响度归一化
    if not args.no_normalize:
        normalized_output = args.output.replace(".mp3", "_normalized.mp3")
        loudness_normalize(args.output, normalized_output)
    else:
        print("→ 跳过响度归一化（--no-normalize）")


if __name__ == "__main__":
    main()
