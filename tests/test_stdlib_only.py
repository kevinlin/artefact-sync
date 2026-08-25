from __future__ import annotations

import ast
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "scripts"

# sys.stdlib_module_names is 3.10+, and the floor is 3.9, so the allowlist is explicit.
ALLOWED = {
    "__future__", "argparse", "collections", "contextlib", "dataclasses", "datetime",
    "difflib", "fnmatch", "hashlib", "html", "http", "io", "json", "os", "pathlib",
    "re", "shutil", "string", "subprocess", "sys", "tempfile", "textwrap", "time",
    "typing", "urllib",
}

# The modules import each other by bare name, so every sibling counts as allowed.
ALLOWED |= {path.stem for path in PACKAGE.glob("*.py")}


class StdlibOnlyTests(unittest.TestCase):
    def test_every_module_imports_only_stdlib(self) -> None:
        offenders = []
        for path in sorted(PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]] if node.level == 0 else []
                else:
                    continue
                offenders += [
                    f"{path.name}:{node.lineno} {n}" for n in names if n and n not in ALLOWED
                ]
        self.assertEqual([], offenders)

    def test_every_module_has_future_annotations(self) -> None:
        missing = [
            path.name
            for path in sorted(PACKAGE.rglob("*.py"))
            if "from __future__ import annotations" not in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], missing)
