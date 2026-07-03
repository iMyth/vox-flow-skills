---
name: audiobook-studio
description: 多角色有声书全流程制作——从大纲到可发布的音频/视频成品。编排 LLM 分析 → 脚本生成 → Qwen TTS 合成 → hyperframes 视频伴奏 → ffmpeg 合成。当用户想制作有声书、广播剧、多角色配音内容、带视频伴奏的音频，或提到 "audiobook"、"有声书"、"广播剧"、"小说转音频"、"配音作品" 时触发。
license: MIT
compatibility: Requires the `hyperframes` skill (`npx skills add github.com/heygen-com/hyperframes`), the `qwen-tts` skill (bundled in this repo), ffmpeg, and a DashScope API key (https://dashscope.console.aliyun.com/).
metadata:
  author: imyth
  version: "1.0"
  depends-on: "hyperframes, qwen-tts"
  repository: "github.com/imyth/vox-flow-skills"
---

# Audiobook Studio

**多角色有声书全流程制作**。输入一段大纲/故事梗概，输出可发布的 MP3（或带视频的 MP4）。

## 依赖

- **`qwen-tts` skill** — 阿里云百炼 Qwen TTS API 文档（语音合成）
- **`hyperframes` skill** — HTML→视频 渲染（视频伴奏，可选）
- **ffmpeg** — 音频拼接、音视频合成（`brew install ffmpeg` / `apt install ffmpeg`）
- **LLM API** — OpenAI 兼容端点（DashScope、OpenRouter、本地 Ollama 都行）

## 前置信息（先问用户）

开始之前确认这些：

1. **大纲 / 故事文本**（文本文件或粘贴都行）
2. **LLM API**：endpoint、API key、model（如果用户没说，推荐 DashScope + `qwen-plus`）
3. **DashScope API Key**（用于 TTS，如果用户没装过 qwen-tts skill 就一起申请）
4. **是否需要视频**？→ 决定走不走 Step 7-8
5. **语言**？→ 影响音色和 LLM 输出语言

---

## 8 步工作流

```
大纲 → [1.创建项目] → [2.分析大纲] → [3.生成脚本] → [4.创建角色]
                                                         ↓
最终 MP4 ← [8.合并] ← 视频 ← [7.视频伴奏] ← [6.音频装配] ← [5.TTS合成] ← characters.json
        MP3
```

### Step 1 — 创建项目

按 [references/project-layout.md](references/project-layout.md) 的目录结构，建好目录 + `project.json`。

```bash
mkdir -p my-audiobook/audio/lines my-audiobook/video
```

写 `project.json`：

```json
{
  "id": "proj_20260702_001",
  "name": "我的有声书",
  "language": "zh-CN",
  "llm": {
    "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "api_key_env": "DASHSCOPE_API_KEY"
  },
  "tts_default": {
    "model": "qwen3-tts-instruct-flash-realtime",
    "voice": "Cherry"
  },
  "video_style": "大气几何 + 渐变流动，避免文字堆砌",
  "created_at": "2026-07-02T..."
}
```

把大纲存到 `outline.txt`。

### Step 2 — 分析大纲

调 LLM 返回结构化章节计划。prompt 见 [references/llm-prompts.md](references/llm-prompts.md) 的 "Outline Analysis"。

**输出** → `plan.json`：

```json
{
  "chapters": [
    { "title": "第一章", "estimated_lines": 20, "characters": ["主角", "旁白"], "mood": "紧张" }
  ],
  "suggested_characters": [
    { "name": "主角", "role": "protagonist", "matched_existing": false }
  ],
  "overall_style": "冒险向，节奏紧凑"
}
```

### Step 3 — 生成脚本

再次调 LLM，按 plan 的章节结构生成完整对白脚本。prompt 见 [references/llm-prompts.md](references/llm-prompts.md) 的 "Script Generation"。

**输出** → `script.json`，schema 见 [references/script-format.md](references/script-format.md)。

关键约束：
- 只能使用 `characters.json` 里登记过的角色名
- 每行带 `gap_after_ms`（默认 500，可调）
- `instructions` 字段给 TTS 情感提示（"温柔地"、"低语"等）

### Step 4 — 创建 / 确认角色

根据 `plan.json` 的 `suggested_characters`，写 `characters.json`：

```json
[
  { "id": "char_1", "name": "旁白", "voice": "Cherry", "model": "qwen3-tts-instruct-flash-realtime", "speed": 1.0, "pitch": 1.0 },
  { "id": "char_2", "name": "主角", "voice": "Ethan", "model": "qwen3-tts-instruct-flash-realtime", "speed": 1.0, "pitch": 1.0 }
]
```

**音色匹配建议**：让 Claude 根据角色性格从 `qwen-tts` skill 的 [voices.md](../qwen-tts/references/voices.md) 挑选，并告知用户选择理由，让用户最终拍板。

### Step 5 — TTS 合成（委托 qwen-tts skill）

按 [qwen-tts skill](../qwen-tts/SKILL.md) 的 WebSocket Realtime 协议，逐行合成：

```
for line in script.json 的每一行:
    1. 查 characters.json 拿 voice / model / instructions
    2. 走 WS 协议合成 → audio/lines/{line_id}.mp3
    3. 用 ffprobe 测 duration_ms，回写到 script.json（可选，用于时间轴同步）
```

**关键技巧**：
- 文本 > 200 中文字符按标点切段，多段放同一 session 保韵律
- 失败重试 3 次 + 指数退避
- 进度提示：每完成 10% 告诉用户

### Step 6 — 音频装配（ffmpeg）

按章节拼接 `audio/lines/*.mp3`，中间插静音 gap：

```bash
# 给每个 line 后插入静音（按 gap_after_ms）
ffmpeg -i line_1.mp3 -af "apad=whole_dur=1.5" line_1_padded.mp3

# 章节内 concat
# 写 filelist.txt:
#   file 'line_1_padded.mp3'
#   file 'line_2_padded.mp3'
ffmpeg -f concat -safe 0 -i filelist.txt -c copy section-1.mp3

# 全剧合并
ffmpeg -f concat -safe 0 -i all_files.txt -c copy audio/final.mp3
```

> 实际生成时让 Claude 写 Python/Node 脚本循环处理，不要手工敲每个 ffmpeg。

### Step 7 — 视频伴奏（可选，委托 hyperframes skill）

**前置**：用户明确说要视频。

按 [references/audiobook-video.md](references/audiobook-video.md) 的规范生成 HTML 作品，再用 hyperframes 渲染：

```bash
npx hyperframes render section-1.html section-1.mp4
```

每个 section 独立生成 + 渲染（避免单文件过长）。

**核心原则**：视频是"视觉伴奏"，不是字幕。参考 `audiobook-video.md` 的详细要求。

### Step 8 — 最终合成（可选）

把每段 section 视频合并成全剧视频：

```bash
# 分辨率统一为 1920x1080
for f in video/section-*.mp4; do
  ffmpeg -i "$f" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -an "video/tmp_$f" 
done

# concat
ffmpeg -f concat -safe 0 -i video_list.txt -c:v libx264 video/noaudio.mp4

# 合并音轨
ffmpeg -i video/noaudio.mp4 -i audio/final.mp3 -c:v copy -c:a aac -shortest video/final.mp4
```

---

## 进度沟通

每个 Step 开始前告诉用户"现在做什么"，完成后告诉用户"产出了什么、下一步是什么"。长步骤（TTS、视频渲染）要报百分比进度。

## 失败处理

- **LLM 返回非法 JSON** → 重试 2 次，再不行让用户手动检查
- **TTS 失败** → 单行重试 3 次，全失败记录到 `audio/lines/{line_id}.failed` 并继续下一行
- **ffmpeg 报错** → 把 stderr 贴给用户，通常是路径/编码问题

## 产出物

完成后告诉用户：

```
✓ audio/final.mp3      (XX:XX 总时长)
✓ video/final.mp4      (如果走了 Step 7-8)
✓ script.json          (可回放/修订)
✓ characters.json      (可复用)
```
