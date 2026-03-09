"""Architecture acceptance for the final multi-product target state.

This contract keeps the post-M83 target tree, canonical ownership, and
intentional compatibility shim inventory in sync with the architecture document.
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
    "platform/persistence/session/sqlite_store.py",
    "platform/product.py",
    "platform/products/local_coding.py",
    "platform/products/personal_assistant.py",
    "platform/sdk/client.py",
    "platform/tools/loader.py",
    "platform/tools/safety.py",
    "products/base.py",
    "products/local_coding/profile.py",
    "products/personal_assistant/profile.py",
    "apps/coding_cli/client.py",
    "apps/coding_cli/commands.py",
    "apps/coding_cli/main.py",
    "apps/coding_cli/managed_server.py",
)

INTENTIONAL_SHIMS = {
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
    "platform.persistence.session.base": {
        "path": "platform/persistence/session/base.py",
        "canonical": "core/session/store.py",
        "marker": "Compatibility shim re-exporting the canonical core session store contract.",
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
    "hooks.loader": {
        "path": "hooks/loader.py",
        "canonical": "platform/hooks/loader.py",
        "marker": "Compatibility shim for the canonical platform hook loader.",
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
    "cli.http_client": {
        "path": "cli/http_client.py",
        "canonical": "platform/sdk/client.py",
        "marker": "Compatibility shim for the shared HTTP client contract.",
    },
    "apps.coding_cli.client": {
        "path": "apps/coding_cli/client.py",
        "canonical": "platform/sdk/client.py",
        "marker": "Application-layer alias for the shared HTTP client contract.",
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
}

REQUIRED_DOC_SNIPPETS = (
    "## 八、M83 最终目标态验收（代码/测试/文档对齐）",
    "### 1. 最终目标目录树（以当前代码为准）",
    "### 2. M83 验收后的 canonical ownership",
    "### 3. 保留的 compatibility shim 清单（intentional only）",
    "### 4. 验收测试与文档勾稽",
    "### 5. M80-M83 高优先项收口状态",
    "tests/contract/test_multi_product_architecture_acceptance.py",
    "DONE：M80 products canonicalization and profile contracts",
    "DONE：M81 platform physical canonicalization",
    "DONE：M82 core 归位与共享抽象收口",
    "DONE：M83 compatibility shim 清理与目录目标态验收",
    "deferred：`apps/node_gateway/`",
)


def test_architecture_doc_contains_final_target_tree_and_acceptance_sections() -> None:
    doc = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for snippet in REQUIRED_DOC_SNIPPETS:
        assert snippet in doc, f"missing architecture acceptance snippet: {snippet}"
    for line in EXPECTED_TARGET_TREE_LINES:
        assert line in doc, f"target tree line missing from architecture doc: {line}"



def test_final_target_tree_paths_exist_in_repository() -> None:
    for relative_path in EXPECTED_EXISTING_PATHS:
        assert (SRC_ROOT / relative_path).exists(), f"missing target-state path: {relative_path}"



def test_intentional_shims_still_point_at_documented_canonical_homes() -> None:
    doc = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    for shim_name, meta in INTENTIONAL_SHIMS.items():
        shim_path = SRC_ROOT / meta["path"]
        canonical_path = SRC_ROOT / meta["canonical"]
        assert shim_path.exists(), f"missing shim path: {meta['path']}"
        assert canonical_path.exists(), f"missing canonical path for {shim_name}: {meta['canonical']}"

        source = shim_path.read_text(encoding="utf-8")
        assert meta["marker"] in source, f"shim marker drifted for {shim_name}"
        assert shim_name in doc, f"architecture doc missing shim entry: {shim_name}"
        assert meta["canonical"] in doc, f"architecture doc missing canonical target for {shim_name}"
