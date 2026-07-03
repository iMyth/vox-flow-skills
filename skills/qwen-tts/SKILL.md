---
name: qwen-tts
description: 用阿里云百炼（DashScope）Qwen TTS 合成语音。两种接入方式——HTTP REST（简单一次性合成）和 WebSocket Realtime（流式、多段文本、音色更连贯）。覆盖 qwen3-tts-flash / qwen3-tts-instruct-flash / qwen3-tts-vc 三类模型。当用户需要文本转语音、配音、旁白生成、voice clone、TTS，或提到 DashScope、阿里云百炼、Qwen TTS 时触发。
license: MIT
compatibility: Requires a DashScope API key (https://dashscope.console.aliyun.com/) and network access to aliyuncs.com endpoints.
metadata:
  author: imyth
  version: "1.0"
  repository: "github.com/imyth/vox-flow-skills"
---

# Qwen TTS（阿里云百炼 DashScope）

用 Qwen 系列 TTS 模型把文本合成语音。两种接入方式，按场景选：

| 接入 | 适用 | 特点 |
|------|------|------|
| **HTTP REST** | 短文本、一次性合成、脚本快速调用 | 简单，拿 URL 下载即可 |
| **WebSocket Realtime** | 长文本分段、多段拼接、需要连贯韵律 | 流式、低延迟、支持 instructions、音色更自然 |

**推荐默认**：WebSocket Realtime + `qwen3-tts-instruct-flash-realtime` 模型，支持情感指令，质量最高。

## 鉴权

所有请求都走 Bearer token。从 https://dashscope.console.aliyun.com/ 申请 API Key。

```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxx"
```

---

## HTTP REST API

### Endpoint

```
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

### 请求

```http
Content-Type: application/json
Authorization: Bearer $DASHSCOPE_API_KEY
```

```json
{
  "model": "qwen-tts",
  "input": {
    "text": "你好，欢迎使用 Qwen TTS。",
    "voice": "Cherry",
    "instructions": "温柔地、缓慢地",
    "optimize_instructions": true
  }
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `model` | 是 | 模型 ID（见 [references/models.md](references/models.md)） |
| `input.text` | 是 | 待合成文本，≤ 200 中文字符 / 600 UTF-8 字节 |
| `input.voice` | 是 | 音色 ID（见 [references/voices.md](references/voices.md)） |
| `input.instructions` | 否 | 情感/风格指令（仅 instruct 模型支持） |
| `input.optimize_instructions` | 否 | 是否让模型优化指令措辞，建议 `true` |

### 响应

```json
{
  "output": {
    "audio": {
      "url": "http://dashscope-audio.oss-cn-xxx/xxx.wav"
    }
  },
  "usage": { "characters": 15 }
}
```

**注意**：返回的 URL 是 `http://`，生产环境请换成 `https://` 再下载。

### curl 示例

```bash
curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -d '{
    "model": "qwen-tts",
    "input": {
      "text": "你好，世界。",
      "voice": "Cherry"
    }
  }' \
  | jq -r '.output.audio.url' \
  | sed 's|^http://|https://|' \
  | xargs curl -o output.wav
```

---

## WebSocket Realtime API

### Endpoint

```
wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}
```

### 握手 Headers

```
Authorization: bearer $DASHSCOPE_API_KEY
X-DashScope-DataInspection: enable
Host: dashscope.aliyuncs.com
```

### 协议流程

```
客户端                           服务端
  ─── session.update ─────────►
  ◄── session.created ─────────
  ─── input_text_buffer.append ─►  (可发多次)
  ─── input_text_buffer.append ─►
  ─── session.finish ──────────►
  ◄── audio.delta ─────────────  (base64, 多次)
  ◄── audio.delta ─────────────
  ◄── audio.completed ─────────
```

### `session.update`

```json
{
  "type": "session.update",
  "session": {
    "mode": "server_commit",
    "model": "qwen3-tts-instruct-flash-realtime",
    "voice": "Cherry",
    "response_format": "mp3",
    "sample_rate": 24000,
    "instructions": "温柔地"
  }
}
```

| 字段 | 说明 |
|------|------|
| `mode` | 固定 `"server_commit"` |
| `model` | 模型 ID |
| `voice` | 音色 ID |
| `response_format` | `"mp3"` 或 `"wav"` |
| `sample_rate` | `24000`（推荐） |
| `instructions` | 情感指令（VC 模型不支持） |

### `input_text_buffer.append`

```json
{ "type": "input_text_buffer.append", "text": "第一段文本。" }
```

多段文本分多次发送，**同一 session 内能保持连贯韵律**——这是 WS 比 HTTP 好的地方。

### `session.finish`

```json
{ "type": "session.finish" }
```

告诉服务端"文本发完了"。

### 收 `audio.delta`

```json
{ "type": "audio.delta", "delta": "base64-encoded-audio-chunk..." }
```

把每个 `delta` 的 base64 解码后拼起来，就是完整音频文件。

### Python 完整示例

```python
import asyncio, base64, json, os, websockets

API_KEY = os.environ["DASHSCOPE_API_KEY"]
MODEL = "qwen3-tts-instruct-flash-realtime"
VOICE = "Cherry"

async def synthesize(texts: list[str], output: str):
    url = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={MODEL}"
    headers = {
        "Authorization": f"bearer {API_KEY}",
        "X-DashScope-DataInspection": "enable",
    }
    async with websockets.connect(url, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "mode": "server_commit", "model": MODEL,
                "voice": VOICE, "response_format": "mp3",
                "sample_rate": 24000,
            }
        }))
        for t in texts:
            await ws.send(json.dumps({"type": "input_text_buffer.append", "text": t}))
        await ws.send(json.dumps({"type": "session.finish"}))

        audio = bytearray()
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "audio.delta":
                audio.extend(base64.b64decode(data["delta"]))
            elif data["type"] == "audio.completed":
                break
    with open(output, "wb") as f:
        f.write(audio)

asyncio.run(synthesize(["第一段。", "第二段。"], "out.mp3"))
```

### Node.js 提示

用 `ws` 或 `websocket` 包，逻辑同上：连 → `session.update` → N 个 `append` → `finish` → 收 `audio.delta` 拼 base64。

---

## 模型与音色

- **模型选择** → [references/models.md](references/models.md)
- **音色选择** → [references/voices.md](references/voices.md)

---

## 关键约束

1. **长度限制**：单次请求 ≤ 200 中文字符 / 600 UTF-8 字节。超过就切段，每段独立合成后拼接。
2. **切段技巧**：按标点切（句号/问号/叹号），避免切在词中间。每段之间如需停顿，合成时加静音或在文本里用标点。
3. **音色切换**：多角色场景，每个角色单独合成（不同 `voice`），再按顺序拼接。
4. **instructions 模型专属**：只有 `qwen3-tts-instruct-flash-realtime` 和 `-vc-` 系列支持 `instructions`，普通 flash 模型忽略该字段。
5. **Voice clone**：用 `qwen3-tts-vc-realtime-2026-01-15` + `qwen-tts-vc-voice-{voice_id}` 形式的音色（需先用克隆 API 注册）。

---

## 错误码速查

| HTTP Status | 常见原因 |
|-------------|----------|
| 401 | API Key 错或过期 |
| 400 | 字段拼错、模型不支持 instructions、文本超长 |
| 429 | QPS 超限，等 1s 重试 |
| 500 | 服务端临时故障，指数退避重试 |

---

## 给 Claude 的代码生成原则

- **问用户用什么语言**：Python / Node.js / Bash+curl，再生成对应代码
- **用 `websockets`（Python）或 `ws`（Node）**：成熟库，不要自己实现握手
- **永远 retry 3 次**：网络/OSS 偶尔失败，加指数退避
- **base64 拼完再写文件**：不要边收边写（虽然可以，但失败时文件会损坏）
- **URL 一律 http→https**：DashScope 返回的音频 URL 是 http，下载前替换
