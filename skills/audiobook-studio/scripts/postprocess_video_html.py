#!/usr/bin/env python3
"""
视频 HTML 后处理 Safety-Net（5 步）
实现 audiobook-video.md 中定义的后处理步骤：
  1. data-duration 强制修正
  2. window.__hf.duration 强制覆盖
  3. Font 清洗
  4. Clip timing 校准
  5. Overflow clip 截断

用法:
  python postprocess_video_html.py --html video/section-1.html --audio audio/section-1.mp3
  python postprocess_video_html.py --html video/section-1.html --duration 11.632
"""

import argparse
import os
import re
import subprocess
import sys


def get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 获取音频时长。"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[ERROR] ffprobe 失败: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return float(result.stdout.strip())


def step1_fix_data_duration(html: str, duration: float) -> str:
    """修正根元素的 data-duration 属性。"""
    # 只修改根元素（body）上的 data-duration，不碰 CSS 选择器中的
    pattern = r'(<body[^>]*data-composition-id="ai-generated"[^>]*)data-duration="[^"]*"'
    replacement = rf'\1data-duration="{duration}"'

    # 也处理 data-composition-id 在 data-duration 后面的情况
    pattern2 = r'(<body[^>]*?)data-duration="[^"]*"'
    if re.search(r'data-composition-id="ai-generated"', html):
        # 找到 body 标签，替换其中的 data-duration
        def replacer(m):
            tag = m.group(0)
            if 'data-composition-id="ai-generated"' in tag:
                return re.sub(r'data-duration="[^"]*"', f'data-duration="{duration}"', tag)
            return tag
        html = re.sub(r'<body[^>]*>', replacer, html, count=1)

    return html


def step2_inject_safety_net(html: str, duration: float) -> str:
    """注入 window.__hf safety-net script。"""
    script = f"""
  <script>
  (function() {{
    var DURATION = {duration};
    window.__timelines = window.__timelines || {{}};
    if (!window.__timelines['ai-generated']) {{
      if (typeof gsap !== 'undefined') {{
        window.__timelines['ai-generated'] = gsap.timeline({{ paused: true }});
      }} else {{
        window.__timelines['ai-generated'] = {{ seek: function() {{}}, duration: function() {{ return DURATION; }} }};
      }}
    }}
    window.__hf = window.__hf || {{}};
    window.__hf.duration = DURATION;
    if (!window.__hf.seek) {{
      window.__hf.seek = function(time) {{
        if (window.__timelines) {{
          Object.values(window.__timelines).forEach(function(tl) {{
            if (tl && typeof tl.seek === 'function') tl.seek(time);
          }});
        }}
      }};
    }}
  }})();
  </script>
"""
    # 注入位置：body 结束前 > html 结束前 > 末尾
    if "</body>" in html:
        html = html.replace("</body>", script + "</body>")
    elif "</html>" in html:
        html = html.replace("</html>", script + "</html>")
    else:
        html += script
    return html


def step3_font_cleaning(html: str) -> str:
    """清洗字体：替换 var(--font-*) 和剥离 @font-face。"""
    # 剥离 @font-face 块
    html = re.sub(r'@font-face\s*\{[^}]*\}', '', html)

    # 替换 CSS 变量字体为通用字体
    html = re.sub(r"var\(--font-[^)]+\)", "sans-serif", html)

    # 替换不在 hyperframes registry 中的字体名为通用字体
    # 保留常见安全字体
    safe_fonts = {
        'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy',
        'system-ui', '-apple-system', 'BlinkMacSystemFont',
        'Noto Sans SC', 'Noto Serif SC', 'Noto Sans JP',
        'DM Sans', 'DM Serif Display', 'Space Grotesk',
        'Inter', 'Roboto', 'Arial', 'Helvetica',
    }
    # 简单策略：如果 font-family 包含不常见的字体名，替换为 sans-serif
    # 这个步骤比较激进，推荐做法是直接用 generic family

    return html


def step4_clip_timing校准(html: str, duration: float) -> str:
    """校准 clip 的 data-start 和 data-duration。"""
    # 找到所有 clip 元素
    def fix_clip(m):
        tag = m.group(0)
        start_match = re.search(r'data-start="([^"]*)"', tag)
        dur_match = re.search(r'data-duration="([^"]*)"', tag)

        if not start_match or not dur_match:
            return tag

        try:
            start = float(start_match.group(1))
            dur = float(dur_match.group(1))
        except ValueError:
            return tag

        # 修正：start + duration 不能超过总时长
        if start + dur > duration + 0.05:  # 50ms epsilon
            new_dur = max(0, duration - start)
            tag = tag.replace(dur_match.group(0), f'data-duration="{new_dur}"')

        return tag

    html = re.sub(r'<[a-z][^>]*class="[^"]*clip[^"]*"[^>]*>', fix_clip, html)
    return html


def step5_overflow_clip截断(html: str, duration: float) -> str:
    """截断超出总时长的 clip。"""
    def fix_overflow(m):
        tag = m.group(0)
        start_match = re.search(r'data-start="([^"]*)"', tag)
        dur_match = re.search(r'data-duration="([^"]*)"', tag)

        if not start_match or not dur_match:
            return tag

        try:
            start = float(start_match.group(1))
            dur = float(dur_match.group(1))
        except ValueError:
            return tag

        if start + dur > duration + 0.05:
            new_dur = max(0.1, duration - start)
            tag = tag.replace(dur_match.group(0), f'data-duration="{new_dur}"')

        return tag

    # 匹配所有带 data-start 和 data-duration 的元素
    html = re.sub(r'<[a-z][^>]*data-start="[^"]*"[^>]*data-duration="[^"]*"[^>]*>', fix_overflow, html)
    return html


def postprocess(html_path: str, duration: float = None, audio_path: str = None) -> str:
    """执行全部 5 步后处理，返回修正后的 HTML。"""
    with open(html_path) as f:
        html = f.read()

    # 获取时长
    if duration is None:
        if audio_path and os.path.exists(audio_path):
            duration = get_audio_duration(audio_path)
            print(f"  音频时长: {duration:.3f}s")
        else:
            # 从 HTML 的 data-duration 读取
            m = re.search(r'data-duration="([^"]*)"', html)
            if m:
                duration = float(m.group(1))
                print(f"  HTML 标注时长: {duration:.3f}s")
            else:
                print("[ERROR] 无法确定时长，请通过 --duration 或 --audio 指定", file=sys.stderr)
                sys.exit(1)

    print(f"  [1/5] 修正 data-duration → {duration}")
    html = step1_fix_data_duration(html, duration)

    print(f"  [2/5] 注入 safety-net script (duration={duration})")
    html = step2_inject_safety_net(html, duration)

    print("  [3/5] Font 清洗")
    html = step3_font_cleaning(html)

    print(f"  [4/5] Clip timing 校准 (max={duration})")
    html = step4_clip_timing校准(html, duration)

    print(f"  [5/5] Overflow clip 截断 (max={duration})")
    html = step5_overflow_clip截断(html, duration)

    # 写回
    with open(html_path, "w") as f:
        f.write(html)

    print(f"✓ 后处理完成: {html_path}")
    return html


def main():
    parser = argparse.ArgumentParser(description="视频 HTML 后处理 Safety-Net")
    parser.add_argument("--html", required=True, help="HTML 文件路径")
    parser.add_argument("--audio", help="对应音频文件路径（用于获取真实时长）")
    parser.add_argument("--duration", type=float, help="手动指定时长（秒）")
    args = parser.parse_args()

    if not os.path.exists(args.html):
        print(f"[ERROR] HTML 文件不存在: {args.html}", file=sys.stderr)
        sys.exit(1)

    postprocess(args.html, args.duration, args.audio)


if __name__ == "__main__":
    main()
