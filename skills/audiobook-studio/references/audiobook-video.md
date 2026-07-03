# Audiobook Video（有声书视频伴奏规范）

**核心定位**：视频是有声书的"视觉伴奏"——音频已有完整旁白，视频负责营造氛围、传递情绪。

**不是字幕**。观众从音频获取内容，视频只负责让画面好看、情绪到位。

> 本文档与 `hyperframes` skill 配合使用。生成 HTML 时遵循本文档的调性要求 + hyperframes skill 的技术规范。

---

## 内容策略

### ✅ 可以做

- 展示关键短句 / 金句 / 核心概念（每场景 1-3 个，每个 ≤ 15 字）
- 用几何图形、渐变、粒子营造氛围
- 角色名 / 地名等关键信息作为视觉亮点
- 章节标题、数字、时间线作为结构元素

### ❌ 禁止

- 把原文逐字逐句当字幕堆在画面上（观众在听音频！）
- 大段文字（超过 15 字的句子都不要）
- 静态画面（每场景必须有可见的连续运动）

---

## 视觉丰富度（重要）

画面必须**丰富、有活力、禁止空洞**：

### 元素密度

- **每场景至少 6-10 个视觉元素**（文字 + 图形 + 装饰）
- 让画面充实，不要"大片空白 + 一行小字"

### 动画速度

- 装饰元素：2-5 秒一个循环
- 主元素入场：0.5-1.2 秒
- 必须有肉眼可感知的**持续运动**——不是"看 10 秒才发现在动"的微动画
- 每个场景必须有连续运动的元素（旋转的几何体、流动的线条、脉动的光晕等）

### 元素分批入场

场景内的元素应该 **stagger**（错开入场），形成节奏感，而非同时出现。

### 具体视觉元素建议

| 类型 | 示例 |
|------|------|
| 大号关键词 | 80px+，用 slam / slide / scale 等动感入场 |
| 几何装饰 | 旋转圆环、脉动多边形、移动线条网格 |
| 背景层 | 渐变流动、radial glow 呼吸、粒子漂浮 |
| 分隔/结构 | 动态 accent lines、扩展边框、reveal 效果 |
| 数据感 | progress bar 动画、counter 计数、node 连接线 |

---

## 场景规划

### 时长节奏

- 每 **10-20 秒**一个场景（内容密集时可以更短）
- 每个场景有独特的视觉风格（不同几何主体、不同动画方向）
- **调色板全片一致**（场景间不要换色）

### 场景过渡

- 场景间**必须有过渡效果**：crossfade、wipe、blur-through 等
- **禁止跳切**

### 结尾

- 最后一个场景有淡出效果
- 其余场景只做入场动画（退场由过渡处理）

---

## 视觉设计

按 `hyperframes` skill 的 `house-style.md` 和 `video-composition.md` 规则：

1. **调色板**：根据内容情绪选择，声明 `bg` / `fg` / `accent`
2. **字体**：选择有特色的字体（避开 banned 列表：Inter / Roboto / Arial 等系统字体）
3. **主视觉**：用 `techniques.md` 中的技巧（SVG drawing、CSS 3D、kinetic type 等）
4. **节奏**：参考 `beat-direction.md`，快拍 vs 慢拍交替
5. **入场动画**：每个场景用不同方向和缓动
6. **缓动多样性**：同一场景内至少 3 种不同的 ease

---

## 时间轴同步

**关键**：每个时间轴条目对应音频的精确时间点。

```
clip 的 data-start    = 条目的 start（秒）
clip 的 data-duration = 条目的 duration（秒）
```

- 条目间的间隔必须保留
- 整个作品从 `t=0` 开始，在 `t=TOTAL_DURATION` 结束
- 多个条目可共享一个视觉场景，但每条仍需对应一个 clip 元素

---

## 技术约束（严格遵守，否则渲染失败）

### 必须

- 根元素属性：
  - `data-composition-id="ai-generated"`
  - `data-duration="{TOTAL_DURATION}"`（音频真实时长，ffprobe 测出）
  - `data-width="1920"` `data-height="1080"`（**必须**，否则 hyperframes 默认竖屏）
- GSAP timeline 必须 `paused: true`
- **同步注册** `window.__timelines['ai-generated'] = tl;`（不能放在 setTimeout / async / Promise 里）
- 所有 GSAP 代码在 `</body>` 前的 `<script>` 中**同步执行**
- 实现：
  ```js
  window.__hf = {
    duration: TOTAL_DURATION,
    seek: function(t) {
      Object.values(window.__timelines).forEach(function(tl) {
        tl.seek(t);
      });
    }
  };
  ```
- GSAP CDN: `https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js`
- 关键词字号 80px+
- `font-variant-numeric: tabular-nums` 处理数字
- `gsap.from()` 做入场
- `gsap.to()` 只用于最后场景退出
- 每个入场 tween 偏移 0.1-0.3s（不从 t=0 开始）

### 禁止

- `Math.random()`（渲染结果不稳定）
- `Date.now()`（同上）
- `repeat: -1`（无限循环，渲染器卡死）
- async timeline construction
- `@font-face`（hyperframes 无法解析外部字体）
- 任何 unmapped font name（hyperframes 编译 fatal error）

---

## 后处理 Safety-Net

**LLM 生成的 HTML 几乎一定有细节错误**。渲染前必须跑这些后处理（建议 Claude 用 Python/Node 脚本实现）：

### 1. `data-duration` 强制修正

找 `data-composition-id="ai-generated"` 元素，强制把 `data-duration` 设为**音频真实时长**（ffprobe 测出来的）。

**注意**：CSS 选择器里也有 `[data-composition-id="..."]`，要区分开——只改真实 HTML 属性。

### 2. `window.__hf.duration` 强制覆盖

LLM 经常设错 duration。在 HTML 末尾注入 safety-net script：

```html
<script>
(function() {
  window.__timelines = window.__timelines || {};
  if (!window.__timelines['ai-generated']) {
    if (typeof gsap !== 'undefined') {
      window.__timelines['ai-generated'] = gsap.timeline({ paused: true });
    } else {
      window.__timelines['ai-generated'] = {
        seek: function() {},
        duration: function() { return CORRECT_DURATION; }
      };
    }
  }
  window.__hf = window.__hf || {};
  window.__hf.duration = CORRECT_DURATION;
  if (!window.__hf.seek) {
    window.__hf.seek = function(time) {
      if (window.__timelines) {
        Object.values(window.__timelines).forEach(function(tl) {
          if (tl && typeof tl.seek === 'function') tl.seek(time);
        });
      }
    };
  }
})();
</script>
```

注入位置：`</body>` 前；如果没有 `</body>`，在 `</html>` 前；都没有就 append。

### 3. Font 清洗

Hyperframes 编译器把**任何 unmapped font name**都当 fatal error。

处理：
- 把 `var(--font-*)` 替换成真实字体（如 `'DM Sans', sans-serif`）
- 剥掉所有 `@font-face` 块
- 如果字体不在 hyperframes registry，整段 `font-family` 替换成 `sans-serif` / `serif` / `monospace`（从原值推断类别）

**推荐做法**：渲染前直接用 generic family，跳过字体映射问题。

### 4. Clip timing 校准

LLM 经常把 clip 的 `data-start` / `data-duration` 写错。

后处理：
- 找到所有 `<... class="clip" data-start="..." data-duration="...">`
- 按 proximity matching 对应到 timeline entries
- 强制修正为正确值（5 秒内算匹配，超出算装饰元素不动）

### 5. Overflow clip 截断

防止某个装饰 clip 的 `start + duration > TOTAL_DURATION`，导致渲染时长超出音频。

处理：
- 遍历所有 clip
- 如果 `start + duration > TOTAL_DURATION + 0.05`（留 50ms epsilon）
- 把 `duration` clamp 到 `TOTAL_DURATION - start`

---

## 渲染命令

```bash
# 在 video/ 目录下执行
cd video
npx hyperframes render . -c section-1.html -o section-1.mp4

# 渲染失败时：检查字体错误，跑 font 清洗后重试
```

快速起步可复制 `assets/video-starter.html` 作为模板。

渲染器用 headless Chrome 抓帧，30fps。

---

## 给 Claude 的执行流程

```
for each section in script.json.sections:
    1. 拿该 section 的所有 line，计算时间轴：
       line_1: start=0,        duration=ffprobe(line_1.mp3)
       line_2: start=line_1.end + gap_1, duration=ffprobe(line_2.mp3)
       ...
    2. 算出 section 总时长 = 最后一个 line 的 end
    3. 用 audiobook-video.md 规范 + hyperframes skill 生成 HTML
    4. 跑 5 步后处理 safety-net
    5. `npx hyperframes render` 渲染成 mp4
```

**时间轴数据示例**（传给 LLM 让它生成对应 HTML）：

```json
{
  "total_duration": 45.5,
  "entries": [
    { "content_hint": "夜幕降临，古老的城门...", "start": 0, "duration": 5.2, "character": "旁白", "section": "片头" },
    { "content_hint": "我必须在今晚离开...", "start": 6.0, "duration": 3.1, "character": "主角", "section": "片头" }
  ]
}
```

`content_hint` 是给 LLM 理解主题用的，**不要显示在视频里**（截断到 60 字符防止 LLM 把它当字幕）。
