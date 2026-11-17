"""Offline inventory of public IkaBot menu actions and background tasks.

Only Python AST files are read; importing IkaBot modules or logging into a game
session is deliberately avoided. This is an inspection tool, not a task API.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path


class EngineNotFoundError(FileNotFoundError):
    """The public IkaBot source package cannot be located."""


@dataclass(frozen=True)
class EngineCapability:
    name: str
    kind: str
    module: str
    menu_codes: tuple[int, ...]
    parameters: tuple[str, ...]
    structured_cli: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def locate_engine_source(source: str | Path | None = None) -> Path:
    """Locate the engine package without executing its imports or game code."""
    candidates: list[Path] = []
    if source is not None:
        candidates.append(Path(source).expanduser())
    else:
        # Editable development checkout, before the separate engine is installed.
        candidates.append(Path(__file__).resolve().parents[2] / "engine" / "ikabot")
        spec = importlib.util.find_spec("ikabot")
        if spec and spec.submodule_search_locations:
            candidates.extend(Path(p) for p in spec.submodule_search_locations)

    for candidate in candidates:
        # Accept either the vendored distribution root or its package directory.
        for path in (candidate, candidate / "ikabot"):
            if (path / "command_line.py").is_file() and (path / "function").is_dir():
                return path.resolve()
    raise EngineNotFoundError("IkaBot source was not found; install engine/ikabot or pass --source")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _menu_operations(command_line: ast.Module) -> dict[str, list[int]]:
    operations: dict[str, list[int]] = {}
    for node in ast.walk(command_line):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "menu_actions"
                   for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, int)
                and isinstance(value, ast.Name)
            ):
                operations.setdefault(value.id, []).append(key.value)
    return operations


def _module_imports(command_line: ast.Module) -> dict[str, str]:
    modules: dict[str, str] = {}
    for node in ast.walk(command_line):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for entry in node.names:
            alias = entry.asname or entry.name
            modules[alias] = node.module
    return modules


def _native_tasks(function_path: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    tasks: dict[str, tuple[str, tuple[str, ...]]] = {}
    for path in sorted(function_path.glob("*.py")):
        tree = _parse(path)
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in fn.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "task"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    name = decorator.args[0].value
                    params = tuple(arg.arg for arg in fn.args.args if arg.arg != "session")
                    tasks[name] = (f"ikabot.function.{path.stem}", params)
    return tasks


def inspect_engine(source: str | Path | None = None) -> list[EngineCapability]:
    """Produce a deterministic, honest menu/task inventory from source code."""
    root = locate_engine_source(source)
    tree = _parse(root / "command_line.py")
    menu = _menu_operations(tree)
    imports = _module_imports(tree)
    tasks = _native_tasks(root / "function")
    capabilities: list[EngineCapability] = []
    for name in sorted(set(menu) | set(tasks), key=str.casefold):
        task = tasks.get(name)
        capabilities.append(
            EngineCapability(
                name=name,
                kind="background_task" if task else "interactive_menu",
                module=task[0] if task else imports.get(name, "unknown"),
                menu_codes=tuple(sorted(menu.get(name, []))),
                parameters=task[1] if task else (),
                # Public stable IkaBot 7.7.2 only supports legacy predetermined
                # input. An explicit JSON API is proposed but not merged.
                structured_cli=False,
            )
        )
    return capabilities
