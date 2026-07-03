# Qwen TTS 模型对比

## 三类模型

| 模型 ID | 接入 | 支持 instructions | 用途 |
|---------|------|------------------|------|
| `qwen3-tts-flash-realtime` | WS | ❌ | 基础 TTS，纯文本合成，最快最便宜 |
| `qwen3-tts-instruct-flash-realtime` | WS | ✅ | 情感/风格可控，**默认推荐** |
| `qwen3-tts-vc-realtime-2026-01-15` | WS | ❌ | Voice Clone（克隆音色） |
| `qwen-tts` | HTTP | 视具体子模型 | 旧版 HTTP REST 入口 |

> 所有 `-realtime` 结尾的模型**只能走 WebSocket**，HTTP REST 端点不支持。

---

## 选型建议

### 场景 1：有声书 / 广播剧（默认）

**`qwen3-tts-instruct-flash-realtime`**

- 能用 `instructions` 控制"温柔地"、"愤怒地"、"低语"等情感
- 音色连贯、韵律自然
- 支持 `optimize_instructions: true` 让模型自己优化指令措辞

```json
{
  "type": "session.update",
  "session": {
    "model": "qwen3-tts-instruct-flash-realtime",
    "voice": "Cherry",
    "instructions": "温柔地、缓慢地，像讲睡前故事"
  }
}
```

### 场景 2：旁白 / 工具类（无需情感控制）

**`qwen3-tts-flash-realtime`**

- 更便宜、更快
- 不支持 `instructions`（传了会被忽略）
- 适合：教程旁白、新闻播报、系统提示音

### 场景 3：声音克隆

**`qwen3-tts-vc-realtime-2026-01-15`**

- 克隆流程：先调 DashScope 声音克隆 API 注册音频 → 拿到 `qwen-tts-vc-voice-{voice_id}` → 用 VC 模型合成
- 克隆 API endpoint：`POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization`
- **不支持 `instructions`**

---

## HTTP vs WebSocket 怎么选

| 维度 | HTTP REST | WebSocket Realtime |
|------|-----------|-------------------|
| 易用性 | 一个 curl 就行 | 需要维持连接 |
| 长文本 | 必须切段分别调 | 一个 session 多段文本，**韵律更连贯** |
| 多角色 | 多次 HTTP 调用 | 单 session 内无法切音色，需要多 session |
| 延迟 | 较高（要等服务端完整生成） | 流式返回，第一段音频几秒就来 |
| 推荐 | 快速验证、短文本 | **生产环境首选** |

**结论**：除了"只想 curl 一下试试"的场景，都用 WebSocket。

---

## 多角色有声书的实际做法

Qwen TTS 单 session 内只能用一个 `voice`。所以多角色方案：

1. 按角色 + 顺序分组
2. 每行（或每段）独立开一个 WS session，传对应的 `voice`
3. 拿到每行的 mp3 后，用 ffmpeg 按顺序拼接，中间插静音 gap

这就是 audiobook-studio skill 的工作方式。
