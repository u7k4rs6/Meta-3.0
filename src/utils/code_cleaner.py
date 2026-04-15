"""
src/utils/code_cleaner.py
Code post-processing utilities consolidated from AutoType.py,
general.py, and multifile_autotype.py.
"""
from __future__ import annotations

import re


def strip_code_fences(text: str) -> str:
    """Remove leading/trailing ``` fences from model output."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def strip_comments(code: str) -> str:
    """Remove all single-line and block comments from code."""
    clean = []
    for line in code.splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith("//"):
            continue
        if s.startswith("*") or s.startswith("/*") or s == "*/":
            continue
        line = re.sub(r'\s*//(?![\'"])[^\n]*', "", line)
        line = re.sub(r'(?<![\'"\w])#[^\n]*', "", line)
        clean.append(line.rstrip())
    return "\n".join(l for l in clean if l.strip() != "" or l == "")


def normalize_indentation(code: str) -> str:
    """Replace all tabs with 4-space indentation."""
    lines = []
    for line in code.splitlines():
        line = line.replace("\t", "    ")
        stripped   = line.lstrip(" ")
        raw_spaces = len(line) - len(stripped)
        level      = round(raw_spaces / 4)
        lines.append("    " * level + stripped)
    return "\n".join(lines)


def clean_code_response(raw: str) -> str:
    """Full pipeline: strip fences → strip comments → normalize indent."""
    code = strip_code_fences(raw.strip())
    code = strip_comments(code)
    code = normalize_indentation(code)
    return code.strip()
