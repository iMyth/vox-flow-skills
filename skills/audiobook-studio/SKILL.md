---
name: audiobook-studio
description: 文章/散文/小说转有声书或配音视频——直接拆分成品文章，TTS 合成，可选视频伴奏。当用户想把一篇文章变成音频/视频，或提到 "有声书"、"朗读"、"配音"、"文章转音频"、"散文朗读" 时触发。
license: MIT
compatibility: Requires the `hyperframes` skill (`npx skills add github.com/heygen-com/hyperframes`), the `qwen-tts` skill (`npx skills add github.com/imyth/qwen-tts`), ffmpeg, and a DashScope API key (https://dashscope.console.aliyun.com/).
metadata:
  author: imyth
  version: "2.0"
  depends-on: "hyperframes, github.com/imyth/qwen-tts"
  repository: "github.com/imyth/vox-flow-skills"
---

# Audiobook Studio

**文章转有声书 / 配音视频**。输入一篇成品文章（散文、小说、论文、演讲稿等），输出可发布的 MP3（或带视频的 MP4）。

核心设计：**不经过 LLM 改写**——原文就是最终脚本，只做智能拆分 + TTS 合成。可选 `--llm` 模式让 LLM 做格式整理和语义分段（不改写内容）。

## 依赖

- **`qwen-tts` skill** — 阿里云百炼 Qwen TTS API（语音合成），独立仓库：`npx skills add github.com/imyth/qwen-tts`
- **`hyperframes` skill** — HTML→视频渲染（视频伴奏，可选）
- **ffmpeg** — 音频拼接、响度归一化、音视频合成
- **DashScope API Key** — TTS 必需

**LLM 可选**——默认纯规则拆分（按段落/标点切分），不依赖大模型。`--llm` 模式可让 LLM 做格式整理和语义分段（适合非 Markdown 输入），复用同一个 `DASHSCOPE_API_KEY`。

## 前置信息（开始前必问）

**音色选择是最关键的一步**，尤其单人旁白场景，音色直接决定成品质量。

开始前必须确认：

1. **文章文件**（文本文件或粘贴）
2. **音色偏好**——**必须问**，参考 `qwen-tts` skill 的音色列表（`npx skills add github.com/imyth/qwen-tts` 后查看 `references/voices.md`）：
   - 男声 / 女声？
   - 风格：沉稳睿智（Eldric Sage）/ 温柔催眠（Kai）/ 率性帅气（Moon）/ 知性温柔（Maia）/ 阳光亲切（Cherry）？
   - 或直接让用户从音色表里挑
3. **是否需要视频**？→ 决定走不走 Step 4-5
4. **语速**：默认 0.9（慢速适合散文/哲学），1.0 适合叙事，0.85 适合催眠/冥想
5. **instruction 提示词**：给 TTS 的全局情感指令（如"低沉温暖，像深夜电台主播讲故事"）

---

## 5 步工作流

```
文章 → [1.创建项目] → [2.拆分文章] → [3.TTS合成] → [4.音频装配+归一化] → [5.视频伴奏(可选)]
                                                              ↓
                                                         audio/final.mp3
                                                         video/final.mp4
```

### Step 1 — 创建项目

按 [references/project-layout.md](references/project-layout.md) 建目录 + `project.json`。

```bash
mkdir -p my-audiobook/audio/lines my-audiobook/video
```

`project.json`：

```json
{
  "id": "proj_20260707_001",
  "name": "文章标题",
  "language": "zh-CN",
  "tts_default": {
    "model": "qwen3-tts-instruct-flash-realtime",
    "voice": "Kai",
    "speed": 0.9,
    "pitch": 1.0
  },
  "global_instructions": "低沉、温暖、舒缓的声音朗读，语速放慢，像深夜电台主播讲故事",
  "video_style": "深邃哲学风格：暗色背景 + 流动几何 + 渐变色光晕",
  "created_at": "2026-07-07T..."
}
```

把原文存到 `article.txt`。

**预检**（可选但推荐）：
```bash
python scripts/preflight.py --project-dir my-audiobook
```

### Step 2 — 拆分文章

用 `scripts/split_article.py` 把文章拆成 `script.json`：

```bash
# 纯规则模式（快速，适合格式规范的 Markdown）
python scripts/split_article.py \
  --input article.txt \
  --output script.json \
  --character "旁白" \
  --instructions "低沉、温暖、舒缓"

# LLM 模式（推荐，适合非 Markdown、PDF 提取、需要语义分段的场景）
python scripts/split_article.py \
  --input article.txt \
  --output script.json \
  --character "旁白" \
  --instructions "低沉、温暖、舒缓" \
  --llm
```

**两种模式**：

| | 纯规则模式 | LLM 模式 (`--llm`) |
|---|---|---|
| 速度 | 即时 | 几秒（调 LLM） |
| 适合 | 格式规范的 Markdown | 任意格式（纯文本、Word、PDF 提取等） |
| 公式处理 | 直接删除 | 转成可读文字 |
| 分段 | 按 `---` 和空行 | LLM 理解语义后分段 |
| 标点 | 保留原文 | 统一为中文标点 |
| 依赖 | 无 | `dashscope` 包 + `DASHSCOPE_API_KEY`；模型可通过 `DASHSCOPE_LLM_MODEL` 环境变量配置（默认 `qwen3.7-plus`） |

**拆分规则**（两种模式共用）：
- 每行一个完整句子（以 `。！？` 结尾），不在逗号/分号处断句，保持语义连贯
- 自动设置 `gap_after_ms`：根据标点类型和位置——句号 400ms，问号/叹号 600ms，段尾 900-1200ms，section 尾 2500ms
- LLM 模式额外：清理格式残留、LaTeX 公式转文字、统一标点、语义分段

**输出** `script.json`，schema 见 [references/script-format.md](references/script-format.md)。

**拆分后检查**：
1. 行数是否合理（通常 50-120 行）
2. 是否有遗漏内容（对比原文）
3. 每行是否都是完整句子（以 `。！？` 结尾）
4. LLM 模式：检查公式是否正确转成文字

### Step 3 — TTS 合成（委托 qwen-tts skill）

按 `qwen-tts` skill 的 WebSocket 协议（见 `github.com/imyth/qwen-tts`），**顺序逐行合成**：

```
for line in script.json 的每一行（顺序执行，不并行）:
    1. 读 project.json 的 voice / model / instructions
    2. 开 WS session → 发文本 → 收音频 → 写 audio/lines/{line_id}.mp3
    3. 用 ffprobe 测 duration_ms，回写到 script.json
```

**为什么顺序不并行**：
- 同一 voice + 同一 instruction 的顺序调用，音色和语感一致性最好
- 并行调用可能导致 TTS 服务端分配不同实例，产生音色波动

**关键技巧**：
- 文本 > 200 字按标点切段，多段放**同一 WebSocket session** 内发送，保持韵律连贯
- 单 session 单音色：同一 session 内无法切换 voice，多角色需开多个 session
- 失败重试 3 次 + 指数退避
- 进度提示：每完成 10% 告诉用户

### Step 4 — 音频装配 + 响度归一化

```bash
python scripts/assemble_audio.py --project-dir my-audiobook
```

脚本完成：
1. 按 script.json 顺序拼接 `audio/lines/*.mp3`，行间插静音 gap
2. 对 `audio/final.mp3` 做 **EBU R128 响度归一化**：
   ```
   ffmpeg -i final.mp3 -af loudnorm=I=-23:TP=-2:LRA=7 -ar 48000 final_normalized.mp3
   ```
   - `I=-23` LUFS：标准响度
   - `TP=-2`：峰值余量
   - `LRA=7`：响度范围（压缩动态差异，让全篇音量均匀）

### Step 5 — 视频伴奏（可选）

**前置**：用户明确说要视频。

按 [references/audiobook-video.md](references/audiobook-video.md) 规范，为每个 section 生成 HyperFrames HTML → 渲染 MP4 → 拼接 → 合并音轨。

```bash
# 1. 每个 section 一个独立项目目录（hyperframes 需要 index.html）
mkdir -p video/proj_1_2 video/proj_3_4 ...
cp video/sec_X.html video/proj_X/index.html

# 2. 渲染
cd video/proj_X && npx hyperframes render --output ../sec_X.mp4

# 3. 如果音频时长与视频不匹配，用 setpts 拉伸视频
ffmpeg -i sec_X.mp4 -vf "setpts=FACTOR*PTS" -r 30 -an sec_X_stretched.mp4

# 4. 拼接视频
ffmpeg -f concat -safe 0 -i video_list.txt -c copy video_merged.mp4

# 5. 合并音轨
ffmpeg -i video_merged.mp4 -i audio/final_normalized.mp3 \
  -c:v copy -c:a aac -ar 48000 -shortest video/final.mp4
```

**视频与音频时长对齐**：TTS 合成后才知道真实时长，视频渲染用原始估算时长。拼接后用 `setpts` 滤镜按比例拉伸/压缩视频，再用 `-shortest` 对齐。

---

## 进度沟通

每个 Step 开始前告诉用户"现在做什么"，完成后告诉"产出了什么"。长步骤（TTS、视频渲染）报百分比进度。

## 失败处理

- **TTS 失败** → 单行重试 3 次，全失败记录到 `audio/lines/{line_id}.failed` 并继续下一行
- **ffmpeg 报错** → 把 stderr 贴给用户，通常是路径/编码问题
- **视频渲染失败** → 先跑 font 清洗重试；再失败跳过该 section，最终合成时只用音频

## 产出物

完成后告诉用户：

```
✓ audio/final.mp3              (XX:XX 总时长)
✓ audio/final_normalized.mp3   (响度归一化版本)
✓ video/final.mp4              (如果走了 Step 5)
✓ script.json                  (可回放/修订)
```
