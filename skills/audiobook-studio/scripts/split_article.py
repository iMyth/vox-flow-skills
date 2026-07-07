#!/usr/bin/env python3
"""
文章拆分脚本——把成品文章拆成 script.json

两种模式：
  1. 纯规则模式（默认）：直接在原文上做规则拆分
  2. LLM 模式（--llm）：先调 LLM 整理格式和结构，再规则拆分

设计原则：
  每行 = 一个完整句子（以。！？结尾）。
  只在句子结束标点处断句，保持语义连贯。
  行与行之间根据标点类型和段落/章节结构给出不同长度的停顿。

用法:
  # 纯规则模式
  python split_article.py --input article.txt --output script.json

  # LLM 模式（适合非 Markdown 输入、需要语义分段）
  python split_article.py --input article.txt --output script.json --llm
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 文本清洗（纯规则模式用）
# ---------------------------------------------------------------------------

def clean_markdown(text: str) -> str:
    """清理 markdown 格式，保留可读的纯文本"""
    # 移除图片（必须在链接之前，否则残留 alt 文本）
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    # 移除链接但保留文本
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # 移除 LaTeX 块公式（多行）
    text = re.sub(r'\$\$[^$]+\$\$', '', text, flags=re.DOTALL)
    # 移除行内公式
    text = re.sub(r'\$[^$]+\$', '', text)
    # 上标数字 10^120 → 10的120次方
    text = re.sub(r'(\d+)\^(\d+)', r'\1的\2次方', text)
    # 移除 bold/italic
    text = text.replace('**', '').replace('*', '')
    # 移除引用标记
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # 合并连续空行（超过 2 个换行的压成 2 个）
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------------------------------------------------------------------
# 切句
# ---------------------------------------------------------------------------

def split_into_sentences(text: str) -> list[str]:
    """
    把一段文本切成朗读单元。

    策略：只在句子结束标点（。！？）处切分，保持每个句子语义完整。
    不在逗号/分号等处二次断开，避免破坏语义连贯性。
    """
    if not text or not text.strip():
        return []

    # 按句子结束符切分（保留标点）
    parts = re.split(r'([。！？]+)', text)

    sentences: list[str] = []
    for i in range(0, len(parts), 2):
        body = parts[i]
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        s = (body + punct).strip()
        if s:
            sentences.append(s)

    return sentences


# ---------------------------------------------------------------------------
# 停顿估算
# ---------------------------------------------------------------------------

def estimate_gap(text: str, is_para_end: bool, is_section_end: bool) -> int:
    """
    根据当前行的结束标点和所在位置估算停顿（毫秒）。

    优先级：section 结束 > 段落结束 > 标点类型
    """
    if is_section_end:
        return 2500

    last_char = text[-1] if text else ""

    if is_para_end:
        if last_char in "？！":
            return 1200
        return 900

    # 同段内
    if last_char in "？！":
        return 600
    if last_char == "。":
        return 400
    if text.endswith("——"):
        return 350
    if last_char in "，,；;":
        return 250
    if last_char in "：:":
        return 300
    return 300


# ---------------------------------------------------------------------------
# 公共：从结构化 section 数据生成 script.json
# ---------------------------------------------------------------------------

def _build_script(
    title: str,
    sections_data: list[dict],
    character: str,
    instructions: str,
) -> dict:
    """
    从结构化的 section 数据生成 script.json。

    Args:
        title: 文章标题
        sections_data: [{"title": str, "content": str}, ...]
        character: 角色名
        instructions: TTS 指令

    Returns:
        script.json 的完整字典
    """
    sections: list[dict] = []
    total_lines = 0
    line_counter = 1

    for sec_idx, sec_data in enumerate(sections_data):
        sec_title = sec_data.get("title", f"第{sec_idx + 1}部分")
        sec_content = sec_data.get("content", "").strip()

        if not sec_content:
            continue

        # 按空行分段落
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', sec_content) if p.strip()]

        lines: list[dict] = []
        for para_idx, para in enumerate(paragraphs):
            sentences = split_into_sentences(para)

            for sent_idx, sent in enumerate(sentences):
                sent = sent.strip()
                if not sent:
                    continue

                is_last_in_para = (sent_idx == len(sentences) - 1)
                is_last_in_section = (
                    para_idx == len(paragraphs) - 1 and is_last_in_para
                )

                gap = estimate_gap(sent, is_last_in_para, is_last_in_section)

                line_id = f"line_{line_counter:03d}"
                lines.append({
                    "id": line_id,
                    "text": sent,
                    "character": character,
                    "gap_after_ms": gap,
                    "instructions": instructions,
                    "duration_ms": 0,
                })

                line_counter += 1
                total_lines += 1

        if lines:
            sections.append({
                "id": f"sec_{sec_idx + 1}",
                "title": sec_title,
                "order": sec_idx,
                "lines": lines,
            })

    return {
        "title": title,
        "language": "zh-CN",
        "total_lines": total_lines,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# 纯规则模式
# ---------------------------------------------------------------------------

def split_article_rules(
    input_path: str,
    character: str,
    instructions: str,
    title: str,
) -> dict:
    """纯规则模式：直接在原文上做规则拆分"""

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取标题
    if not title:
        lines = content.split('\n')
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip()
            content = '\n'.join(lines[1:])

    if not title:
        title = Path(input_path).stem

    # 清理 markdown
    content = clean_markdown(content)

    # 按 --- 分 section
    raw_sections = re.split(r'\n\s*---+\s*\n', content)

    sections_data: list[dict] = []
    for sec_idx, raw_sec in enumerate(raw_sections):
        raw_sec = raw_sec.strip()
        if not raw_sec:
            continue

        # 提取 section 标题
        sec_lines = raw_sec.split('\n')
        sec_title = ""
        sec_content = raw_sec

        if sec_lines and sec_lines[0].startswith('##'):
            sec_title = sec_lines[0].lstrip('#').strip()
            sec_content = '\n'.join(sec_lines[1:]).strip()

        if not sec_title:
            sec_title = f"第{sec_idx + 1}部分"

        sections_data.append({"title": sec_title, "content": sec_content})

    return _build_script(title, sections_data, character, instructions)


# ---------------------------------------------------------------------------
# LLM 模式
# ---------------------------------------------------------------------------

def split_article_llm(
    input_path: str,
    character: str,
    instructions: str,
    title: str,
    model: str = "",
) -> dict | None:
    """
    LLM 模式：先调 LLM 整理，再规则拆分。
    失败时返回 None，调用方应降级到纯规则模式。
    """
    if not model:
        model = os.environ.get("DASHSCOPE_LLM_MODEL", "qwen3.7-plus")

    # 导入 llm_cleanup（同目录）
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))
    from llm_cleanup import llm_cleanup

    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 提取标题（传给 LLM 参考）
    if not title:
        lines = text.split('\n')
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip()

    print(f"正在调用 LLM ({model}) 整理文章...")
    result = llm_cleanup(text, title=title, model=model)

    if result is None:
        return None

    print(f"✓ LLM 整理完成: {len(result['sections'])} 个 section")
    for sec in result['sections']:
        print(f"  - {sec['title']}: {len(sec['content'])} 字")

    return _build_script(
        result.get("title", title or "未命名"),
        result["sections"],
        character,
        instructions,
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def split_article(
    input_path: str,
    output_path: str,
    character: str = "旁白",
    instructions: str = "",
    title: str = "",
    use_llm: bool = False,
    llm_model: str = "",
) -> None:
    """拆分文章为 script.json"""

    if not llm_model:
        llm_model = os.environ.get("DASHSCOPE_LLM_MODEL", "qwen3.7-plus")

    if use_llm:
        script = split_article_llm(input_path, character, instructions, title, llm_model)
        if script is None:
            print("⚠ LLM 模式失败，降级为纯规则模式...")
            script = split_article_rules(input_path, character, instructions, title)
    else:
        script = split_article_rules(input_path, character, instructions, title)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 拆分完成: {script['total_lines']} 行, {len(script['sections'])} 个 section")
    print(f"✓ 输出: {output_path}")

    for sec in script['sections']:
        print(f"  - {sec['title']}: {len(sec['lines'])} 行")


def main():
    parser = argparse.ArgumentParser(description='文章拆分脚本')
    parser.add_argument('--input', required=True, help='输入文章路径')
    parser.add_argument('--output', required=True, help='输出 script.json 路径')
    parser.add_argument('--character', default='旁白', help='角色名称')
    parser.add_argument('--instructions', default='', help='TTS 指令')
    parser.add_argument('--title', default='', help='文章标题（可选）')
    parser.add_argument('--llm', action='store_true',
                        help='使用 LLM 模式（先整理格式和结构，再规则拆分）')
    parser.add_argument('--llm-model', default=os.environ.get('DASHSCOPE_LLM_MODEL', 'qwen3.7-plus'),
                        help='LLM 模型名称（默认 qwen3.7-plus，可通过 DASHSCOPE_LLM_MODEL 环境变量配置）')

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"错误: 输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    split_article(
        input_path=args.input,
        output_path=args.output,
        character=args.character,
        instructions=args.instructions,
        title=args.title,
        use_llm=args.llm,
        llm_model=args.llm_model,
    )


if __name__ == '__main__':
    main()
