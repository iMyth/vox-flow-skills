#!/usr/bin/env python3
"""
LLM 调用参考脚本（OpenAI 兼容端点）
用于 Step 2（大纲分析）和 Step 4（脚本生成）。

用法:
  python call_llm.py --endpoint "$LLM_ENDPOINT" --model qwen-plus --api-key-env DASHSCOPE_API_KEY \
      --system "..." --user "..." --output plan.json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


def call_llm(
    endpoint: str,
    model: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192,
) -> str:
    """调用 LLM 并返回完整响应文本。"""
    url = f"{endpoint}/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }).encode("utf-8")

    # 仅在 system prompt 提到 JSON 时才用 json_object 模式（qwen-plus 要求 prompt 含 "json"）
    if "json" in system_prompt.lower() or "JSON" in system_prompt:
        payload = json.loads(data)
        payload["response_format"] = {"type": "json_object"}
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    # macOS: 使用 certifi 的 CA 证书
    try:
        import certifi, ssl
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None

    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"[ERROR] HTTP {e.code}: {error_body[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] 连接失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # 提取响应文本
    choices = body.get("choices", [])
    if not choices:
        print(f"[ERROR] LLM 返回空响应: {json.dumps(body, ensure_ascii=False)[:500]}", file=sys.stderr)
        sys.exit(1)

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        print(f"[ERROR] LLM 返回空内容: {json.dumps(body, ensure_ascii=False)[:500]}", file=sys.stderr)
        sys.exit(1)

    return content.strip()


def parse_json_response(text: str) -> dict:
    """从 LLM 响应中提取 JSON（处理 markdown fence 等常见问题）。"""
    # 剥掉 markdown fence
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉第一行 ```json 和最后一行 ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description="LLM 调用（OpenAI 兼容端点）")
    parser.add_argument("--endpoint", required=True, help="LLM endpoint（不含 /chat/completions）")
    parser.add_argument("--model", default="qwen-plus", help="模型名")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY", help="API Key 环境变量名")
    parser.add_argument("--system", required=True, help="System prompt")
    parser.add_argument("--user", required=True, help="User prompt（或文件路径）")
    parser.add_argument("--output", help="输出文件路径（JSON）")
    parser.add_argument("--max-tokens", type=int, default=8192, help="max_tokens")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"[ERROR] 环境变量 {args.api_key_env} 未设置", file=sys.stderr)
        sys.exit(1)

    # 支持从文件读取 user prompt
    user_prompt = args.user
    if os.path.isfile(user_prompt):
        with open(user_prompt) as f:
            user_prompt = f.read().strip()

    print(f"调用 LLM: {args.endpoint} / {args.model}")
    response = call_llm(
        args.endpoint, args.model, api_key,
        args.system, user_prompt, args.max_tokens,
    )

    # 尝试解析 JSON
    try:
        parsed = parse_json_response(response)
        output_text = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        output_text = response
        print("[WARN] LLM 响应不是合法 JSON，输出原始文本", file=sys.stderr)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_text)
        print(f"✓ 输出 → {args.output}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
