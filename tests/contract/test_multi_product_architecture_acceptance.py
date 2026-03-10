"""Architecture acceptance for the final multi-product target state.

This contract keeps the post-M87 target tree, canonical ownership, and
minimal intentional compatibility surface in sync with the architecture doc.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"
ARCHITECTURE_DOC = PROJECT_ROOT / "多产品架构调整建议.md"

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
    "core/skills/formatter.py",
    "core/skills/registry.py",
    "core/types.py",
    "platform/bootstrap.py",
    "platform/config/resolver.py",
    "platform/hooks/loader.py",
    "platform/http_api/app.py",
    "platform/http_api/auth.py",
    "platform/http_api/deps.py",
    "platform/http_api/routes/event.py",
    "platform/http_api/routes/session.py",
    "platform/http_api/sse.py",
    "platform/llm/providers/__init__.py",
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

MINIMAL_SURVIVING_SHIMS = {
    "platform.product": {
        "path": "platform/product.py",
        "canonical": "products/base.py",
        "marker": "Compatibility shim for the canonical product contract module.",
    },
    "platform.products.local_coding": {
        "path": "platform/products/local_coding.py",
        "canonical": "products/local_coding/profile.py",
        "marker": "Compatibility shim for the canonical local_coding product profile.",
    },
    "platform.products.personal_assistant": {
        "path": "platform/products/personal_assistant.py",
        "canonical": "products/personal_assistant/profile.py",
        "marker": "Compatibility shim for the canonical personal_assistant product profile.",
    },
    "platform.persistence.session.base": {
        "path": "platform/persistence/session/base.py",
        "canonical": "core/session/store.py",
        "marker": "Compatibility shim re-exporting the canonical core session store contract.",
    },
    "session.stores": {
        "path": "session/stores/__init__.py",
        "canonical": "platform/persistence/session/__init__.py",
        "marker": "Compatibility shims for platform-owned session store implementations.",
    },
    "session.stores.base": {
        "path": "session/stores/base.py",
        "canonical": "core/session/store.py",
        "marker": "Compatibility shim for the canonical platform session store contract.",
    },
    "session.stores.jsonl_store": {
        "path": "session/stores/jsonl_store.py",
        "canonical": "platform/persistence/session/jsonl_store.py",
        "marker": "Compatibility shim for the canonical platform JSONL session store.",
    },
    "session.stores.sqlite_store": {
        "path": "session/stores/sqlite_store.py",
        "canonical": "platform/persistence/session/sqlite_store.py",
        "marker": "Compatibility shim for the canonical platform SQLite session store.",
    },
    "session.entries": {
        "path": "session/entries.py",
        "canonical": "core/session/entries.py",
        "marker": "Compatibility shim re-exporting canonical core session entries.",
    },
    "session.models": {
        "path": "session/models.py",
        "canonical": "core/session/models.py",
        "marker": "Compatibility shim re-exporting canonical core session models.",
    },
    "session.manager": {
        "path": "session/manager.py",
        "canonical": "core/session/manager.py",
        "marker": "Compatibility shim re-exporting the canonical core session manager.",
    },
    "session.service": {
        "path": "session/service.py",
        "canonical": "platform/persistence/session/service.py",
        "marker": "Compatibility alias exposing canonical platform session service module.",
    },
    "session.serializers": {
        "path": "session/serializers.py",
        "canonical": "platform/persistence/session/serializers.py",
        "marker": "Compatibility shim for canonical platform session serializers.",
    },
    "hooks.loader": {
        "path": "hooks/loader.py",
        "canonical": "platform/hooks/loader.py",
        "marker": "Compatibility shim for the canonical platform hook loader.",
    },
    "hooks.session_events": {
        "path": "hooks/session_events.py",
        "canonical": "platform/hooks/session_events.py",
        "marker": "Compatibility shim for canonical platform session event contracts.",
    },
    "hooks.session_usage": {
        "path": "hooks/session_usage.py",
        "canonical": "platform/hooks/session_usage.py",
        "marker": "Compatibility shim for canonical platform session usage contracts.",
    },
    "hooks.context": {
        "path": "hooks/context.py",
        "canonical": "core/hooks/context.py",
        "marker": "Compatibility shim re-exporting canonical core hook context types.",
    },
    "hooks.registry": {
        "path": "hooks/registry.py",
        "canonical": "core/hooks/registry.py",
        "marker": "Compatibility shim re-exporting the canonical core hook registry.",
    },
    "hooks.runner": {
        "path": "hooks/runner.py",
        "canonical": "core/hooks/runner.py",
        "marker": "Compatibility shim re-exporting the canonical core hook runner.",
    },
    "hooks.types": {
        "path": "hooks/types.py",
        "canonical": "core/hooks/types.py",
        "marker": "Compatibility shim re-exporting canonical core hook type declarations.",
    },
    "skills.registry": {
        "path": "skills/registry.py",
        "canonical": "core/skills/registry.py",
        "marker": "Compatibility shim re-exporting canonical core skill discovery types.",
    },
    "skills.formatter": {
        "path": "skills/formatter.py",
        "canonical": "core/skills/formatter.py",
        "marker": "Compatibility shim re-exporting canonical core skill prompt formatting.",
    },
    "llm.factory": {
        "path": "llm/factory.py",
        "canonical": "core/llm/factory.py",
        "marker": "Compatibility shim re-exporting the canonical core LLM factory.",
    },
    "llm.interfaces": {
        "path": "llm/interfaces.py",
        "canonical": "core/llm/interfaces.py",
        "marker": "Compatibility shim re-exporting canonical core LLM interfaces.",
    },
    "llm.model_registry": {
        "path": "llm/model_registry.py",
        "canonical": "core/llm/model_registry.py",
        "marker": "Compatibility shim re-exporting canonical core LLM model metadata.",
    },
    "tools.base": {
        "path": "tools/base.py",
        "canonical": "platform/tools/base.py",
        "marker": "Compatibility shim for canonical platform tool contracts.",
    },
    "tools.constants": {
        "path": "tools/constants.py",
        "canonical": "platform/tools/constants.py",
        "marker": "Compatibility shim for canonical platform tool constants.",
    },
    "tools.registry": {
        "path": "tools/registry.py",
        "canonical": "platform/tools/registry.py",
        "marker": "Compatibility shim for the canonical platform tool registry.",
    },
    "tools.loader": {
        "path": "tools/loader.py",
        "canonical": "platform/tools/loader.py",
        "marker": "Compatibility shim for the canonical platform tool loader.",
    },
    "tools.safety": {
        "path": "tools/safety.py",
        "canonical": "platform/tools/safety.py",
        "marker": "Compatibility shim for the canonical platform tool safety module.",
    },
    "server": {
        "path": "server/__init__.py",
        "canonical": "platform/http_api/__init__.py",
        "marker": "Compatibility shim package for the canonical platform HTTP API.",
    },
    "server.app": {
        "path": "server/app.py",
        "canonical": "platform/http_api/app.py",
        "marker": "Compatibility shim for the canonical platform HTTP API app module.",
    },
    "sdk.client": {
        "path": "sdk/client.py",
        "canonical": "platform/sdk/client.py",
        "marker": "Compatibility shim for the canonical platform SDK client surface.",
    },
    "cli.commands": {
        "path": "cli/commands.py",
        "canonical": "apps/coding_cli/commands.py",
        "marker": "Compatibility facade for CLI command orchestration module.",
    },
    "cli.main": {
        "path": "cli/main.py",
        "canonical": "apps/coding_cli/main.py",
        "marker": "Console script module for launching CLI through HTTP API boundary.",
    },
    "cli.http_client": {
        "path": "cli/http_client.py",
        "canonical": "platform/sdk/client.py",
        "marker": "Compatibility shim for the shared HTTP client contract.",
    },
    "cli.release_playbook": {
        "path": "cli/release_playbook.py",
        "canonical": "apps/coding_cli/release_playbook.py",
        "marker": "Compatibility shim for the canonical apps-level CLI release playbook.",
    },
    "cli.release_observability": {
        "path": "cli/release_observability.py",
        "canonical": "apps/coding_cli/release_observability.py",
        "marker": "Compatibility shim for the canonical apps-level CLI release observability helpers.",
    },
}

REMOVED_LEGACY_PATHS = (
    "server/auth.py",
    "server/deps.py",
    "server/sse.py",
    "server/routes/__init__.py",
    "server/routes/event.py",
    "server/routes/global_routes.py",
    "server/routes/hook.py",
    "server/routes/run.py",
    "server/routes/session.py",
    "server/routes/tool.py",
    "cli/app/__init__.py",
    "cli/app/commands.py",
    "cli/context_budget.py",
    "cli/error_presenter.py",
    "cli/events/__init__.py",
    "cli/events/event_pipeline.py",
    "cli/events/repl_events.py",
    "cli/input/__init__.py",
    "cli/input/repl_commands.py",
    "cli/input/repl_input.py",
    "cli/managed_server.py",
    "cli/render/__init__.py",
    "cli/render/context_budget.py",
    "cli/render/error_presenter.py",
    "cli/render/repl_render.py",
    "cli/render/turn_usage.py",
    "cli/repl_commands.py",
    "cli/repl_events.py",
    "cli/repl_input.py",
    "cli/repl_render.py",
    "cli/repl_runtime.py",
    "cli/runtime/__init__.py",
    "cli/runtime/repl_runtime.py",
    "cli/turn_usage.py",
)

REQUIRED_DOC_SNIPPETS = (
    "## 八、M83 最终目标态验收（代码/测试/文档对齐）",
    "## 十、M87 legacy shim 截肢与最小兼容面验收",
    "### 1. M87 最小保留 compatibility surface（intentional only）",
    "### 2. 已删除的低价值 legacy shim families",
    "### 3. M87 验收测试与文档勾稽",
    "tests/contract/test_multi_product_architecture_acceptance.py",
    "tests/unit/test_platform_http_api_location.py",
    "tests/unit/test_apps_coding_cli_location.py",
    "server/auth.py",
    "server/routes/session.py",
    "cli/context_budget.py",
    "cli/events/repl_events.py",
    "cli/managed_server.py",
)


def test_architecture_doc_contains_final_target_tree_and_m87_minimal_compat_sections() -> None:
    doc = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for snippet in REQUIRED_DOC_SNIPPETS:
        assert snippet in doc, f"missing architecture acceptance snippet: {snippet}"
    for line in EXPECTED_TARGET_TREE_LINES:
        assert line in doc, f"target tree line missing from architecture doc: {line}"



def test_final_target_tree_paths_exist_in_repository() -> None:
    for relative_path in EXPECTED_EXISTING_PATHS:
        assert (SRC_ROOT / relative_path).exists(), f"missing target-state path: {relative_path}"



def test_minimal_surviving_shims_still_point_at_documented_canonical_homes() -> None:
    doc = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for shim_name, meta in MINIMAL_SURVIVING_SHIMS.items():
        shim_path = SRC_ROOT / meta["path"]
        canonical_path = SRC_ROOT / meta["canonical"]
        assert shim_path.exists(), f"missing shim path: {meta['path']}"
        assert canonical_path.exists(), f"missing canonical path for {shim_name}: {meta['canonical']}"

        source = shim_path.read_text(encoding="utf-8")
        assert meta["marker"] in source, f"shim marker drifted for {shim_name}"
        assert shim_name in doc, f"architecture doc missing shim entry: {shim_name}"
        assert meta["canonical"] in doc, f"architecture doc missing canonical target for {shim_name}"



def test_low_value_legacy_shim_families_have_been_deleted() -> None:
    doc = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for relative_path in REMOVED_LEGACY_PATHS:
        assert not (SRC_ROOT / relative_path).exists(), f"legacy shim should be deleted in M87: {relative_path}"
        assert relative_path in doc, f"architecture doc missing removed-shim note: {relative_path}"
