#!/usr/bin/env python3
"""
有声书项目预检脚本
检查：
  1. 外部依赖（ffmpeg, ffprobe, node, npx, python3 + websockets）
  2. DashScope API Key 环境变量
  3. 项目目录结构
  4. project.json 合法性
  5. macOS SSL 证书

用法:
  python preflight.py --project-dir my-audiobook
  python preflight.py  # 仅检查依赖和环境
"""

import argparse
import json
import os
import shutil
import sys


def check_command(name: str) -> bool:
    """检查命令是否可用。"""
    return shutil.which(name) is not None


def check_env_var(name: str) -> bool:
    """检查环境变量是否设置。"""
    return bool(os.environ.get(name))


def check_project_dir(base: str) -> list[str]:
    """检查项目目录结构。"""
    issues = []
    required_dirs = ["audio/lines", "video"]
    required_files = ["project.json", "article.txt"]

    for d in required_dirs:
        path = os.path.join(base, d)
        if not os.path.isdir(path):
            issues.append(f"缺少目录: {d}（运行 mkdir -p {d}）")

    for f in required_files:
        path = os.path.join(base, f)
        if not os.path.exists(path):
            issues.append(f"缺少文件: {f}")

    return issues


def check_project_json(base: str) -> list[str]:
    """检查 project.json 合法性。"""
    path = os.path.join(base, "project.json")
    if not os.path.exists(path):
        return []

    issues = []
    try:
        with open(path) as f:
            proj = json.load(f)
    except json.JSONDecodeError as e:
        return [f"project.json 不是合法 JSON: {e}"]

    required = ["id", "name", "language", "tts_default"]
    for field in required:
        if field not in proj:
            issues.append(f"project.json 缺少字段: {field}")

    if "tts_default" in proj:
        tts = proj["tts_default"]
        if "voice" not in tts:
            issues.append("project.json.tts_default 缺少 voice")
        if "model" not in tts:
            issues.append("project.json.tts_default 缺少 model")

    return issues


def main():
    parser = argparse.ArgumentParser(description="有声书项目预检")
    parser.add_argument("--project-dir", help="项目目录（可选）")
    args = parser.parse_args()

    all_ok = True
    checks = []

    # 1. 外部依赖
    print("=== 依赖检查 ===")
    deps = [
        ("ffmpeg", "音频/视频处理"),
        ("ffprobe", "音频时长测量"),
        ("node", "hyperframes 渲染"),
        ("npx", "hyperframes CLI"),
        ("python3", "脚本运行"),
    ]
    for cmd, desc in deps:
        ok = check_command(cmd)
        status = "✓" if ok else "✗"
        print(f"  {status} {cmd} ({desc})")
        if not ok:
            all_ok = False
            checks.append(f"缺少命令: {cmd}")

    # Python websockets 库
    try:
        import websockets
        print(f"  ✓ websockets (Python TTS)")
    except ImportError:
        print(f"  ✗ websockets (Python TTS) — pip install websockets")
        all_ok = False
        checks.append("缺少 Python 包: websockets")

    # LLM 模式依赖（可选）
    print("\n=== LLM 模式依赖（可选，--llm 时需要）===")
    llm_deps = [
        ("openai", "LLM 调用（DashScope OpenAI 兼容）"),
        ("dashscope", "DashScope SDK"),
    ]
    for pkg, desc in llm_deps:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg} ({desc})")
        except ImportError:
            print(f"   {pkg} ({desc}) — pip install {pkg}")

    # 2. API Key
    print("\n=== 环境变量检查 ===")
    env_vars = [
        ("DASHSCOPE_API_KEY", "DashScope TTS"),
    ]
    for var, desc in env_vars:
        ok = check_env_var(var)
        status = "✓" if ok else "✗"
        print(f"  {status} {var} ({desc})")
        if not ok:
            all_ok = False
            checks.append(f"环境变量未设置: {var}")

    # 3. macOS SSL 提醒
    if sys.platform == "darwin":
        try:
            import certifi
            print(f"  ✓ certifi (SSL 证书) — {certifi.where()}")
        except ImportError:
            print(f"   certifi 未安装 — macOS 可能需要 SSL_CERT_FILE 环境变量")
            print(f"    解决: SSL_CERT_FILE=$(python3 -c 'import certifi; print(certifi.where())')")

    # 4. 项目目录（如果指定）
    if args.project_dir:
        print(f"\n=== 项目检查: {args.project_dir} ===")
        issues = check_project_dir(args.project_dir)
        issues += check_project_json(args.project_dir)
        for issue in issues:
            print(f"  ✗ {issue}")
            all_ok = False
        if not issues:
            print("  ✓ 项目结构正常")

    print()
    if all_ok:
        print("✓ 预检通过")
    else:
        print(f"✗ {len(checks)} 个问题需要修复:")
        for c in checks:
            print(f"  - {c}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
