# Script Format（脚本 JSON 规范）

`script.json` 是有声书的核心产出——所有对白、角色、停顿、情感提示都在这里。

---

## 顶层结构

```json
{
  "title": "我的有声书",
  "language": "zh-CN",
  "total_lines": 120,
  "sections": [
    { "id": "sec_1", "title": "第一章", "order": 0, "lines": [...] },
    { "id": "sec_2", "title": "第二章", "order": 1, "lines": [...] }
  ]
}
```

---

## Section 结构

```json
{
  "id": "sec_1",
  "title": "第一章",
  "order": 0,
  "lines": [
    {
      "id": "sec_1_line_1",
      "text": "夜幕降临，古老的城门缓缓关闭。",
      "character": "旁白",
      "instructions": "缓慢地、略带神秘",
      "gap_after_ms": 800
    },
    {
      "id": "sec_1_line_2",
      "text": "我必须在今晚离开。",
      "character": "主角",
      "instructions": "紧张地低语",
      "gap_after_ms": 500
    }
  ]
}
```

### Section 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | `sec_` + 序号 |
| `title` | 是 | 章节标题（"片头"、"第一幕"、"第一章" 都行） |
| `order` | 是 | 排序用，从 0 开始 |
| `lines` | 是 | 该章节的所有行 |

### Line 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 全局唯一，建议 `{section_id}_line_{n}` |
| `text` | 是 | 该行的文本（**≤ 200 中文字符**，超过要切段） |
| `character` | 是 | 角色名，必须匹配 `characters.json` 里某个 `name` |
| `instructions` | 否 | 给 TTS 的情感/风格提示（如 "温柔地"、"低语"、"愤怒"） |
| `gap_after_ms` | 推荐 | 该行之后插入的静音时长（毫秒）。默认 500，对话之间可 300-500，段落之间可 800-1500 |

---

## Line ID 命名约定

为了便于调试和 TTS 文件对应：

```
sec_1_line_1
sec_1_line_2
...
sec_2_line_1
sec_2_line_2
```

生成 `audio/lines/{line_id}.mp3` 时直接用 line ID 当文件名。

---

## `text` 字段的长度限制

Qwen TTS 单次请求上限：**200 中文字符 / 600 UTF-8 字节**。

处理策略：

1. **LLM 生成时就控制**：在 prompt 里要求每行 ≤ 180 字
2. **合成时二次检查**：超长按标点切段（句号/问号/叹号/逗号）
3. **切段不切词**：不要在词中间断开（"葡萄 / 酒" 不行）

如果一行必须很长（如旁白描述），可以：
- 切段后每段独立调用 TTS（但可能损失韵律连贯）
- 或者用 WebSocket session 一次发多段（**推荐**，同一 session 内韵律连贯）

---

## `gap_after_ms` 建议值

| 场景 | 推荐 gap |
|------|---------|
| 同一角色连续对话 | 300-500 ms |
| 角色切换 | 500-700 ms |
| 段落切换 | 800-1200 ms |
| 章节切换 | 1500-3000 ms |
| 强调 / 停顿 | 500-1000 ms |
| 片头 / 片尾 | 2000+ ms |

---

## `instructions` 字段

仅 `qwen3-tts-instruct-flash-realtime` 模型支持。给 TTS 情感/风格提示。

**好的写法**：
- `"温柔地"`
- `"愤怒地，声音提高"`
- `"低语，像说秘密"`
- `"像讲睡前故事，缓慢"`
- `"紧张地，带喘息"`

**差的写法**：
- `"用男声"`（音色由 voice 字段决定，instructions 无法切换音色）
- `"快速"`（用 `speed` 字段更可控）
- `"讲得很长"`（模糊，不如具体说"缓慢地，每字拉长"）

**配合 `optimize_instructions: true`**：让 TTS 模型自己优化指令措辞，通常效果更好。

---

## 完整示例

```json
{
  "title": "夜奔",
  "language": "zh-CN",
  "total_lines": 5,
  "sections": [
    {
      "id": "sec_1",
      "title": "片头",
      "order": 0,
      "lines": [
        {
          "id": "sec_1_line_1",
          "text": "夜奔，一个关于逃离与追寻的故事。",
          "character": "旁白",
          "instructions": "缓慢地、略带神秘",
          "gap_after_ms": 1500
        }
      ]
    },
    {
      "id": "sec_2",
      "title": "第一幕",
      "order": 1,
      "lines": [
        {
          "id": "sec_2_line_1",
          "text": "我必须在今晚离开。",
          "character": "主角",
          "instructions": "紧张地低语",
          "gap_after_ms": 500
        },
        {
          "id": "sec_2_line_2",
          "text": "可是城门已经关了。",
          "character": "同伴",
          "instructions": "担忧",
          "gap_after_ms": 800
        }
      ]
    }
  ]
}
```
