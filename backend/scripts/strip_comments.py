"""Strip module docstrings and inline comments from Python files."""
import re
import sys
import tokenize
import io

SKIP_PATTERNS = ["venv", "__pycache__", "strip_comments"]

def strip_comments_and_docstrings(source: str) -> str:
    """Remove all comments and module/function/class docstrings from Python source."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return source

    result = []
    prev_toktype = tokenize.ENCODING
    last_lineno = -1
    last_col = 0

    for tok in tokens:
        token_type = tok.type
        token_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        if token_type == tokenize.COMMENT:
            # Skip all inline # comments
            continue
        elif token_type == tokenize.STRING:
            # Skip docstrings (string as first statement in module/class/function)
            if prev_toktype in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL,
                                tokenize.ENCODING, 54):  # 54 = OP for some pythons
                # Check if it's a standalone string statement (docstring)
                # We keep it if it's used as an expression (assigned, etc.)
                # Simple heuristic: if the previous meaningful token was
                # INDENT or NEWLINE, it's a docstring
                continue

        if start_line > last_lineno:
            last_col = 0

        col_diff = start_col - last_col
        if col_diff > 0:
            result.append(" " * col_diff)

        result.append(token_string)
        last_lineno = end_line
        last_col = end_col
        prev_toktype = token_type

    return "".join(result)


def clean_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    if not source.strip():
        return

    # Remove module-level triple-quoted docstrings at top of file (more reliable regex)
    # Pattern: optional whitespace, then triple-quoted string at start
    source_cleaned = re.sub(
        r'^(\s*)("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n',
        '',
        source,
        count=1,
        flags=re.MULTILINE
    )

    # Remove inline comments (# ...) but not inside strings
    lines = source_cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove trailing inline comments, preserving string contents
        # Simple approach: strip everything after # that's not in a string
        stripped = _remove_inline_comment(line)
        cleaned_lines.append(stripped)

    # Remove consecutive blank lines (max 1 blank line)
    result_lines = []
    blank_count = 0
    for line in cleaned_lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 1:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)

    result = '\n'.join(result_lines).strip() + '\n'

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"  Cleaned: {filepath}")


def _remove_inline_comment(line: str) -> str:
    """Remove inline # comment from a line, preserving strings."""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == '#' and not in_single and not in_double:
            return line[:i].rstrip()
        i += 1
    return line


import os
import glob

base = r"c:\Users\sande\OneDrive\Desktop\hackathon\backend"
py_files = glob.glob(os.path.join(base, "**", "*.py"), recursive=True)

for fp in py_files:
    if any(skip in fp for skip in SKIP_PATTERNS):
        continue
    clean_file(fp)

print(f"\nDone! Cleaned {len(py_files)} files.")
