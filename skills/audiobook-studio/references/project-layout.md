# 项目目录结构

所有文件都在一个项目目录下，零外部依赖，纯文件系统 + JSON。

```
my-audiobook/                       # 项目根（名字用户定）
├── project.json                    # 项目元数据（必读）
├── outline.txt                     # 原始大纲（用户输入）
├── plan.json                       # LLM 大纲分析结果（可选，可重新生成）
├── characters.json                 # 角色列表
├── script.json                     # 最终脚本（核心产出）
│
├── audio/
│   ├── lines/                      # 每行 TTS 输出
│   │   ├── line_1.mp3
│   │   ├── line_2.mp3
│   │   └── ...
│   ├── section-1.mp3               # 章节合并
│   ├── section-2.mp3
│   └── final.mp3                   # 全剧合并
│
└── video/                          # 仅当用户需要视频时生成
    ├── section-1.html              # hyperframes 作品源文件
    ├── section-1.mp4               # 单段渲染
    ├── section-2.html
    ├── section-2.mp4
    └── final.mp4                   # 全剧合并
```

---

## `project.json` Schema

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
  "created_at": "2026-07-02T10:30:00Z",
  "updated_at": "2026-07-02T10:30:00Z"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 项目 ID，建议 `proj_YYYYMMDD_NNN` 或 UUID |
| `name` | 是 | 项目名（用于展示） |
| `language` | 是 | BCP 47 语言标签，影响 LLM 输出语言和 TTS 语言 |
| `llm` | 是 | LLM 配置 |
| `llm.endpoint` | 是 | OpenAI 兼容的 chat/completions endpoint（不带 `/chat/completions`） |
| `llm.model` | 是 | 模型名（`qwen-plus`、`gpt-4o-mini`、`llama3` 等） |
| `llm.api_key_env` | 推荐 | 环境变量名（比直接存 key 安全），Claude 读 `process.env[name]` |
| `llm.api_key` | 备选 | 直接存 API key（不推荐，仅本地测试用） |
| `tts_default` | 是 | 默认 TTS 配置（角色可覆盖） |
| `video_style` | 否 | 视频整体风格提示（传给 audiobook-video.md） |

---

## `characters.json` Schema

数组，每个元素一个角色：

```json
[
  {
    "id": "char_narrator",
    "name": "旁白",
    "voice": "Cherry",
    "model": "qwen3-tts-instruct-flash-realtime",
    "speed": 1.0,
    "pitch": 1.0,
    "description": "温和沉稳的主旁白"
  },
  {
    "id": "char_hero",
    "name": "主角",
    "voice": "Ethan",
    "model": "qwen3-tts-instruct-flash-realtime",
    "speed": 1.05,
    "pitch": 1.0,
    "description": "20 多岁青年，热血冲动"
  }
]
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 角色 ID，`char_` 前缀 + 名字拼音/英文 |
| `name` | 是 | **必须与 script.json 里的 character 字段完全一致** |
| `voice` | 是 | Qwen TTS 音色 ID（见 qwen-tts skill 的 voices.md） |
| `model` | 否 | TTS 模型（缺省回退到 `project.tts_default.model`） |
| `speed` | 否 | 语速，默认 1.0 |
| `pitch` | 否 | 音调，默认 1.0 |
| `description` | 否 | 角色描述（给 LLM 生成脚本时参考） |

---

## 关键约定

1. **角色名一致性**：`characters.json` 的 `name` 必须 = `script.json` 每行的 `character` 字段。拼写/空格/中英文都要一致。
2. **旁白角色**：约定俗成用 `"旁白"` 或 `"Narrator"`，必须在 characters.json 登记。
3. **ID 唯一性**：project / character / section / line 的 ID 在项目内必须唯一。
4. **大文件不进 JSON**：音频/视频路径只存相对路径（如 `audio/lines/line_1.mp3`），不存二进制。
5. **可 git 跟踪**：所有 JSON/txt 文件都纯文本，可以 commit；`audio/` 和 `video/` 加进 `.gitignore`。

---

## 推荐的 `.gitignore`

```gitignore
audio/lines/
audio/section-*.mp3
audio/final.mp3
video/
```
