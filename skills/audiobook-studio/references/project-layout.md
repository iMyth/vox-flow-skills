# 项目目录结构

所有文件都在一个项目目录下，零外部依赖，纯文件系统 + JSON。

```
my-audiobook/                       # 项目根（名字用户定）
├── project.json                    # 项目元数据（必读）
├── article.txt                     # 原始文章（用户输入）
├── characters.json                 # 角色列表
├── script.json                     # 拆分后的脚本（核心产出）
│
├── audio/
│   ├── lines/                      # 每行 TTS 输出
│   │   ├── line_001.mp3
│   │   ├── line_002.mp3
│   │   └── ...
│   ├── section-1.mp3               # 章节合并
│   ├── section-2.mp3
│   ├── final.mp3                   # 全剧合并
│   └── final_normalized.mp3        # 响度归一化版本
│
└── video/                          # 仅当用户需要视频时生成
    ├── sec_1-2.html                # hyperframes 作品源文件
    ├── sec_1-2.mp4                 # 单段渲染
    ├── sec_3-4.html
    ├── sec_3-4.mp4
    └── final.mp4                   # 全剧合并
```

---

## `project.json` Schema

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
  "created_at": "2026-07-07T10:30:00Z",
  "updated_at": "2026-07-07T10:30:00Z"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 项目 ID，建议 `proj_YYYYMMDD_NNN` 或 UUID |
| `name` | 是 | 项目名（用于展示） |
| `language` | 是 | BCP 47 语言标签，影响 TTS 语言 |
| `tts_default` | 是 | 默认 TTS 配置（角色可覆盖） |
| `tts_default.model` | 是 | TTS 模型（推荐 `qwen3-tts-instruct-flash-realtime`） |
| `tts_default.voice` | 是 | 音色 ID（见 qwen-tts skill 的 voices.md） |
| `tts_default.speed` | 否 | 语速，默认 1.0，散文/哲学建议 0.9 |
| `global_instructions` | 推荐 | 全局 TTS 情感指令（所有行共用） |
| `video_style` | 否 | 视频整体风格提示（传给 audiobook-video.md） |

---

## `characters.json` Schema

数组，每个元素一个角色：

```json
[
  {
    "id": "char_narrator",
    "name": "旁白",
    "voice": "Kai",
    "model": "qwen3-tts-instruct-flash-realtime",
    "speed": 0.9,
    "pitch": 1.0,
    "description": "温柔催眠男声，适合深夜哲学散文"
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
| `description` | 否 | 角色描述 |

---

## 关键约定

1. **角色名一致性**：`characters.json` 的 `name` 必须 = `script.json` 每行的 `character` 字段。拼写/空格/中英文都要一致。
2. **旁白角色**：约定俗成用 `"旁白"` 或 `"Narrator"`，必须在 characters.json 登记。
3. **ID 唯一性**：project / character / section / line 的 ID 在项目内必须唯一。
4. **大文件不进 JSON**：音频/视频路径只存相对路径（如 `audio/lines/line_001.mp3`），不存二进制。
5. **可 git 跟踪**：所有 JSON/txt 文件都纯文本，可以 commit；`audio/` 和 `video/` 加进 `.gitignore`。

---

## 推荐的 `.gitignore`

```gitignore
audio/lines/
audio/section-*.mp3
audio/final.mp3
audio/final_normalized.mp3
video/
```
