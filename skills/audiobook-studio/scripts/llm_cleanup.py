#!/usr/bin/env python3
"""
LLM 文章整理脚本——用大模型清理格式、识别结构

把任意格式的原文（Markdown、纯文本、PDF 提取等）整理成结构化的中间格式，
供 split_article.py 的规则引擎做最终拆分。

设计原则：
  LLM 负责"理解"：格式清理、语义分段、公式转文字
  规则引擎负责"执行"：按句子切分、生成 script.json

用法:
  # 独立运行
  python llm_cleanup.py --input article.txt --output cleaned.json

  # 作为模块导入
  from llm_cleanup import llm_cleanup
  result = llm_cleanup(text)
"""

import argparse
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一个有声书脚本整理专家。你的任务是把一篇文章整理成适合 TTS（文字转语音）朗读的结构化格式。

## 你的职责

1. **清理格式**：移除所有格式标记（Markdown、HTML、LaTeX 标记等），只保留纯文本
2. **公式转文字**：把数学公式转成可读的中文描述
   - 例：`$S_{ent}=\\frac{A_{min}}{4G_N}$` → "S_ent 等于 A_min 除以 4G_N"
   - 例：`10^{120}` → "10 的 120 次方"
3. **识别结构**：识别文章的章节/section 边界，给每个 section 一个标题
4. **修复格式问题**：修复 PDF 提取的常见问题（多余换行、断词、页码残留等）
5. **保持原意**：不修改文字内容，只做格式清理和结构识别

## 输出格式

输出严格的 JSON，不要包含其他内容：

```json
{
  "title": "文章标题",
  "sections": [
    {
      "title": "第一章标题",
      "content": "整理后的纯文本。\\n\\n段落之间用两个换行分隔。\\n\\n每个段落是一整段连贯的文字。"
    },
    {
      "title": "第二章标题",
      "content": "..."
    }
  ]
}
```

## 注意事项

- 不要添加原文没有的内容
- 不要删除原文的内容（公式要转成文字，不能直接删除）
- 如果原文没有明确的章节划分，根据语义合理分段
- section 的 title 应该简短（10 字以内）
- content 中的段落用 \\n\\n 分隔
- 只输出 JSON，不要输出其他解释文字"""


def llm_cleanup(text: str, title: str = "", model: str = "") -> dict | None:
    """
    调用 LLM 整理文章格式。

    Args:
        text: 原文内容
        title: 文章标题（可选，LLM 也会尝试识别）
        model: 使用的模型名称（默认从 DASHSCOPE_LLM_MODEL 环境变量读取，否则 qwen3.7-plus）

    Returns:
        结构化字典 {"title": str, "sections": [{"title": str, "content": str}, ...]}
        如果失败返回 None
    """
    if not model:
        model = os.environ.get("DASHSCOPE_LLM_MODEL", "qwen3.7-plus")
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠ openai 包未安装，无法使用 LLM 模式", file=sys.stderr)
        return None

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("⚠ DASHSCOPE_API_KEY 未设置，无法使用 LLM 模式", file=sys.stderr)
        return None

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        user_message = text
        if title:
            user_message = f"文章标题：{title}\n\n{text}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # 低温度，输出更确定性
            response_format={"type": "json_object"},  # 强制 JSON 输出
        )

        content = response.choices[0].message.content
        if not content:
            print("⚠ LLM 返回空内容", file=sys.stderr)
            return None

        # 解析 JSON
        result = json.loads(content)

        # 验证结构
        if "sections" not in result or not isinstance(result["sections"], list):
            print("⚠ LLM 输出格式不正确：缺少 sections 字段", file=sys.stderr)
            return None

        for sec in result["sections"]:
            if "title" not in sec or "content" not in sec:
                print("⚠ LLM 输出格式不正确：section 缺少 title 或 content", file=sys.stderr)
                return None

        # 使用传入的 title 或 LLM 识别的 title
        if title:
            result["title"] = title
        elif "title" not in result:
            result["title"] = "未命名文章"

        return result

    except json.JSONDecodeError as e:
        print(f"⚠ LLM 输出不是合法 JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"⚠ LLM 调用失败: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='LLM 文章整理脚本')
    parser.add_argument('--input', required=True, help='输入文章路径')
    parser.add_argument('--output', required=True, help='输出 JSON 路径')
    parser.add_argument('--title', default='', help='文章标题（可选）')
    parser.add_argument('--model', default=os.environ.get('DASHSCOPE_LLM_MODEL', 'qwen3.7-plus'),
                        help='LLM 模型（默认 qwen3.7-plus，可通过 DASHSCOPE_LLM_MODEL 环境变量配置）')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"正在调用 LLM 整理文章...")
    result = llm_cleanup(text, title=args.title, model=args.model)

    if result is None:
        print("错误: LLM 整理失败", file=sys.stderr)
        sys.exit(1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✓ 整理完成: {len(result['sections'])} 个 section")
    print(f"✓ 输出: {args.output}")
    for sec in result['sections']:
        print(f"  - {sec['title']}: {len(sec['content'])} 字")


if __name__ == '__main__':
    main()
