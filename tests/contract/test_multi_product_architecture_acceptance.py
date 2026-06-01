"""Architecture acceptance for the M90 agent package rename target state."""

from importlib.util import find_spec
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
ARCHITECTURE_DOC = PROJECT_ROOT / "SPEC.md"
README = PROJECT_ROOT / "README.md"
CODING_CLI_SPEC = PROJECT_ROOT / "docs" / "CodingCLI-SPEC.md"
# feat-392-M1: docs/内核设计SPEC.md 退役（移入 docs/archive/）。内核分层 + 依赖方向 +
# 库形态（无 HTTP）是跨包架构属性，SPEC_GUIDE 判定不进单包契约层——canonical 家是顶点 SPEC.md。
# 故架构验收锚回 SPEC.md（同一份顶点既验顶层结构又验内核终态，不再读已退役的子系统 SPEC）。
KERNEL_SPEC = PROJECT_ROOT / "SPEC.md"

EXPECTED_TARGET_TREE_LINES = (
    "src/",
    "└── IM/                           # IM 前后端（独立网络服务）",
)

EXPECTED_EXISTING_PATHS = (
    "__init__.py",
    "core/agent/__init__.py",
    "core/agent/loop.py",
    "core/agent/policies.py",
    "core/agent/prompting.py",
    "core/agent/runtime.py",
    "core/agent/skill_commands.py",
    "core/agent/state.py",
    "core/agent/compaction/applier.py",
    "core/agent/compaction/planner.py",
    "core/agent/compaction/policy.py",
    "core/agent/compaction/summarizer.py",
    "core/agent/compaction/types.py",
    "core/errors.py",
    # core/events.py converted to package in refactor-387-M4-R1; use events/ paths below
    "core/hooks/context.py",
    "core/hooks/registry.py",
    "core/hooks/runner.py",
    "core/hooks/types.py",
    "core/ids.py",
    "core/events/__init__.py",  # new: events package (R1 migration)
    "core/events/hub.py",  # new: EventStreamHub in core (R1 migration)
    "core/events/types.py",  # new: RuntimeEvent types moved here (R1)
    "core/llm/factory.py",
    "core/llm/interfaces.py",
    "core/llm/model_registry.py",
    "core/observability/__init__.py",
    "core/observability/logger.py",
    "core/observability/tracing.py",
    "core/runs/__init__.py",
    "core/runs/registry.py",
    "core/session/entries.py",
    "core/session/manager.py",
    "core/session/models.py",
    "core/skills/discovery.py",
    "core/skills/formatter.py",
    "core/skills/registry.py",
    "core/types.py",
    "core/tools/base.py",
    "core/tools/registry.py",
    "platform/bootstrap.py",
    "platform/config/resolver.py",
    "platform/hooks/builtins/auto_mode_gate.py",
    "platform/hooks/builtins/default_status.py",
    "platform/hooks/builtins/realtime_stream.py",
    "platform/hooks/builtins/usage_metrics.py",
    "platform/hooks/loader.py",
    "platform/hooks/session_events.py",
    "platform/hooks/session_usage.py",
    # platform/http_api/ deleted in refactor-387-M4 (HTTP layer removed entirely)
    "platform/llm/providers/__init__.py",
    "platform/llm/providers/anthropic/client.py",
    "platform/llm/providers/anthropic/mapper.py",
    "platform/llm/providers/openai_compat/client.py",
    "platform/llm/providers/openai_compat/mapper.py",
    "platform/llm/providers/translator.py",
    "platform/persistence/session/service.py",
    "platform/product.py",
    "platform/products/local_coding.py",
    "platform/products/personal_assistant.py",
    # platform/sdk/client.py deleted in refactor-387-M1 (legacy HTTP client removed;
    # products now use agent.sdk.build_kernel in-process instead of HTTP)
    "sdk/__init__.py",  # new top-level agent.sdk surface added in refactor-387-M1
    "platform/tools/base.py",
    "platform/tools/builtins/bash.py",
    "platform/tools/builtins/edit.py",
    "platform/tools/builtins/read.py",
    "platform/tools/builtins/task.py",
    "platform/tools/builtins/write.py",
    "platform/tools/constants.py",
    "platform/tools/loader.py",
    "platform/tools/registry.py",
    "platform/tools/safety.py",
    "products/base.py",
    "products/local_coding/profile.py",
    "products/personal_assistant/profile.py",
)

EXPECTED_TOP_LEVEL_CODING_CLI_PATHS = (
    # client.py, kernel_app.py, managed_server.py, session_stream.py deleted in M4
    "commands.py",
    "main.py",
    "release_observability.py",
    "release_playbook.py",
)

REMOVED_LEGACY_ROOTS = ("apps",)

LEGACY_MODULE_ROOTS = ("nano_multiagent",)
LEGACY_DOC_SNIPPETS = (
    "src/nano_multiagent",
    "nano_multiagent.core",
    "nano_multiagent.platform",
    "nano_multiagent.products",
    "python3 -m nano_multiagent",
)
TOP_LEVEL_REQUIRED_DOC_SNIPPETS = (
    "├── agent/                        # Agent 内核库（对外只暴露 agent.sdk，进程内调用）",
    "├── coding_cli/                   # 本地编码 CLI 应用",
    "├── personal_assistant/           # 个人助手 Node Gateway",
)
# feat-392-M1: 锚回 SPEC.md（KERNEL_SPEC 退役后顶点是 canonical 家）。仍实质验三条内核终态属性：
# ① 内核四层 core/platform/products/sdk；② 依赖方向 core ↛ platform/products；
# ③ 库形态——只暴露 agent.sdk、不内置 HTTP。片段取 SPEC.md §4「agent — 执行内核」实际措辞。
KERNEL_REQUIRED_DOC_SNIPPETS = (
    # ① 内核四层
    "内部分四层（core / platform / products / sdk）",
    "└── sdk/                      # 对外面：build_kernel() → Kernel",
    # ② 依赖方向 core 不依赖 platform/products
    "`core` 纯逻辑，不依赖 `platform` / `products`",
    # ③ 库形态：只暴露 agent.sdk + 无 HTTP
    "对外**只暴露 `agent.sdk`**",
    "内核是库不是服务，**不内置任何对外网络 API**",
)
ARCHITECTURE_REQUIRED_DOC_SNIPPETS = (
    "顶层结构",
    "### agent — 执行内核",
)
END_TO_END_DOCS = {
    "architecture": ARCHITECTURE_REQUIRED_DOC_SNIPPETS
    + TOP_LEVEL_REQUIRED_DOC_SNIPPETS,
    "kernel_spec": KERNEL_REQUIRED_DOC_SNIPPETS,
}


def test_architecture_docs_describe_zero_residue_target_state() -> None:
    docs = {
        "architecture": ARCHITECTURE_DOC.read_text(encoding="utf-8"),
        "readme": README.read_text(encoding="utf-8"),
        "coding_cli_spec": CODING_CLI_SPEC.read_text(encoding="utf-8"),
        "kernel_spec": KERNEL_SPEC.read_text(encoding="utf-8"),
    }

    architecture_doc = docs["architecture"]
    for line in EXPECTED_TARGET_TREE_LINES:
        assert line in architecture_doc, (
            f"target tree line missing from architecture doc: {line}"
        )

    for doc_name, required_snippets in END_TO_END_DOCS.items():
        content = docs[doc_name]
        for snippet in required_snippets:
            assert snippet in content, f"{doc_name} missing required snippet: {snippet}"

    for doc_name, content in docs.items():
        for snippet in LEGACY_DOC_SNIPPETS:
            assert snippet not in content, (
                f"{doc_name} still references legacy path: {snippet}"
            )


def test_final_target_tree_paths_exist_and_legacy_roots_are_removed() -> None:
    for relative_path in EXPECTED_EXISTING_PATHS:
        assert (SRC_ROOT / relative_path).exists(), (
            f"missing target-state path: {relative_path}"
        )

    coding_cli_root = PROJECT_ROOT / "src" / "coding_cli"
    for relative_path in EXPECTED_TOP_LEVEL_CODING_CLI_PATHS:
        assert (coding_cli_root / relative_path).exists(), (
            f"missing top-level coding_cli path: {relative_path}"
        )

    for root_name in REMOVED_LEGACY_ROOTS:
        assert not (SRC_ROOT / root_name).exists(), (
            f"legacy nested root should be removed in M90: {root_name}"
        )


def test_removed_legacy_module_roots_are_not_importable() -> None:
    for module_name in LEGACY_MODULE_ROOTS:
        assert find_spec(module_name) is None, (
            f"removed legacy module should not be importable: {module_name}"
        )
