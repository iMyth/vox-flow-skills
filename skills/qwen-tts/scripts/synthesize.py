#!/usr/bin/env python3
"""
Qwen-TTS Realtime 语音合成脚本
用法:
  python synthesize.py --text "你好" --voice Cherry --output out.mp3
  python synthesize.py --text "你好" --voice Cherry --output out.mp3 --instructions "温柔地"
  python synthesize.py --file script.json --output-dir audio/lines
"""

import asyncio
import argparse
import base64
import json
import os
import ssl
import sys

import websockets

API_KEY_ENV = "DASHSCOPE_API_KEY"
MODEL = "qwen3-tts-instruct-flash-realtime"
ENDPOINT = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}"


def get_ssl_context():
    """创建 SSL 上下文，macOS 上使用 certifi 的 CA 证书。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


async def synthesize(
    texts: list[str],
    output: str,
    voice: str = "Cherry",
    instructions: str = "",
    model: str = MODEL,
):
    """通过 WebSocket 合成语音，base64 拼完再写文件。"""
    url = ENDPOINT.format(model=model)
    headers = {"Authorization": f"Bearer {os.environ[API_KEY_ENV]}"}

    async with websockets.connect(url, additional_headers=headers, ssl=get_ssl_context()) as ws:
        # session.update
        session = {
            "mode": "server_commit",
            "voice": voice,
            "response_format": "mp3",
            "sample_rate": 24000,
        }
        if instructions:
            session["instructions"] = instructions
            session["optimize_instructions"] = True

        await ws.send(json.dumps({"type": "session.update", "session": session}))

        # Drain handshake: expect exactly session.created then session.updated
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                if data["type"] in ("session.created", "session.updated"):
                    continue  # 握手消息，继续等下一条
                # 收到非握手消息（不应该发生），退出
                break
            except asyncio.TimeoutError:
                break  # 超时说明握手完成，服务端在等我们发文本

        # 发送文本（多段放同一 session 保韵律）
        # 注意：发送前加小延迟，避免服务端处理握手消息时来不及接收文本
        await asyncio.sleep(0.3)
        for t in texts:
            await ws.send(json.dumps({"type": "input_text_buffer.append", "text": t}))
        await asyncio.sleep(0.2)
        await ws.send(json.dumps({"type": "session.finish"}))

        # 收集音频
        audio = bytearray()
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)
            data = json.loads(msg)
            if data["type"] == "response.audio.delta":
                audio.extend(base64.b64decode(data["delta"]))
            elif data["type"] == "session.finished":
                break
            elif data["type"] == "error":
                print(f"[ERROR] {data.get('error', {}).get('message', 'unknown')}", file=sys.stderr)
                return False

    with open(output, "wb") as f:
        f.write(audio)
    print(f"✓ {output} ({len(audio)} bytes)")
    return True


async def synthesize_from_script(script_path: str, output_dir: str, chars_path: str = ""):
    """从 script.json 逐行合成，自动查 characters.json 获取 voice/instructions。"""
    with open(script_path) as f:
        script = json.load(f)

    characters = {}
    if chars_path and os.path.exists(chars_path):
        with open(chars_path) as f:
            for c in json.load(f):
                characters[c["name"]] = c

    os.makedirs(output_dir, exist_ok=True)

    total = sum(len(s["lines"]) for s in script["sections"])
    done = 0

    for section in script["sections"]:
        for line in section["lines"]:
            char_name = line["character"]
            char = characters.get(char_name, {})
            voice = char.get("voice", "Cherry")
            model = char.get("model", MODEL)
            instructions = line.get("instructions", "")
            text = line["text"]

            # 超长文本按标点切段，多段放同一 session
            if len(text) > 200:
                segments = split_by_punctuation(text)
            else:
                segments = [text]

            # Derive section ID: use 'id' field if present, otherwise use order index
            sec_id = section.get("id", f"sec_{script['sections'].index(section)+1}")
            line_id = line.get("id", f"{sec_id}_line_{section['lines'].index(line)+1}")
            output = os.path.join(output_dir, f"{line_id}.mp3")

            ok = False
            for attempt in range(3):
                ok = await synthesize(segments, output, voice, instructions, model)
                if ok:
                    break
                await asyncio.sleep(2 ** attempt)

            if not ok:
                failed_path = output + ".failed"
                with open(failed_path, "w") as f:
                    f.write(json.dumps({"line_id": line_id, "text": text, "voice": voice}))
                print(f"✗ {line_id} FAILED after 3 retries → {failed_path}")

            done += 1
            if done % max(1, total // 10) == 0:
                print(f"进度: {done}/{total} ({100*done//total}%)")


def split_by_punctuation(text: str) -> list[str]:
    """按标点切段，不超过 200 字。"""
    result = []
    current = ""
    for ch in text:
        current += ch
        if ch in "。！？；\n" and len(current) >= 50:
            result.append(current.strip())
            current = ""
    if current.strip():
        result.append(current.strip())
    return result


def main():
    parser = argparse.ArgumentParser(description="Qwen-TTS Realtime 语音合成")
    parser.add_argument("--text", help="要合成的文本（单次合成用）")
    parser.add_argument("--voice", default="Cherry", help="音色 ID（默认 Cherry）")
    parser.add_argument("--model", default=MODEL, help="TTS 模型")
    parser.add_argument("--instructions", default="", help="情感/风格指令")
    parser.add_argument("--output", help="输出文件路径（单次合成用）")
    parser.add_argument("--file", help="script.json 路径（批量合成用）")
    parser.add_argument("--output-dir", default="audio/lines", help="批量合成输出目录")
    parser.add_argument("--chars", default="characters.json", help="characters.json 路径")
    args = parser.parse_args()

    if not os.environ.get(API_KEY_ENV):
        print(f"错误: 环境变量 {API_KEY_ENV} 未设置", file=sys.stderr)
        sys.exit(1)

    if args.file:
        asyncio.run(synthesize_from_script(args.file, args.output_dir, args.chars))
    elif args.text and args.output:
        ok = asyncio.run(synthesize([args.text], args.output, args.voice, args.instructions, args.model))
        if not ok:
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
