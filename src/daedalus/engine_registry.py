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
    config_fields: tuple[dict[str, object], ...] = ()
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


def _task_parameter_fields(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[dict[str, object], ...]:
    """Infer conservative UI metadata from literals; never evaluate source code."""
    fields: list[dict[str, object]] = []
    positional = [*fn.args.posonlyargs, *fn.args.args]
    defaults: list[ast.expr | None] = [
        None
    ] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    parameters = list(zip(positional, defaults, strict=True))
    parameters += list(zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True))
    for arg, default in parameters:
        if arg.arg == "session":
            continue
        field: dict[str, object] = {"name": arg.arg, "required": default is None}
        hint = arg.annotation.id if isinstance(arg.annotation, ast.Name) else None
        type_name = {
            "int": "integer", "float": "number", "bool": "boolean", "str": "text",
        }.get(hint, "json")
        if default is not None:
            try:
                value = ast.literal_eval(default)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                value = None
            if type(value) is bool:
                type_name = "boolean"
                field["default"] = value
            elif type(value) is int and abs(value) <= 10**12:
                type_name = "integer"
                field["default"] = value
            elif type(value) is float and abs(value) <= 10**12:
                type_name = "number"
                field["default"] = value
            elif type(value) is str and len(value) <= 200:
                type_name = "text"
                field["default"] = value
            elif (
                value is None and isinstance(default, ast.Constant)
                and default.value is None
            ):
                # Runtime defaults are not evaluated or fabricated.
                field["default"] = None
        field["type"] = type_name
        fields.append(field)
    return tuple(fields)


def _native_tasks(
    function_path: Path,
) -> dict[str, tuple[str, tuple[str, ...], tuple[dict[str, object], ...]]]:
    tasks: dict[str, tuple[str, tuple[str, ...], tuple[dict[str, object], ...]]] = {}
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
                    fields = _task_parameter_fields(fn)
                    tasks[name] = (
                        f"ikabot.function.{path.stem}",
                        tuple(str(field["name"]) for field in fields),
                        fields,
                    )
    return tasks


def supports_structured_cli(source: str | Path | None = None) -> bool:
    """Check whether the engine contains the *proposed* JSON CLI/IPC entry points.

    The backend must independently validate each task before exposing it as an
    executable operation. Presence of IPC support is not permission to dispatch.
    """
    root = locate_engine_source(source)
    ipc_file = root / "helpers" / "ipc.py"
    if not ipc_file.is_file():
        return False
    tree = _parse(ipc_file)
    declared_functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    declared_classes = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    return {"run_cli_task", "_validate_task_config"} <= declared_functions and "IPCServer" in declared_classes


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
                config_fields=task[2] if task else (),
                # Individual tasks remain unvalidated for Daedalus dispatch,
                # even though the candidate engine has a JSON CLI launcher.
                structured_cli=False,
            )
        )
    return capabilities
