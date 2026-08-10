"""Restricted Python Workflow compiler."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from types import CodeType
from typing import Any, Mapping

from .models import WorkflowMeta, WorkflowPhase


class WorkflowCompileError(ValueError):
    """Raised when Workflow source violates the Python program contract."""


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    code: CodeType
    meta: WorkflowMeta
    filename: str


_FORBIDDEN_NODES = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal)
_FORBIDDEN_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "getattr",
    "setattr",
    "vars",
    "dir",
    "type",
    "object",
    "globals",
    "locals",
    "breakpoint",
    "input",
    "help",
    "memoryview",
}


class _PolicyVisitor(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, _FORBIDDEN_NODES):
            label = type(node).__name__.replace("Def", "").lower()
            raise WorkflowCompileError(f"{label} is not allowed in a Workflow")
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id.startswith("_"):
            raise WorkflowCompileError("private names are not allowed in a Workflow")
        if node.id in _FORBIDDEN_NAMES:
            raise WorkflowCompileError(f"{node.id} is not allowed in a Workflow")

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr.startswith("_"):
            raise WorkflowCompileError(
                "private attributes are not allowed in a Workflow"
            )
        self.generic_visit(node)


def _await_checkpoint() -> ast.Expr:
    return ast.Expr(
        value=ast.Await(
            value=ast.Call(
                func=ast.Name(id="__workflow_checkpoint__", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
        )
    )


class _CheckpointTransformer(ast.NodeTransformer):
    def __init__(self) -> None:
        self._async_depth = 0

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802
        self._async_depth += 1
        self.generic_visit(node)
        self._async_depth -= 1
        node.body.insert(0, _await_checkpoint())
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        previous_depth = self._async_depth
        self._async_depth = 0
        self.generic_visit(node)
        self._async_depth = previous_depth
        return node

    def visit_For(self, node: ast.For) -> ast.AST:  # noqa: N802
        self.generic_visit(node)
        if self._async_depth:
            node.body.append(_await_checkpoint())
        return node

    def visit_While(self, node: ast.While) -> ast.AST:  # noqa: N802
        self.generic_visit(node)
        if self._async_depth:
            node.body.append(_await_checkpoint())
        return node

    def visit_Await(self, node: ast.Await) -> ast.AST:  # noqa: N802
        self.generic_visit(node)
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "__workflow_checkpoint__"
        ):
            return node
        return ast.Await(
            value=ast.Call(
                func=ast.Name(id="__workflow_checkpoint_await__", ctx=ast.Load()),
                args=[node.value],
                keywords=[],
            )
        )


def compile_workflow(source: str, *, filename: str = "<workflow>") -> CompiledWorkflow:
    """Validate, instrument, and compile one Python Workflow source artifact."""

    try:
        tree = ast.parse(source, filename=filename, mode="exec")
    except SyntaxError as exc:
        raise WorkflowCompileError(str(exc)) from exc

    _PolicyVisitor().visit(tree)
    meta_value: Mapping[str, Any] | None = None
    main_count = 0
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name == "main":
                if not isinstance(statement, ast.AsyncFunctionDef):
                    raise WorkflowCompileError("Workflow requires async def main()")
                if statement.args.args or statement.args.kwonlyargs:
                    raise WorkflowCompileError(
                        "async def main() must not accept arguments"
                    )
                main_count += 1
            continue
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            raise WorkflowCompileError(
                "top level allows only literal assignments and function definitions"
            )
        target = (
            statement.targets[0]
            if isinstance(statement, ast.Assign)
            else statement.target
        )
        value = statement.value
        if not isinstance(target, ast.Name) or value is None:
            raise WorkflowCompileError("top-level assignment must target one name")
        try:
            literal = ast.literal_eval(value)
        except (ValueError, TypeError) as exc:
            raise WorkflowCompileError(
                "top-level values must be pure literal values"
            ) from exc
        if target.id == "meta":
            if meta_value is not None or not isinstance(literal, Mapping):
                raise WorkflowCompileError(
                    "Workflow requires exactly one literal meta mapping"
                )
            meta_value = literal
    if main_count != 1:
        raise WorkflowCompileError("Workflow requires exactly one async def main()")
    if meta_value is None:
        raise WorkflowCompileError("Workflow requires literal meta")

    meta = _parse_meta(meta_value)
    instrumented = _CheckpointTransformer().visit(tree)
    ast.fix_missing_locations(instrumented)
    return CompiledWorkflow(
        code=compile(instrumented, filename=filename, mode="exec"),
        meta=meta,
        filename=filename,
    )


def _parse_meta(value: Mapping[str, Any]) -> WorkflowMeta:
    name = value.get("name")
    description = value.get("description")
    if not isinstance(name, str) or not name.strip():
        raise WorkflowCompileError("meta.name is required")
    if not isinstance(description, str) or not description.strip():
        raise WorkflowCompileError("meta.description is required")
    when_to_use = value.get("whenToUse")
    if when_to_use is not None and not isinstance(when_to_use, str):
        raise WorkflowCompileError("meta.whenToUse must be a string")
    raw_phases = value.get("phases", ())
    if not isinstance(raw_phases, (list, tuple)):
        raise WorkflowCompileError("meta.phases must be a list")
    phases: list[WorkflowPhase] = []
    for raw in raw_phases:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("title"), str):
            raise WorkflowCompileError("each meta phase requires a title")
        detail = raw.get("detail", "")
        if not isinstance(detail, str):
            raise WorkflowCompileError("phase detail must be a string")
        phases.append(WorkflowPhase(title=raw["title"], detail=detail))
    return WorkflowMeta(
        name=name,
        description=description,
        when_to_use=when_to_use,
        phases=tuple(phases),
    )
