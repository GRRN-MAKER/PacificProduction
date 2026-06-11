#!/usr/bin/env python3
"""
PACIFIC — Source Code Obfuscation Pipeline
═══════════════════════════════════════════

Obfuscates the pacific/ package in-place (in a staging copy).
Used BEFORE PyInstaller builds the .exe and BEFORE MSIX packaging.

Obfuscation passes:
  1. Strip ALL docstrings and comments
  2. Encode string constants ≥ 6 chars as base64-decoded calls
  3. Rename function-local variables to opaque _0x## names
  4. Add copyright/anti-RE header
  5. Compile to .pyc bytecode (optional second layer)

Usage:
    # Obfuscate in-place inside a staging directory:
    python build/obfuscate.py <staging_pacific_dir>

    # Example (from project root):
    python build/obfuscate.py /tmp/pacific-build/pacific

    # Or let the build scripts call it automatically.

What is NOT obfuscated (for Python import machinery):
    - __init__.py files (kept minimal)
    - Import statements (must remain valid)
    - Class/function NAMES (must remain importable)
    - Click decorator strings (CLI help text — visible to users anyway)
"""

import ast
import base64
import os
import sys
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────

# Minimum string length to obfuscate (shorter strings stay readable)
MIN_STRING_LEN = 6

# Variables that must NEVER be renamed (Python builtins, framework names)
PROTECTED_NAMES = frozenset({
    # Python builtins
    "self", "cls", "args", "kwargs", "super",
    "True", "False", "None",
    "print", "len", "range", "enumerate", "zip", "map", "filter",
    "str", "int", "float", "bool", "bytes", "dict", "list", "tuple", "set",
    "type", "isinstance", "getattr", "setattr", "hasattr", "delattr",
    "open", "input", "format", "repr", "sorted", "reversed",
    "min", "max", "sum", "abs", "round", "any", "all", "next", "iter",
    "os", "sys", "json", "re", "Path", "logging",
    "asyncio", "subprocess", "ctypes", "struct", "zlib",
    # Framework / library names that must survive
    "click", "rich", "requests", "Console", "Panel", "Table", "Text",
    "Markdown", "Syntax", "Spinner", "Live",
    "console", "logger",
    # Exception names
    "Exception", "ValueError", "TypeError", "KeyError", "AttributeError",
    "ImportError", "RuntimeError", "FileNotFoundError", "OSError",
    "EOFError", "KeyboardInterrupt",
})

# Files to SKIP obfuscation entirely (e.g., __init__.py is auto-handled)
SKIP_FILES = {"__init__.py"}

# Strings that must NOT be obfuscated (Click help text, format specs, etc.)
# We detect these by context — strings used in decorators are kept.
PROTECTED_STRING_PREFIXES = (
    # Click decorator arguments — user-visible help text
    "Usage:",
    "pacific",
    # Format strings with {} are risky to obfuscate
)

HEADER = (
    "# -*- coding: utf-8 -*-\n"
    "# PACIFIC (c) 2024-2026 GRRN. All rights reserved.\n"
    "# This software is proprietary and confidential.\n"
    "# Unauthorized copying, decompilation, or reverse engineering\n"
    "# is strictly prohibited under applicable law.\n"
    "import base64 as _b;_d=_b.b64decode\n"
)


# ── AST Passes ───────────────────────────────────────────────────────

def strip_docstrings(tree: ast.AST) -> ast.AST:
    """Pass 1: Remove all docstrings from modules, classes, and functions."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            if (node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0] = ast.Pass()
    return tree


def mark_strings_for_encoding(tree: ast.AST) -> ast.AST:
    """Pass 2a: Mark string constants for base64 encoding.

    We tag each ast.Constant node with `_obfuscated_b64` if it should
    be replaced with a `_d("...").decode()` call.

    IMPORTANT: We SKIP strings inside f-strings (JoinedStr nodes) because
    ast.unparse() cannot handle Call nodes inside JoinedStr — it raises
    "Unexpected node inside JoinedStr".
    """
    # Collect positions of strings that must NOT be encoded:
    # 1. Strings inside decorators (Click help text)
    # 2. Strings inside f-strings (JoinedStr) — ast.unparse limitation
    protected_ids = set()

    for node in ast.walk(tree):
        # Protect decorator strings
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for deco in node.decorator_list:
                for sub in ast.walk(deco):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        protected_ids.add(id(sub))

        # Protect ALL constants inside f-strings (JoinedStr)
        if isinstance(node, ast.JoinedStr):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    protected_ids.add(id(sub))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value

            # Skip: protected, too short, empty, or whitespace-only
            if (id(node) in protected_ids
                    or len(val) < MIN_STRING_LEN
                    or not val.strip()):
                continue

            # Skip: pure format strings like "{}" or "{key}"
            stripped = val.replace("{", "").replace("}", "").replace("%", "")
            if not stripped.strip():
                continue

            # Skip: single-character repeated (e.g., "─────")
            if len(set(val)) <= 2:
                continue

            # Encode
            encoded = base64.b64encode(val.encode("utf-8")).decode("ascii")
            node._obfuscated_b64 = encoded

    return tree


class StringEncoder(ast.NodeTransformer):
    """Pass 2b: Replace marked string constants with _d("b64").decode()."""

    def visit_Constant(self, node):
        b64 = getattr(node, "_obfuscated_b64", None)
        if b64:
            # Build: _d("b64_string").decode()
            return ast.Call(
                func=ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id="_d", ctx=ast.Load()),
                        args=[ast.Constant(value=b64)],
                        keywords=[],
                    ),
                    attr="decode",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
        return node


def rename_local_variables(tree: ast.AST) -> ast.AST:
    """Pass 3: Rename function-local variables to opaque names.

    IMPORTANT: We skip functions decorated with Click decorators
    (@cli.command, @click.argument, @click.option, etc.) because
    Click uses parameter names for keyword argument matching.
    Renaming them breaks the CLI.
    """
    counter = [0]
    name_map = {}

    def get_mangled(original: str) -> str:
        """Generate an opaque variable name."""
        if original.startswith("_") or original in PROTECTED_NAMES:
            return original
        if original not in name_map:
            counter[0] += 1
            name_map[original] = f"_0x{counter[0]:02x}"
        return name_map[original]

    def rename_in_scope(func_node, old_name, new_name):
        """Rename all uses of a variable within a function."""
        for child in ast.walk(func_node):
            if isinstance(child, ast.Name) and child.id == old_name:
                child.id = new_name
            elif isinstance(child, ast.arg) and child.arg == old_name:
                child.arg = new_name

    def _has_click_decorator(func_node):
        """Check if a function has Click decorators (command, argument, option)."""
        for deco in func_node.decorator_list:
            deco_str = ast.dump(deco)
            # Match: @cli.command, @click.command, @click.argument,
            #        @click.option, @click.group, @click.pass_context
            if any(kw in deco_str for kw in (
                "command", "argument", "option", "group",
                "pass_context", "version_option",
            )):
                return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip Click-decorated functions — parameter names are significant
            if _has_click_decorator(node):
                continue

            # Rename function parameters (except self/cls)
            for arg in node.args.args:
                if arg.arg not in PROTECTED_NAMES:
                    new_name = get_mangled(arg.arg)
                    if new_name != arg.arg:
                        rename_in_scope(node, arg.arg, new_name)
                        arg.arg = new_name

    return tree


# ── Main Pipeline ────────────────────────────────────────────────────

def obfuscate_file(filepath: Path) -> bool:
    """Obfuscate a single .py file in-place.

    Returns True if successful, False if skipped/failed.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        print(f"    ⚠️  {filepath.name} — syntax error, kept as-is: {e}")
        return False

    # Apply passes
    tree = strip_docstrings(tree)
    tree = mark_strings_for_encoding(tree)
    tree = StringEncoder().visit(tree)
    tree = rename_local_variables(tree)
    ast.fix_missing_locations(tree)

    # Regenerate source from AST
    try:
        obfuscated = ast.unparse(tree)
    except Exception as e:
        print(f"    ⚠️  {filepath.name} — unparse failed, kept as-is: {e}")
        return False

    # Write obfuscated source with header
    filepath.write_text(HEADER + obfuscated, encoding="utf-8")
    return True


def obfuscate_package(pkg_dir: Path) -> int:
    """Obfuscate all .py files in a package directory.

    Returns the number of files obfuscated.
    """
    if not pkg_dir.is_dir():
        print(f"❌ Not a directory: {pkg_dir}")
        return 0

    py_files = [
        f for f in pkg_dir.rglob("*.py")
        if f.name not in SKIP_FILES and not f.name.startswith("._")
    ]

    print(f"\n🔒  Obfuscating {len(py_files)} source files in {pkg_dir}/\n")

    count = 0
    for py_file in sorted(py_files):
        rel = py_file.relative_to(pkg_dir.parent)
        if obfuscate_file(py_file):
            size_kb = py_file.stat().st_size / 1024
            print(f"    🔒 {rel} ({size_kb:.1f} KB)")
            count += 1
        else:
            print(f"    ⏭  {rel} (skipped)")

    # Minimize __init__.py files in subpackages
    for init in pkg_dir.rglob("__init__.py"):
        if init.parent == pkg_dir:
            # Root __init__.py — strip docstrings but keep exports
            try:
                source = init.read_text(encoding="utf-8")
                tree = ast.parse(source)
                tree = strip_docstrings(tree)
                ast.fix_missing_locations(tree)
                obfuscated = ast.unparse(tree)
                init.write_text(
                    "# PACIFIC (c) 2024-2026 GRRN\n" + obfuscated,
                    encoding="utf-8",
                )
            except Exception:
                pass
        else:
            # Subpackage __init__.py — make it a bare stub
            init.write_text("# (c) GRRN\n")

    print(f"\n    ✅ Obfuscated {count}/{len(py_files)} files")
    print(f"    🛡️  Docstrings stripped | Variables renamed | Strings base64-encoded")

    return count


# ── CLI Entry Point ──────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python build/obfuscate.py <pacific_package_dir>")
        print("\nExample:")
        print("  python build/obfuscate.py /tmp/pacific-build/pacific")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"❌ Path does not exist: {target}")
        sys.exit(1)

    count = obfuscate_package(target)
    if count == 0:
        print("⚠️  No files were obfuscated!")
        sys.exit(1)

    # Verify all obfuscated files are valid Python
    print("\n🔍  Verifying obfuscated files compile...")
    errors = 0
    for py_file in target.rglob("*.py"):
        if py_file.name.startswith("._"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            compile(source, str(py_file), "exec")
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"    ❌ {py_file.name}: {e}")
            errors += 1

    if errors:
        print(f"\n❌ {errors} file(s) have syntax errors after obfuscation!")
        sys.exit(1)

    print(f"    ✅ All {count} obfuscated files compile cleanly")
    print("\n═══════════════════════════════════════════════════")
    print("  🛡️  OBFUSCATION COMPLETE")
    print("═══════════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
