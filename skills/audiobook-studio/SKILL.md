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
大纲 → [1.创建项目] → [2.分析大纲] → [4.创建角色] → [3.生成脚本]
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
    "voice": "Cherry",
    "speed": 1.0,
    "pitch": 1.0
  },
  "video_style": "大气几何 + 渐变流动，避免文字堆砌",
  "created_at": "2026-07-02T..."
}
```

把大纲存到 `outline.txt`。

**预检**（可选但推荐）：
```bash
# 检查依赖
scripts/preflight.py --project-dir my-audiobook
# 测试 LLM 连通性
curl -s "$LLM_ENDPOINT/chat/completions" -H "Authorization: Bearer $LLM_API_KEY" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"hi"}],"max_tokens":5}' | head -c 200
```

### Step 2 — 分析大纲

调 LLM 返回结构化章节计划。prompt 见 [references/llm-prompts.md](references/llm-prompts.md) 的 "Outline Analysis"。

**调用方式**（推荐）：
```bash
python scripts/call_llm.py \
  --endpoint "$LLM_ENDPOINT" --model qwen-plus --api-key-env DASHSCOPE_API_KEY \
  --system "$(cat references/llm-prompts.md 的 Outline Analysis System Prompt)" \
  --user outline.txt --output plan.json
```

**关键**：LLM 调用必须带 `response_format: { "type": "json_object" }` 强制 JSON 输出。

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

### Step 3 — 创建 / 确认角色

根据 `plan.json` 的 `suggested_characters`，写 `characters.json`：

```json
[
  { "id": "char_1", "name": "旁白", "voice": "Cherry", "model": "qwen3-tts-instruct-flash-realtime", "speed": 1.0, "pitch": 1.0 },
  { "id": "char_2", "name": "主角", "voice": "Ethan", "model": "qwen3-tts-instruct-flash-realtime", "speed": 1.0, "pitch": 1.0 }
]
```

**音色匹配建议**：让 Claude 根据角色性格从 `qwen-tts` skill 的 [voices.md](../qwen-tts/references/voices.md) 挑选，并告知用户选择理由，让用户最终拍板。

**校验**：`voice` 字段必须在 `voices.md` 的 ID 列表中，否则 TTS 会返回 400 错误。

### Step 4 — 生成脚本

再次调 LLM，按 plan 的章节结构生成完整对白脚本。prompt 见 [references/llm-prompts.md](references/llm-prompts.md) 的 "Script Generation"。

**输出** → `script.json`，schema 见 [references/script-format.md](references/script-format.md)。

关键约束：
- 只能使用 `characters.json` 里登记过的角色名
- 每行带 `gap_after_ms`（默认 500，可调）
- `instructions` 字段给 TTS 情感提示（"温柔地"、"低语"等）
- 每行 `text` ≤ 180 中文字符（TTS 限制）
- `line_id` 命名规则：`{section_id}_line_{n}`

**生成后校验**（必须执行）：
1. 用 `scripts/validate_script.py --project-dir .` 检查角色名一致性、行长度、ID 唯一性
2. 如果总行数 > 50，告知用户预计 TTS 耗时（约 2 秒/行）
3. 校验不通过则让 LLM 修正后重新生成

### Step 5 — TTS 合成（委托 qwen-tts skill）

按 [qwen-tts skill](../qwen-tts/SKILL.md) 的 Qwen-TTS Realtime WebSocket 协议，逐行合成：

```
for line in script.json 的每一行:
    1. 查 characters.json 拿 voice / model / instructions
    2. 走 WS 协议合成 → audio/lines/{line_id}.mp3
    3. 用 ffprobe 测 duration_ms，回写到 script.json（**走视频流程时必选**，用于 Step 7 时间轴同步；纯音频可选）
```

**关键技巧**：
- 文本 > 200 中文字符按标点切段，多段放同一 session 保韵律
- 失败重试 3 次 + 指数退避
- 进度提示：每完成 10% 告诉用户
- 可直接用 `../qwen-tts/scripts/synthesize.py --file script.json --output-dir audio/lines --chars characters.json` 批量合成
- 合成后用 `scripts/measure_durations.py --project-dir .` 回写 duration_ms 到 script.json

### Step 6 — 音频装配（ffmpeg）

按章节拼接 `audio/lines/*.mp3`，中间插静音 gap。

**推荐做法**：先生成静音文件，再用 concat 拼接。

```bash
# 1. 生成静音文件（按 gap_after_ms 生成不同时长的静音）
ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 0.5 -q:a 9 gap_500.mp3
ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 1.0 -q:a 9 gap_1000.mp3

# 2. 写 filelist.txt（音频和静音交替）
#   file 'line_1.mp3'
#   file 'gap_500.mp3'
#   file 'line_2.mp3'
#   file 'gap_800.mp3'
ffmpeg -f concat -safe 0 -i filelist.txt -c copy section-1.mp3

# 3. 全剧合并
ffmpeg -f concat -safe 0 -i all_files.txt -c copy audio/final.mp3
```

> 实际生成时让 Claude 写 Python/Node 脚本循环处理，或直接用 `scripts/assemble_audio.py --project-dir my-audiobook`。不要手工敲每个 ffmpeg。

### Step 7 — 视频伴奏（可选，委托 hyperframes skill）

**前置**：用户明确说要视频。

按 [references/audiobook-video.md](references/audiobook-video.md) 的规范生成 HTML 作品，再用 hyperframes 渲染：

- **快速开始**：复制 `assets/video-starter.html` 作为模板，替换场景内容和时间轴
- **手动生成**：按 `audiobook-video.md` 规范从零写 HTML

```bash
# 在 video/ 目录下执行，-c 指定 composition 文件，-o 指定输出路径
cd video
npx hyperframes render . -c section-1.html -o section-1.mp4
```

每个 section 独立生成 + 渲染（避免单文件过长）。

**核心原则**：视频是"视觉伴奏"，不是字幕。参考 `audiobook-video.md` 的详细要求。

**渲染前必须执行后处理**：LLM 生成的 HTML 几乎必然有细节错误。跑 `scripts/postprocess_video_html.py` 执行 5 步 safety-net（duration 修正、font 清洗、clip timing 校准等），详见 [audiobook-video.md](references/audiobook-video.md) 的"后处理 Safety-Net"。

**失败降级**：如渲染失败，先跑 font 清洗重试；再失败则跳过该 section 视频，最终合成时只用音频。

### Step 8 — 最终合成（可选）

把每段 section 视频合并成全剧视频：

```bash
# 分辨率统一为 1920x1080，输出到 video/tmp/ 避免覆盖原文件
mkdir -p video/tmp
for f in video/section-*.mp4; do
  base=$(basename "$f" .mp4)
  ffmpeg -i "$f" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -an "video/tmp/${base}_scaled.mp4"
done

# 写 concat list
for f in video/tmp/*_scaled.mp4; do echo "file '$f'"; done > video/video_list.txt

# concat
ffmpeg -f concat -safe 0 -i video/video_list.txt -c:v libx264 video/noaudio.mp4

# 合并音轨（音频重采样为 48kHz 以匹配视频容器）
ffmpeg -i video/noaudio.mp4 -i audio/final.mp3 -c:v copy -c:a aac -ar 48000 -shortest video/final.mp4
```

> `-shortest`：以较短的流（通常是视频）为准截断，防止音画不同步。合并后如果时长差异 > 1s，警告用户检查。

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
