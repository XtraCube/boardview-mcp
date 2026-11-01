"""Compile-check a Python file: ``python scripts/ast_check.py <path>``."""

import ast
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    source = handle.read()
try:
    ast.parse(source)
except SyntaxError as exc:
    print(f"SYNTAX {type(exc).__name__}: {exc.message} at line {exc.lineno} col {exc.col_offset}")
    print("AROUND:", repr("\n".join(source.splitlines()[max(0, exc.lineno - 3):exc.lineno + 1])))
else:
    print(f"AST-OK {path}: {len(source.splitlines())} lines")
