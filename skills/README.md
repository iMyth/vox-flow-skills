# VoxFlow Skills

从 [VoxFlow](https://github.com/imyth/VoxFlow) 抽离的 Agent Skills，符合 [Agent Skills 规范](https://agentskills.io/specification)。

## Skills

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| [`audiobook-studio`](./audiobook-studio/) | 多角色有声书全流程编排（大纲 → 脚本 → TTS → 视频 → 成品） | `hyperframes`, `qwen-tts`, ffmpeg, DashScope API |
| [`qwen-tts`](./qwen-tts/) | Qwen TTS API 文档（HTTP REST + WebSocket Realtime） | DashScope API key |

## Install

```bash
# 安装整个 skill 仓库（包含两个 skill）
npx skills add github.com/imyth/vox-flow-skills

# 或单独安装某个 skill
npx skills add github.com/imyth/vox-flow-skills/skills/qwen-tts
npx skills add github.com/imyth/vox-flow-skills/skills/audiobook-studio
```

## External Dependencies

### `audiobook-studio` 需要

| 依赖 | 安装方式 |
|------|---------|
| `hyperframes` skill | `npx skills add github.com/heygen-com/hyperframes` |
| `ffmpeg` | `brew install ffmpeg` / `apt install ffmpeg` |
| DashScope API key | https://dashscope.console.aliyun.com/ |
| LLM API（OpenAI 兼容） | 任意（DashScope `qwen-plus`、OpenAI、Ollama 等） |

### `qwen-tts` 需要

| 依赖 | 安装方式 |
|------|---------|
| DashScope API key | https://dashscope.console.aliyun.com/ |
| 网络访问 `*.aliyuncs.com` | — |

## Spec Compliance

- ✅ `name` 匹配目录名
- ✅ `description` ≤ 1024 字符
- ✅ `compatibility` 声明环境与 skill 依赖
- ✅ `metadata` 含 author / version / repository / depends-on
- ✅ SKILL.md < 500 行
- ✅ references 子目录按需加载

## 校验

```bash
npx skills-ref validate ./audiobook-studio
npx skills-ref validate ./qwen-tts
```

---

## 写新 skill（quick reference）

快速创建符合规范的新 skill：

### 1. 建目录 + SKILL.md

```bash
mkdir my-skill && cd my-skill
touch SKILL.md
```

### 2. Frontmatter 模板

```yaml
---
name: my-skill                           # 必填，小写+连字符，匹配目录名
description: >-                          # 必填，≤1024 字符
  这个 skill 做什么，什么时候用。
  触发关键词：X、Y、Z。
license: MIT                             # 推荐填
compatibility: >-                        # 有环境依赖就填，≤500 字符
  需要 ffmpeg、Node.js 22+、
  以及 hyperframes skill (`npx skills add ...`)。
metadata:
  author: yourname
  version: "1.0"
  repository: "github.com/yourname/repo"
  depends-on: "hyperframes, other-skill" # 自定义字段，声明依赖的其他 skill
---

# 正文

这里写指令。保持 < 500 行 / < 5000 tokens。
详细内容放 references/ 按需加载。
```

### 3. 目录结构推荐

```
my-skill/
├── SKILL.md              # 主入口（< 500 行）
├── references/           # 详细文档（agent 按需读）
│   ├── api.md
│   └── examples.md
├── scripts/              # 可执行脚本（agent 可调用）
│   └── validate.py
└── assets/               # 模板、图片、数据文件
    └── template.json
```

### 4. 触发匹配 = description

Agent 根据 description 决定何时加载 skill。**这是最重要的字段**。

❌ 差：`description: Helps with PDFs.`
✅ 好：`description: Extract text and tables from PDF files, fill forms, merge PDFs. Use when working with PDF documents or when user mentions PDFs, forms, or document extraction.`

要点：
- 说清楚**做什么** + **什么时候用**
- 包含触发关键词（用户可能说的词）
- 用第三人称描述（"Extract..." 而非 "I will extract..."）

### 5. 声明依赖（规范没有 dependencies 字段）

两招组合用：

```yaml
# 1. compatibility 字段：给人类 + 环境检查器看
compatibility: Requires the `hyperframes` skill and ffmpeg.

# 2. metadata.depends-on：给 skill 管理工具看
metadata:
  depends-on: "hyperframes, qwen-tts"
```

在 SKILL.md 正文里也可以加一段给 agent 看的"依赖检查"指令：

```markdown
## 依赖检查（开始工作前必做）

开始执行前，确认以下 skill 已安装：
- `hyperframes`：`.claude/skills/hyperframes/SKILL.md` 应存在
- 缺失则提示用户：`npx skills add github.com/heygen-com/hyperframes`
```

### 6. 校验 + 测试

```bash
# 结构校验
npx skills-ref validate ./my-skill

# 触发测试：在新会话里说一句应该激活 skill 的话，看 agent 是否加载
```

### 规范要点速查

| 维度 | 要求 |
|------|------|
| name | 小写/数字/连字符，匹配目录名，≤64 字符 |
| description | ≤1024 字符 |
| compatibility | ≤500 字符 |
| SKILL.md 正文 | < 500 行，< 5000 tokens |
| 文件引用 | 相对路径，从 skill 目录根起算 |
| 跨 skill 依赖 | 用 `compatibility` + `metadata.depends-on` |

详细规范：https://agentskills.io/specification

