# Qwen-TTS Realtime 模型

## 两类模型

| 模型 ID | instruction | 推荐场景 |
|---------|------------|---------|
| `qwen3-tts-instruct-flash-realtime` | ✅ | **默认推荐**，情感/风格可控 |
| `qwen3-tts-flash-realtime` | ❌ | 基础 TTS，更快更便宜 |

> 两个模型都**只能走 WebSocket**，不支持 HTTP REST。

---

## 选型建议

### 有声书 / 广播剧（默认）

**`qwen3-tts-instruct-flash-realtime`**

- 用 `instructions` 控制"温柔地"、"愤怒地"、"低语"等情感
- 配合 `optimize_instructions: true` 让模型优化指令措辞
- ≤ 1600 token，中英文都行

### 旁白 / 工具类（无需情感控制）

**`qwen3-tts-flash-realtime`**

- 更便宜、更快
- 不支持 `instructions`（传了会被忽略）
- 适合：教程旁白、新闻播报、系统提示音

---

## 多角色有声书的实际做法

单 session 内只能用一个 `voice`。多角色方案：

1. 按角色 + 顺序分组
2. 每行（或每段）独立开一个 WS session，传对应的 `voice`
3. 拿到每行的 mp3 后，用 ffmpeg 按顺序拼接，中间插静音 gap

这就是 audiobook-studio skill 的工作方式。
