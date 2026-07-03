# VoxFlow Skills

[![Agent Skills Spec](https://img.shields.io/badge/Agent_Skills-spec_compliant-blue)](https://agentskills.io/specification)

从 [VoxFlow](https://github.com/imyth/VoxFlow)（Tauri 有声书桌面应用）中抽离出的 Agent Skills，让你**无需安装 VoxFlow app** 就能让 AI agent 直接完成"从大纲到有声书成品"的全流程。

符合 [Agent Skills 开放规范](https://agentskills.io/specification)（Vercel 发起），可在 Claude Code / Cursor / Windsurf / Cline 等多客户端通用。

## 📦 包含的 Skills

| Skill | 用途 | 依赖 |
|-------|------|------|
| [`audiobook-studio`](./skills/audiobook-studio/) | 多角色有声书全流程编排（大纲 → 脚本 → TTS → 视频 → 成品） | `hyperframes`、`qwen-tts`、ffmpeg、DashScope API |
| [`qwen-tts`](./skills/qwen-tts/) | 阿里云百炼 Qwen TTS API 完整文档（HTTP + WebSocket Realtime） | DashScope API key |

更详细列表见 [`skills/README.md`](./skills/README.md)。

## 🚀 安装

### 安装整个仓库（推荐）

```bash
npx skills add github.com/imyth/vox-flow-skills
```

### 单独安装某个 skill

```bash
npx skills add github.com/imyth/vox-flow-skills/skills/qwen-tts
npx skills add github.com/imyth/vox-flow-skills/skills/audiobook-studio
```

安装后 skill 会出现在项目的 `.agents/skills/` 目录，agent 在对话中会自动识别并触发。

## 🔧 外部依赖

### `audiobook-studio`

| 依赖 | 安装方式 |
|------|---------|
| `hyperframes` skill | `npx skills add github.com/heygen-com/hyperframes` |
| `ffmpeg` | `brew install ffmpeg` / `apt install ffmpeg` |
| DashScope API key | https://dashscope.console.aliyun.com/ |
| LLM API（OpenAI 兼容） | 任意（DashScope `qwen-plus`、OpenAI、Ollama 等） |

### `qwen-tts`

| 依赖 | 安装方式 |
|------|---------|
| DashScope API key | https://dashscope.console.aliyun.com/ |
| 网络访问 `*.aliyuncs.com` | — |

## 🎯 用法示例

在任何支持 Agent Skills 的 AI 编辑器里，开新会话说：

- **"帮我做一个有声书"** → 触发 `audiobook-studio`，走完 8 步流程
- **"用 Qwen TTS 合成这段话"** → 触发 `qwen-tts`，调 DashScope API

完整工作流见 [`skills/audiobook-studio/SKILL.md`](./skills/audiobook-studio/SKILL.md)。

## 🏗️ 仓库结构

```
vox-flow-skills/
├── skills/                      # 自研 skills（本仓库的核心内容）
│   ├── audiobook-studio/        # 有声书编排
│   └── qwen-tts/                # Qwen TTS API 文档
├── .agents/skills/              # 通过 npx skills 安装的第三方 skills
├── skills-lock.json             # 安装锁定（类似 package-lock.json）
└── README.md
```

## 📐 Agent Skills 规范

本仓库的 skills 符合 [Agent Skills Specification](https://agentskills.io/specification)。核心要点：

**一个 skill = 一个目录 + 一个 SKILL.md**

```
skill-name/
├── SKILL.md          # 必需：YAML frontmatter + Markdown 指令
├── scripts/          # 可选：可执行脚本（agent 可调用）
├── references/       # 可选：按需加载的详细文档
└── assets/           # 可选：模板、静态资源
```

**渐进式加载**：

| 层 | 何时加载 | 预算 |
|----|---------|------|
| Frontmatter（name + description） | 启动时（所有 skill 都加载） | ~100 tokens |
| SKILL.md 正文 | skill 被触发时 | < 5000 tokens / < 500 行 |
| references/ scripts/ 内文件 | 正文指示需要时 | 按需 |

**Frontmatter 字段**：

| 字段 | 必填 | 用途 |
|------|------|------|
| `name` | ✅ | skill ID（小写+连字符，匹配目录名，≤64 字符） |
| `description` | ✅ | **触发匹配的主机制**（agent 据此判断是否激活，≤1024 字符） |
| `license` | ❌ | 许可证 |
| `compatibility` | ❌ | 环境/依赖声明（系统包、网络、其他 skill，≤500 字符） |
| `metadata` | ❌ | 任意 key-value（author / version / depends-on 等） |
| `allowed-tools` | ❌ | 预授权工具（实验性） |

**跨 skill 依赖**：规范没有 `dependencies` 字段，用 `compatibility` + `metadata.depends-on` 组合声明。

### 校验

```bash
npx skills-ref validate ./skills/audiobook-studio
npx skills-ref validate ./skills/qwen-tts
```

### 规范资源

| 资源 | URL |
|------|-----|
| 规范全文 | https://agentskills.io/specification |
| 写 skill 最佳实践 | https://agentskills.io/skill-creation/best-practices |
| 优化 description | https://agentskills.io/skill-creation/optimizing-descriptions |
| scripts 用法 | https://agentskills.io/skill-creation/using-scripts |
| 质量评估 | https://agentskills.io/skill-creation/evaluating-skills |
| Vercel CLI 仓库 | https://github.com/vercel-labs/skills |
| 官方 skill 集合 | https://github.com/vercel-labs/agent-skills |

## 🔗 相关项目

- [VoxFlow](https://github.com/imyth/VoxFlow) — 本仓库 skills 的来源，Tauri 桌面应用版
- [hyperframes](https://github.com/heygen-com/hyperframes) — HTML→视频 渲染框架（`audiobook-studio` 依赖）

## License

MIT
