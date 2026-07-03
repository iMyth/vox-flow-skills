---
name: qwen-tts
description: 用阿里云百炼 Qwen-TTS-Realtime WebSocket API 合成语音。流式传输、支持 instruction 情感控制、多段文本连贯韵律。当用户需要文本转语音、配音、旁白生成、TTS，或提到 DashScope、阿里云百炼、Qwen TTS 时触发。
license: MIT
compatibility: Requires a DashScope API key (https://dashscope.console.aliyun.com/) and network access to aliyuncs.com endpoints.
metadata:
  author: imyth
  version: "2.0"
  repository: "github.com/imyth/vox-flow-skills"
---

# Qwen-TTS Realtime（WebSocket API）

用 Qwen-TTS 系列模型把文本合成语音。WebSocket 流式传输，支持 instruction 情感控制，多段文本在同一 session 内保持连贯韵律。

## 鉴权

Bearer token，从 https://dashscope.console.aliyun.com/ 申请 API Key。

```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxx"
```

---

## WebSocket 协议

### Endpoint

```
wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}
```

| 模型 | instruction | 推荐场景 |
|------|------------|---------|
| `qwen3-tts-instruct-flash-realtime` | ✅ | **默认推荐**，情感/风格可控 |
| `qwen3-tts-flash-realtime` | ❌ | 基础 TTS，更快更便宜 |

### 握手 Headers

```
Authorization: Bearer $DASHSCOPE_API_KEY
```

### 协议流程

```
客户端                              服务端
  ─── session.update ─────────────►
  ◄── session.created ─────────────
  ◄── session.updated ─────────────
  ─── input_text_buffer.append ────►  (可发多次)
  ─── input_text_buffer.append ────►
  ─── session.finish ──────────────►
  ◄── response.created ────────────
  ◄── response.audio.delta ────────  (base64, 多次)
  ◄── response.audio.delta ────────
  ◄── response.audio.done ─────────
  ◄── response.done ───────────────
  ◄── session.finished ────────────
```

**关键**：音频在 `response.audio.delta` 里，base64 编码。收到 `session.finished` 表示全部完成。

---

### `session.update`（配置 session）

```json
{
  "type": "session.update",
  "session": {
    "mode": "server_commit",
    "voice": "Cherry",
    "response_format": "mp3",
    "sample_rate": 24000,
    "instructions": "温柔地，像讲睡前故事",
    "optimize_instructions": true
  }
}
```

| 字段 | 默认 | 说明 |
|------|------|------|
| `mode` | `"server_commit"` | `server_commit`（服务端自动判断合成时机）/ `commit`（需手动 `input_text_buffer.commit`） |
| `voice` | 必填 | 音色 ID（见 [references/voices.md](references/voices.md)） |
| `response_format` | `"pcm"` | `pcm` / `mp3` / `wav` |
| `sample_rate` | `24000` | `8000` / `16000` / `24000` / `48000` |
| `instructions` | - | 情感/风格指令（仅 instruct 模型，≤ 1600 token，中英文） |
| `optimize_instructions` | `false` | 让模型优化指令措辞，建议 `true` |
| `language_type` | `"Auto"` | `Auto` / `Chinese` / `English` / `Japanese` 等 |

---

### `input_text_buffer.append`（发文本）

```json
{
  "type": "input_text_buffer.append",
  "text": "你好，欢迎使用 Qwen TTS。"
}
```

- 多段文本分多次发送，**同一 session 内保持连贯韵律**
- `server_commit` 模式下服务端自动判断合成时机

---

### `session.finish`（结束）

```json
{ "type": "session.finish" }
```

---

### 收音频

监听 `response.audio.delta` 事件，把 `delta` 字段的 base64 解码后拼起来：

```json
{ "type": "response.audio.delta", "delta": "base64-encoded-audio..." }
```

收到 `session.finished` 表示合成全部完成。

---

## Python 完整示例

```python
import asyncio, base64, json, os, websockets

API_KEY = os.environ["DASHSCOPE_API_KEY"]
MODEL = "qwen3-tts-instruct-flash-realtime"
VOICE = "Cherry"

async def synthesize(texts: list[str], output: str, instructions: str = ""):
    url = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={MODEL}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with websockets.connect(url, additional_headers=headers) as ws:
        # session.update
        session = {
            "mode": "server_commit",
            "voice": VOICE,
            "response_format": "mp3",
            "sample_rate": 24000,
        }
        if instructions:
            session["instructions"] = instructions
            session["optimize_instructions"] = True
        await ws.send(json.dumps({"type": "session.update", "session": session}))
        await ws.recv()  # session.created

        # send texts
        for t in texts:
            await ws.send(json.dumps({"type": "input_text_buffer.append", "text": t}))
        await ws.send(json.dumps({"type": "session.finish"}))

        # collect audio
        audio = bytearray()
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)
            data = json.loads(msg)
            if data["type"] == "response.audio.delta":
                audio.extend(base64.b64decode(data["delta"]))
            elif data["type"] == "session.finished":
                break

    with open(output, "wb") as f:
        f.write(audio)
    print(f"✓ {output} ({len(audio)} bytes)")

asyncio.run(synthesize(
    ["第一段。你好，这是 Qwen TTS。", "第二段。多段文本连贯合成。"],
    "out.mp3",
    "温柔地"
))
```

---

## 模型与音色

- **模型** → [references/models.md](references/models.md)
- **音色** → [references/voices.md](references/voices.md)

---

## 关键约束

1. **instruction**：仅 `qwen3-tts-instruct-flash-realtime` 支持，≤ 1600 token，中英文
2. **单 session 单音色**：同一 session 内无法切换 voice，多角色需开多个 session
3. **`optimize_instructions: true`**：建议开启，让模型自动优化指令措辞
4. **base64 拼完再写文件**：不要边收边写，失败时文件会损坏
5. **长度**：单段文本建议 ≤ 200 中文字符，超过按标点切段

---

## 错误处理

服务端返回 `error` 事件：

```json
{ "type": "error", "error": {"code": "...", "message": "..."}}
```

| HTTP Status | 常见原因 |
|-------------|----------|
| 401 | API Key 错误或过期 |
| 400 | 字段拼错、模型不支持 instructions |
| 429 | QPS 超限，等 1s 重试 |

---

## 给 Claude 的代码生成原则

- **用 `websockets`（Python）或 `ws`（Node）**：成熟库，不要自己实现握手
- **永远 retry 3 次**：网络偶尔失败，加指数退避
- **base64 拼完再写文件**：收到 `response.audio.delta` 就 `extend`，等 `session.finished` 再写
- **macOS Python SSL**：可能需要 `SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")`
