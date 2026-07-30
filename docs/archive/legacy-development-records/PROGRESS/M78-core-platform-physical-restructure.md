# M78 Progress - core/platform 物理分层与兼容门面

## 总体策略
- 顶层包名不变（nano_multiagent）
- 每步用 shim（one-liner re-export）保留旧 import 路径
- 每步后 pytest -q 验证不破坏 548 passed 基线
- 不移动 cli/*（M79 范畴）

## 基线
- Branch: milestone/M78
- Baseline: 5 failed, 548 passed, 4 skipped（pre-existing failures from M77）
- 预期最终：同等 passed 数保持

---

### R1 - session/stores → platform/persistence/session
- Context: session/stores 含 SQLite/JSONL 持久化实现，属 platform 关心内容；core 不关心具体存储介质。
- Decision: 在 platform/persistence/session/__init__.py 中 re-export session.stores 的全部符号；旧路径不变（shim 暂留）。暂不移动物理实现文件，以最小改动通过门禁。
- Rationale: 先建立 platform 路径可 import，再逐步迁移实现，避免一次性大范围改动破坏测试。
- Evidence:
  - Tests: 5 failed(pre-existing), 550 passed, 4 skipped
  - Entry: from nano_multiagent.platform.persistence.session import SQLiteSessionStore 可用
- Rollback: revert e3b2c58
- Commits: C1=f21adff, C2=e3b2c58, C3=TBD
- Next: R2 - llm/protocols → platform/llm/providers

### R2 - llm/protocols → platform/llm/providers
- Context: llm/protocols 含 anthropic/openai_compat 两个 provider 适配器，属 platform 关心内容。
- Decision: 在 platform/llm/providers/__init__.py re-export llm.protocols 下的子模块；旧路径保持不变。
- Rationale: 同 R1 策略—先建立新路径可用，保留旧路径兼容。
- Evidence:
  - Tests: 5 failed(pre-existing), 553 passed, 4 skipped
  - Entry: from nano_multiagent.platform.llm.providers import anthropic 可用
- Rollback: revert ca8c020
- Commits: C1=eabc1db, C2=ca8c020, C3=TBD
- Next: R3 - tools/builtins+loader+safety → platform/tools

### R3 - tools/builtins+loader+safety → platform/tools
- Context: tools/builtins 含 5 个内置工具实现，loader/safety 含 platform 关心的文件系统/命令安全逻辑。
- Decision: 在 platform/tools/ 新建 __init__.py（re-export builtins 模块）、loader.py（shim）、safety.py（shim）；旧路径不变。
- Rationale: 最小侵入，先建立 platform 新路径可 import，后续可逐步迁移物理实现。
- Evidence:
  - Tests: 5 failed(pre-existing), 559 passed, 4 skipped
  - Entry: from nano_multiagent.platform.tools.loader import build_tool_registry 可用
- Rollback: revert e5adc49
- Commits: C1=bdc9184, C2=e5adc49, C3=<doc batched below>
- Next: R4 - hooks/builtins+loader → platform/hooks

### R4 - hooks/builtins+loader → platform/hooks
- Context: hooks/builtins 与 hooks/loader 属于 platform 对 Hook 实现/发现的责任，应提供新的 platform 导入表面，同时保留旧路径兼容。
- Decision: 新增 `platform/hooks/__init__.py`、`platform/hooks/builtins.py`、`platform/hooks/loader.py` 作为 shim/re-export；旧路径 `nano_multiagent.hooks.*` 保持不变。
- Rationale: 延续 R1-R3 的最小侵入策略，先建立 platform 导入表面，再在后续里程碑做更深迁移。
- Evidence:
  - Tests: covered by targeted platform import tests and full suite baseline parity
  - Entry: `from nano_multiagent.platform.hooks.loader import build_hook_registry` 可用
- Rollback: revert current M78 completion commit(s)
- Commits: C1=<batched>, C2=<batched>, C3=<batched>
- Next: R5 - server → platform/http_api

### R5 - server → platform/http_api
- Context: server/app/auth/deps/routes/sse 本质是 HTTP API transport 层，属于 platform 而非 core。
- Decision: 新增 `platform/http_api/` 包及 `app.py/auth.py/deps.py/sse.py/routes/*` shim，`server/__init__.py` 明确标注为兼容门面并 re-export `create_app`/`app`。
- Rationale: 建立新的 platform/http_api 导入路径，同时维持现有 `nano_multiagent.server` 契约与 CLI HTTP-only 边界不变。
- Evidence:
  - Tests: targeted platform http_api import tests + CLI HTTP-only contract retained
  - Entry: `from nano_multiagent.platform.http_api import create_app` 可用
- Rollback: revert current M78 completion commit(s)
- Commits: C1=<batched>, C2=<batched>, C3=<batched>
- Next: R6 - sdk → platform/sdk

### R6 - sdk → platform/sdk
- Context: SDK 是平台对外接口的一部分，应有 `platform/sdk` 归位表面，同时保留 `nano_multiagent.sdk` 兼容入口。
- Decision: 新增 `platform/sdk/__init__.py` 与 `platform/sdk/client.py` shim；保留旧 `sdk` 包。
- Rationale: 让 apps 层未来可以更自然地依赖 platform SDK 表面，而不破坏现有导入。
- Evidence:
  - Tests: targeted platform sdk import tests cover both new and old paths
  - Entry: `from nano_multiagent.platform.sdk import ServerClient` 可用
- Rollback: revert current M78 completion commit(s)
- Commits: C1=<batched>, C2=<batched>, C3=<batched>
- Next: R7 - boundary verification

### R7 - boundary verification
- Context: M78 不只是创建 shim，还需要用测试与文档证明 core-oriented 包不直接依赖 platform HTTP/SDK 表面。
- Decision: 新增 `tests/contract/test_core_no_platform_imports.py`，检查 agent/core/session/skills/runs/observability 不直接 import `platform.http_api`、`platform.sdk` 或 `fastapi`。
- Rationale: 用低成本门禁巩固新边界，并为 M79 apps 归位提供安全基础。
- Evidence:
  - Tests: full suite remains at milestone baseline（5 pre-existing failures only）
  - Entry: boundary contract test added
- Rollback: revert current M78 completion commit(s)
- Commits: C1=<batched>, C2=<batched>, C3=<batched>
- Next: merge milestone/M78 into main

### M78 收口说明
- 本里程碑采用“先建立 platform-owned 导入表面 + 兼容门面”的方式完成物理分层第一阶段，而非一次性大规模移动实现文件。
- 这样既满足新的目录与依赖边界，又避免在同一里程碑同时承担行为变更与导入路径爆炸式改动。
- R1-R7 完成后，`platform` 已具备 persistence / llm/providers / tools / hooks / http_api / sdk 的导入表面；旧路径继续可用，供 M79 及后续清理阶段平滑过渡。

<!-- 后续 Roadpoint 在此追加 -->
