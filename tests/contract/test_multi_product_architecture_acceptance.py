"""Architecture acceptance for the M88 zero-residue target state."""

from importlib.util import find_spec
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"
ARCHITECTURE_DOC = PROJECT_ROOT / "多产品架构调整建议.md"
README = PROJECT_ROOT / "README.md"
CODING_CLI_SPEC = PROJECT_ROOT / "docs" / "CodingCLI-SPEC.md"
KERNEL_SPEC = PROJECT_ROOT / "docs" / "内核设计SPEC.md"

EXPECTED_TARGET_TREE_LINES = (
    "src/",
    "├── nano_multiagent/",
    "│   ├── core/",
    "│   │   ├── errors.py",
    "│   │   ├── events.py",
    "│   │   ├── hooks/",
    "│   │   ├── ids.py",
    "│   │   ├── llm/",
    "│   │   ├── session/",
    "│   │   ├── skills/",
    "│   │   └── types.py",
    "│   ├── platform/",
    "│   │   ├── bootstrap.py",
    "│   │   ├── config/",
    "│   │   ├── hooks/",
    "│   │   ├── http_api/",
    "│   │   ├── llm/providers/",
    "│   │   ├── persistence/session/",
    "│   │   ├── product.py",
    "│   │   ├── products/",
    "│   │   ├── sdk/",
    "│   │   └── tools/",
    "│   ├── products/",
    "│   │   ├── base.py",
    "│   │   ├── local_coding/",
    "│   │   └── personal_assistant/",
    "│   └── apps/",
    "│       └── coding_cli/",
)

EXPECTED_EXISTING_PATHS = (
    "core/errors.py",
    "core/events.py",
    "core/hooks/context.py",
    "core/hooks/registry.py",
    "core/hooks/runner.py",
    "core/hooks/types.py",
    "core/ids.py",
    "core/llm/factory.py",
    "core/llm/interfaces.py",
    "core/llm/model_registry.py",
    "core/session/entries.py",
    "core/session/manager.py",
    "core/session/models.py",
    "core/session/store.py",
    "core/skills/discovery.py",
    "core/skills/formatter.py",
    "core/skills/registry.py",
    "core/types.py",
    "platform/bootstrap.py",
    "platform/config/resolver.py",
    "platform/hooks/builtins/bash_risk_gate.py",
    "platform/hooks/builtins/default_status.py",
    "platform/hooks/builtins/realtime_stream.py",
    "platform/hooks/builtins/usage_metrics.py",
    "platform/hooks/loader.py",
    "platform/hooks/session_events.py",
    "platform/hooks/session_usage.py",
    "platform/http_api/app.py",
    "platform/http_api/deps.py",
    "platform/http_api/routes/event.py",
    "platform/http_api/routes/session.py",
    "platform/http_api/sse.py",
    "platform/llm/providers/__init__.py",
    "platform/llm/providers/anthropic/client.py",
    "platform/llm/providers/anthropic/mapper.py",
    "platform/llm/providers/openai_compat/client.py",
    "platform/llm/providers/openai_compat/mapper.py",
    "platform/llm/providers/translator.py",
    "platform/persistence/session/base.py",
    "platform/persistence/session/jsonl_store.py",
    "platform/persistence/session/serializers.py",
    "platform/persistence/session/service.py",
    "platform/persistence/session/sqlite_store.py",
    "platform/product.py",
    "platform/products/local_coding.py",
    "platform/products/personal_assistant.py",
    "platform/sdk/client.py",
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
    "apps/coding_cli/client.py",
    "apps/coding_cli/commands.py",
    "apps/coding_cli/main.py",
    "apps/coding_cli/managed_server.py",
    "apps/coding_cli/release_observability.py",
    "apps/coding_cli/release_playbook.py",
)

REMOVED_LEGACY_ROOTS = (
    "cli",
    "server",
    "session",
    "hooks",
    "skills",
    "llm",
    "tools",
    "sdk",
)

LEGACY_MODULE_ROOTS = tuple(f"nano_multiagent.{name}" for name in REMOVED_LEGACY_ROOTS)
LEGACY_DOC_SNIPPETS = LEGACY_MODULE_ROOTS + (
    "uvicorn nano_multiagent.server.app:app --reload",
    "python3 -m nano_multiagent.cli.main",
)
REQUIRED_DOC_SNIPPETS = (
    "## 十、M88 零残留 canonicalization 验收",
    "legacy package roots 已物理删除",
    "nano_multiagent.platform.http_api.app:app",
    "python3 -m nano_multiagent.apps.coding_cli.main",
    "tests/contract/test_multi_product_architecture_acceptance.py",
    "tests/unit/test_platform_http_api_location.py",
    "tests/unit/test_apps_coding_cli_location.py",
)


def test_architecture_docs_describe_zero_residue_target_state() -> None:
    docs = {
        "architecture": ARCHITECTURE_DOC.read_text(encoding="utf-8"),
        "readme": README.read_text(encoding="utf-8"),
        "coding_cli_spec": CODING_CLI_SPEC.read_text(encoding="utf-8"),
        "kernel_spec": KERNEL_SPEC.read_text(encoding="utf-8"),
    }

    architecture_doc = docs["architecture"]
    for snippet in REQUIRED_DOC_SNIPPETS:
        assert snippet in architecture_doc, f"missing architecture acceptance snippet: {snippet}"
    for line in EXPECTED_TARGET_TREE_LINES:
        assert line in architecture_doc, f"target tree line missing from architecture doc: {line}"

    for doc_name, content in docs.items():
        for snippet in LEGACY_DOC_SNIPPETS:
            assert snippet not in content, f"{doc_name} still references legacy path: {snippet}"



def test_final_target_tree_paths_exist_and_legacy_roots_are_removed() -> None:
    for relative_path in EXPECTED_EXISTING_PATHS:
        assert (SRC_ROOT / relative_path).exists(), f"missing target-state path: {relative_path}"

    for root_name in REMOVED_LEGACY_ROOTS:
        assert not (SRC_ROOT / root_name).exists(), f"legacy root should be removed in M88: {root_name}"



def test_removed_legacy_module_roots_are_not_importable() -> None:
    for module_name in LEGACY_MODULE_ROOTS:
        assert find_spec(module_name) is None, f"removed legacy module should not be importable: {module_name}"
