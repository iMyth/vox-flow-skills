#!/usr/bin/env python3
"""
script.json 校验器
检查：
  1. 所有 character 字段都在 characters.json 中
  2. 每行 text ≤ 200 中文字符
  3. line_id 唯一且符合命名规则
  4. gap_after_ms 存在且合理
  5. 总行数预警

用法:
  python validate_script.py --project-dir my-audiobook
  python validate_script.py --script script.json --chars characters.json
"""

import argparse
import json
import os
import re
import sys


def validate(script_path: str, chars_path: str) -> list[str]:
    """返回错误/警告列表。空列表表示通过。"""
    errors = []
    warnings = []

    # 加载数据
    with open(script_path) as f:
        script = json.load(f)

    char_names = set()
    if os.path.exists(chars_path):
        with open(chars_path) as f:
            for c in json.load(f):
                char_names.add(c["name"])
    else:
        warnings.append(f"characters.json 不存在: {chars_path}（跳过角色名校验）")

    # 校验 sections 结构
    if "sections" not in script:
        errors.append("script.json 缺少顶层 'sections' 字段")
        return errors

    seen_ids = set()
    total_lines = 0
    id_pattern = re.compile(r"^sec_\d+_line_\d+$")

    for section in script["sections"]:
        sec_id = section.get("id", "?")
        if "lines" not in section:
            errors.append(f"section '{sec_id}' 缺少 'lines' 字段")
            continue

        for i, line in enumerate(section["lines"]):
            total_lines += 1
            line_id = line.get("id", f"{sec_id}_line_{i+1}")

            # ID 唯一性
            if line_id in seen_ids:
                errors.append(f"重复 line_id: '{line_id}'")
            seen_ids.add(line_id)

            # ID 命名规则
            if not id_pattern.match(line_id):
                warnings.append(f"line_id 不符合命名规则: '{line_id}'（建议: sec_N_line_M）")

            # 角色名
            char = line.get("character", "")
            if char_names and char not in char_names:
                errors.append(f"行 '{line_id}' 的角色 '{char}' 不在 characters.json 中")

            # 文本长度
            text = line.get("text", "")
            char_count = len(text)
            if char_count > 200:
                errors.append(f"行 '{line_id}' 文本过长: {char_count} 字符（上限 200）")
            elif char_count > 180:
                warnings.append(f"行 '{line_id}' 文本接近上限: {char_count} 字符")

            if not text.strip():
                errors.append(f"行 '{line_id}' 文本为空")

            # gap_after_ms
            gap = line.get("gap_after_ms")
            if gap is None:
                warnings.append(f"行 '{line_id}' 缺少 gap_after_ms（将使用默认 500ms）")
            elif not isinstance(gap, (int, float)) or gap < 0:
                errors.append(f"行 '{line_id}' 的 gap_after_ms 无效: {gap}")

            # instructions（非必填）
            if "instructions" not in line:
                pass  # 可选字段，不报错

    # 总行数预警
    if total_lines > 100:
        warnings.append(f"总行数 {total_lines} > 100，TTS 耗时预计 {total_lines * 2} 秒+")
    elif total_lines > 50:
        warnings.append(f"总行数 {total_lines}，TTS 耗时预计 {total_lines * 2} 秒+")

    return errors + [f"[WARN] {w}" for w in warnings]


def main():
    parser = argparse.ArgumentParser(description="校验 script.json")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--script", default="script.json", help="script.json 路径")
    parser.add_argument("--chars", default="characters.json", help="characters.json 路径")
    args = parser.parse_args()

    if args.project_dir:
        base = args.project_dir
        if args.script == "script.json":
            args.script = os.path.join(base, "script.json")
        if args.chars == "characters.json":
            args.chars = os.path.join(base, "characters.json")

    results = validate(args.script, args.chars)

    errors = [r for r in results if not r.startswith("[WARN]")]
    warns = [r for r in results if r.startswith("[WARN]")]

    if errors:
        print(f"✗ {len(errors)} 个错误:")
        for e in errors:
            print(f"  - {e}")
    if warns:
        print(f" {len(warns)} 个警告:")
        for w in warns:
            print(f"  - {w}")
    if not results:
        print("✓ script.json 校验通过")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
