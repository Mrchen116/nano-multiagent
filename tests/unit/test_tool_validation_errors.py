"""Regression tests for tool argument validation error messages (bugfix-468-M3).

These tests pin the CC-style field-named error messages produced by
``_validate_args`` / ``_validate_value`` while keeping the ``details`` dict
shape unchanged for programmatic consumers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.tools.base import (
    set_tool_safety_factory,
    set_tool_safety_config_factory,
)
from agent.core.tools.registry import _validate_args, ToolRegistry
from agent.platform.tools.base import ToolContext
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class _MultiIssueTool:
    name = "multi_issue"
    description = "Demo tool with several validation rules"
    input_schema = {
        "type": "object",
        "properties": {
            "required_a": {"type": "string"},
            "required_b": {"type": "integer"},
            "optional_c": {"type": "boolean"},
        },
        "required": ["required_a", "required_b"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        return args


class _LoadSkillsTool:
    name = "load_skills"
    description = "Bootstrap tool"
    input_schema = {
        "type": "object",
        "properties": {
            "load_skills": {"type": "array"},
        },
        "required": ["load_skills"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        return args


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    ctx = ToolContext.create(repo_root=tmp_path)
    reg = ToolRegistry(context=ctx)
    reg.register(_MultiIssueTool())
    reg.register(_LoadSkillsTool())
    return reg


def _tool_error_message(name: str, args: dict, schema: dict) -> str:
    with pytest.raises(ToolError) as exc_info:
        _validate_args(name=name, args=args, schema=schema)
    return str(exc_info.value)


def test_single_missing_field_lists_parameter_name() -> None:
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": True,
    }
    message = _tool_error_message("echo", {}, schema)

    assert "echo failed due to the following issue:" in message
    assert "The required parameter `text` is missing" in message


def test_multiple_missing_fields_each_on_own_line() -> None:
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
        "additionalProperties": True,
    }
    message = _tool_error_message("demo", {}, schema)

    assert "demo failed due to the following issues:" in message
    assert "The required parameter `a` is missing" in message
    assert "The required parameter `b` is missing" in message
    assert message.index("`a`") < message.index("`b`")


def test_missing_details_dict_unchanged() -> None:
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": True,
    }
    with pytest.raises(ToolError) as exc_info:
        _validate_args(name="echo", args={}, schema=schema)

    assert exc_info.value.details["missing"] == ["text"]


def test_unexpected_field_lists_parameter_name() -> None:
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    message = _tool_error_message("echo", {"text": "hi", "extra": 1}, schema)

    assert "echo failed due to the following issue:" in message
    assert "An unexpected parameter `extra` was provided" in message


def test_multiple_unexpected_fields_each_on_own_line() -> None:
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    message = _tool_error_message(
        "echo", {"text": "hi", "extra_a": 1, "extra_b": 2}, schema
    )

    assert "echo failed due to the following issues:" in message
    assert "An unexpected parameter `extra_a` was provided" in message
    assert "An unexpected parameter `extra_b` was provided" in message


def test_unexpected_details_dict_unchanged() -> None:
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    with pytest.raises(ToolError) as exc_info:
        _validate_args(
            name="echo", args={"text": "hi", "extra": 1}, schema=schema
        )

    assert exc_info.value.details["unknown"] == ["extra"]


@pytest.mark.parametrize(
    "value, expected, provided",
    [
        (123, "string", "integer"),
        ("not a number", "number", "string"),
        (3.14, "integer", "number"),
        ("not bool", "boolean", "string"),
        ("not array", "array", "string"),
    ],
)
def test_type_mismatch_lists_field_and_types(
    value: object, expected: str, provided: str
) -> None:
    schema = {
        "type": "object",
        "properties": {"field": {"type": expected}},
        "required": [],
        "additionalProperties": True,
    }
    message = _tool_error_message("demo", {"field": value}, schema)

    assert "demo failed due to the following issue:" in message
    assert (
        f"The parameter `field` type is expected as `{expected}` but provided as `{provided}`"
        in message
    )


def test_type_mismatch_details_dict_unchanged() -> None:
    schema = {
        "type": "object",
        "properties": {"field": {"type": "string"}},
        "required": [],
        "additionalProperties": True,
    }
    with pytest.raises(ToolError) as exc_info:
        _validate_args(name="demo", args={"field": 123}, schema=schema)

    assert exc_info.value.details["field"] == "field"
    assert exc_info.value.details["expected"] == "string"


def test_load_skills_special_case_retained() -> None:
    schema = {
        "type": "object",
        "properties": {"load_skills": {"type": "array"}},
        "required": ["load_skills"],
        "additionalProperties": False,
    }
    with pytest.raises(ToolError) as exc_info:
        _validate_args(name="load_skills", args={}, schema=schema)

    assert str(exc_info.value) == "missing required argument: load_skills"
    assert exc_info.value.details["missing"] == ["load_skills"]


def test_registry_execute_surface_same_messages(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(registry.execute("multi_issue", {"required_a": 123, "required_b": 1}))

    message = str(exc_info.value)
    assert "multi_issue failed due to the following issue:" in message
    assert "The parameter `required_a` type is expected as `string` but provided as `integer`" in message


def test_registry_execute_multiple_missing(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(registry.execute("multi_issue", {}))

    message = str(exc_info.value)
    assert "multi_issue failed due to the following issues:" in message
    assert "The required parameter `required_a` is missing" in message
    assert "The required parameter `required_b` is missing" in message
