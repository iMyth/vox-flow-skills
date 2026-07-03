#!/usr/bin/env python3
"""
有声书项目预检脚本
检查：
  1. 外部依赖（ffmpeg, node, npx, python3 + websockets）
  2. API Key 环境变量
  3. 项目目录结构
  4. project.json 合法性
  5. LLM endpoint 连通性（可选）

用法:
  python preflight.py --project-dir my-audiobook
  python preflight.py  # 仅检查依赖和环境
"""

import argparse
import json
import os
import shutil
import subprocess
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
    required_files = ["project.json", "outline.txt"]

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

    required = ["id", "name", "language", "llm", "tts_default"]
    for field in required:
        if field not in proj:
            issues.append(f"project.json 缺少字段: {field}")

    if "llm" in proj:
        llm = proj["llm"]
        if "endpoint" not in llm:
            issues.append("project.json.llm 缺少 endpoint")
        if "model" not in llm:
            issues.append("project.json.llm 缺少 model")

    if "tts_default" in proj:
        tts = proj["tts_default"]
        if "voice" not in tts:
            issues.append("project.json.tts_default 缺少 voice")

    return issues


def test_llm_endpoint(endpoint: str, api_key_env: str, model: str) -> bool:
    """测试 LLM endpoint 连通性。"""
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        print(f"  [SKIP] 环境变量 {api_key_env} 未设置，跳过 LLM 测试")
        return True

    try:
        import urllib.request
        import urllib.error
        import ssl

        # macOS: 使用 certifi 的 CA 证书
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = None

        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
        }).encode()

        req = urllib.request.Request(
            f"{endpoint}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        if resp.status == 200:
            return True
    except Exception as e:
        print(f"  [FAIL] LLM 连通性测试失败: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="有声书项目预检")
    parser.add_argument("--project-dir", help="项目目录（可选）")
    parser.add_argument("--skip-llm-test", action="store_true", help="跳过 LLM 连通性测试")
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

    # 2. API Key
    print("\n=== 环境变量检查 ===")
    env_vars = [
        ("DASHSCOPE_API_KEY", "DashScope TTS / LLM"),
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

        # 5. LLM 连通性
        if not args.skip_llm_test:
            proj_path = os.path.join(args.project_dir, "project.json")
            if os.path.exists(proj_path):
                with open(proj_path) as f:
                    proj = json.load(f)
                llm = proj.get("llm", {})
                endpoint = llm.get("endpoint", "")
                model = llm.get("model", "qwen-plus")
                api_key_env = llm.get("api_key_env", "DASHSCOPE_API_KEY")

                if endpoint:
                    print(f"\n=== LLM 连通性测试 ===")
                    print(f"  endpoint: {endpoint}")
                    print(f"  model: {model}")
                    ok = test_llm_endpoint(endpoint, api_key_env, model)
                    if ok:
                        print("  ✓ LLM 连通")
                    else:
                        all_ok = False

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
