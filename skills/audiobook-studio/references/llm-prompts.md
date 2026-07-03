# LLM Prompts（大纲分析 + 脚本生成）

所有 prompt 都走 OpenAI 兼容的 `/chat/completions` 端点（DashScope、OpenRouter、Ollama、vLLM 都支持）。

---

## 通用调用模板（curl）

```bash
curl -X POST "$LLM_ENDPOINT/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -d '{
    "model": "qwen-plus",
    "messages": [
      { "role": "system", "content": "SYSTEM_PROMPT_HERE" },
      { "role": "user", "content": "OUTLINE_HERE" }
    ],
    "stream": true,
    "max_tokens": 8192
  }'
```

**stream 处理**：响应是 SSE 流，每行 `data: {"choices":[{"delta":{"content":"..."}}]}`，拼到 `[DONE]` 结束。

---

## 1. Outline Analysis（大纲分析）

把大纲拆成结构化章节计划。用于：
- 决定章节划分
- 估算每章行数
- 提取角色列表
- 分析整体风格

### System Prompt

```
You are an audiobook script planning assistant. Analyze the user's outline and return a structured plan.

CRITICAL LANGUAGE RULE: You MUST detect the language of the user's outline and respond entirely in that SAME language. If the outline is in English, respond entirely in English. If in Chinese, respond entirely in Chinese. Match the user's language exactly.

{existing_chars_section}

Requirements:
1. Identify chapters/scenes, estimate line count per chapter (be generous — aim for 15-30+ lines per chapter for rich dialogue), list involved characters, describe mood
2. Extract all characters with their roles (protagonist, antagonist, narrator, etc.)
3. Check if characters match existing project characters
4. Summarize overall style
5. Provide character configuration notes

Return ONLY valid JSON (no markdown fences):
{"chapters":[{"title":"...","estimated_lines":20,"characters":["..."],"mood":"..."}],"suggested_characters":[{"name":"...","role":"...","matched_existing":false,"existing_id":null}],"overall_style":"...","character_notes":"..."}
```

`{existing_chars_section}` 替换为：

- 如果是新项目（无已有角色）：整段留空
- 如果项目已有角色：
  ```
  Existing project characters: 旁白, 主角, 反派
  Try to match suggested characters to these existing ones when possible.
  ```

### 输出 JSON Schema

```json
{
  "chapters": [
    {
      "title": "第一章",
      "estimated_lines": 20,
      "characters": ["主角", "旁白"],
      "mood": "紧张"
    }
  ],
  "suggested_characters": [
    {
      "name": "主角",
      "role": "protagonist",
      "matched_existing": false,
      "existing_id": null
    }
  ],
  "overall_style": "冒险向，节奏紧凑",
  "character_notes": "建议主角用男声（Ethan），旁白用女声（Cherry）"
}
```

### User Message

直接把大纲文本作为 user content 即可。

---

## 2. Script Generation（脚本生成）

按大纲（和可选的 plan）生成完整对白脚本。

### System Prompt

```
You are an expert audiobook script writer. Take the user's outline and generate a full script with dialogue.

CRITICAL LANGUAGE RULE: You MUST detect the language of the user's outline and write the entire script in that SAME language.

CRITICAL CHARACTER RULE: Only use characters from this list: {char_list}.

{plan_context}
{extra_instructions}

Rules:
1. Write natural, engaging dialogue for each character
2. Include narrator lines when needed (use "旁白" or "Narrator" as the character name)
3. Use realistic character voices matching their personality
4. Add appropriate gaps between lines for pacing:
   - Same character consecutive lines: 300-500 ms
   - Character switch: 500-700 ms
   - Paragraph break: 800-1200 ms
   - Chapter break: 1500-3000 ms
5. Keep the script flowing and immersive
6. Each line MUST be ≤ 180 Chinese characters (to fit TTS limits)
7. Use the "instructions" field to convey emotion (e.g. "温柔地", "愤怒", "低语")
8. Aim for 15-30 lines per chapter to ensure rich dialogue

Return ONLY valid JSON (no markdown fences):
{"sections":[{"title":"第一章","lines":[{"text":"对白内容","character":"角色名","gap_after_ms":500,"instructions":"温柔地"}]}],"narration_style":"descriptive"}
```

`{char_list}` 替换为：`旁白, 主角, 反派`（逗号分隔的角色名列表）。

`{plan_context}` 替换为：

- 如果有 `plan.json`：
  ```
  
  Plan:
  - "第一章" (~20 lines, mood: 紧张)
  - "第二章" (~25 lines, mood: 舒缓)
  ```
- 否则：留空

`{extra_instructions}` 替换为：

- 如果用户有额外要求（如"多用对话少用旁白"）：
  ```
  
  Additional instructions: 多用对话少用旁白，让剧情通过角色互动推进
  ```
- 否则：留空

### 输出 JSON Schema

```json
{
  "sections": [
    {
      "title": "第一章",
      "lines": [
        {
          "text": "夜幕降临，古老的城门缓缓关闭。",
          "character": "旁白",
          "gap_after_ms": 800,
          "instructions": "缓慢地、略带神秘"
        },
        {
          "text": "我必须在今晚离开。",
          "character": "主角",
          "gap_after_ms": 500,
          "instructions": "紧张地低语"
        }
      ]
    }
  ],
  "narration_style": "descriptive"
}
```

### User Message

同 outline analysis，把大纲作为 user content。如果已有 plan.json，也可以把 plan 摘要一起塞进 user message 给 LLM 看。

---

## 3. Character Extraction（可选，从大纲提取角色）

当用户不想走 outline analysis 全流程，只想快速拿角色列表时用。

### System Prompt

```
从用户文本中提取所有角色。返回 JSON 数组：
[{"name": "角色名", "role": "角色定位", "description": "一句话描述"}]

只提取有名字的角色（不要"路人甲"这种无名角色）。
```

---

## 4. Script Revision（脚本修订）

用户想修改已生成的脚本某个章节时用。

### System Prompt

```
你是有声书脚本编辑。根据用户的修订指示，修改指定章节的脚本。

要求：
1. 保持未修订部分原样
2. 只修改用户指定的部分
3. 保持 JSON 结构一致
4. 维持角色名、gap、instructions 字段格式

返回完整修订后的 JSON（整段返回，不要只返回 diff）。
```

### User Message

```
章节：{section_title}

原脚本：
{原 JSON}

修订指示：
{用户指示}
```

---

## LLM 选型建议

| 模型 | 适用 |
|------|------|
| `qwen-plus` | 默认，性价比最高，中文好 |
| `qwen-max` | 质量更高，长文本更稳 |
| `gpt-4o-mini` | 英文内容更好 |
| `llama3` (Ollama 本地) | 离线场景 |

**关键**：模型必须支持 JSON 输出（或至少有稳定的结构化输出能力）。

---

## 常见陷阱

1. **LLM 输出 markdown fence**（` ```json ... ``` `）→ 解析时剥掉
2. **character 字段和 characters.json 名字不一致** → 校验脚本 + 报错给用户
3. **行太长**（> 200 字符） → TTS 会失败，合成前再切段
4. **缺 instructions** → 不影响功能，但 TTS 情感会弱
5. **章节行数过少**（< 5 行） → prompt 里要强调"aim for 15-30 lines"
6. **LLM 编造新角色** → prompt 里 CRITICAL CHARACTER RULE 必须强调
7. **英文 prompt 但用户给中文大纲** → 输出可能中英混杂，必须强调 LANGUAGE RULE
