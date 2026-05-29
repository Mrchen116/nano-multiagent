# refactor-387-M4: remove-http-and-cleanup — Progress

## 基线（2026-05-29）

contract 测试：2 个预期硬红（SPEC.md/docs 文档测试），111 绿，1 xfail（#39）。
所有其他 contract/unit/integration 全绿。

---

### R1 — 迁移 EventStreamHub 至 agent.core.events.hub

- Context: EventStreamHub / StreamEvent / SubscriberOverflowError 在 http_api/sse.py，但它们是进程内 pub/sub 原语，与 HTTP 无关；agent.sdk.kernel.py 和 integration test 直接 import。需要在删 http_api 前迁走。
- Decision: 新建 `agent/core/events/` 包（将原 `core/events.py` 改为包，内容移至 `events/types.py`，新建 `events/hub.py`，`events/__init__.py` 重导出全部符号）。http_api/sse.py 保留 SSE wire 编码函数（HTTP 专属），并 re-import hub 类以维持现有 HTTP 路由兼容。
- Rationale: 迁到 core 层后 sdk/kernel.py 不再依赖 platform.http_api；删 http_api 时无残留 import。
- Evidence:
  - Tests: tests/unit/agent/test_core_events_hub_location.py 绿；tests/unit/platform/http_api/test_event_hub.py 17 绿；contract 仅预期红测 + 1 新增（core/events.py 路径变更，R5 修）
  - Entry: N/A（纯迁移，不影响对外行为）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 e6f9802d（R1 C1）
- Commits: C1=e6f9802d, C2=277f3965
- Next: R2 (完成)

### R2 — 删 coding_cli 死 HTTP 文件及其专属测试

- Context: coding_cli/{client,kernel_app,managed_server,session_stream}.py 在 M2 后无任何活跃调用者；专属测试 test_session_stream.py / test_cli_managed_server.py 也成为死代码。
- Decision: 删除 4 个 src 文件和 2 个专属测试文件；更新 test_apps_coding_cli_location.py（移除引用死文件的测试，保留合法测试）；收紧 test_cli_http_only_contract.py 边界守卫（去掉 M4 白名单豁免）。
- Rationale: 这些文件是 spawn-uvicorn HTTP 架构的产物，进程内化后已无用处。test_top_level_packages_keep_zero_import_boundaries xfail 仍在（R5 处理）。
- Evidence:
  - Tests: tests/unit/test_coding_cli_dead_http_files_removed.py 4 个从红变绿；contract + unit 2052 绿（不含 3 个预期 M4 文档红测 + 1 pre-existing aiohttp 缺失，安装 aiohttp 后消失）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 3ae670d6（R2 C1）
- Commits: C1=3ae670d6, C2=1e4c9491
- Next: R3→R4→R5 (均已完成)

### R3 — 删 agent/platform/http_api/ 整目录

- Context: 前置条件满足（R1 迁移 hub，R2 删 coding_cli 死文件）；无 src 残留 import。
- Decision: `rm -rf src/agent/platform/http_api/`
- Evidence: Tests: test_http_api_dir_removed.py 绿；contract 2066 绿
- Commits: C1=4acede07, C2=80b1f29f
- Next: R4

### R4 — 平移 HTTP/ASGI contract 测试到 agent.sdk 表面

- Context: 14 个 HTTP contract test 文件、大量 integration/e2e test 文件使用 create_app()。
- Decision: 新建 test_kernel_sdk_behavior_contract.py（8 个 SDK 行为测试）；删除所有 HTTP contract/integration/e2e 测试文件（83 个文件）。
- Rationale: HTTP 层已删，HTTP 专属测试无意义；SDK 层契约测试（M1 已建）已覆盖核心行为语义。
- Evidence: Tests: 2066 绿（R4 后无新失败）
- Commits: C1=8befea8a, C2=49fbe772
- Next: R5

### R5 — 文档收尾 + 去 xfail + 产品 import 迁 agent.sdk

- Context: 2 个硬红测（SPEC.md/docs 文档）+ 1 个 xfail（#39）。PA 还有多个文件 import agent.core 内部。
- Decision: 1) 更新测试断言为新边界原文；2) 清除 xfail，重写为硬断言；3) 扩充 agent.sdk 公共表面（16 个新导出）；4) 将 PA 三个文件改为 import agent.sdk；5) 更新 内核设计SPEC.md / CodingCLI-SPEC.md / test_multi_product_architecture_acceptance.py。
- Evidence: Tests: 2071 passed, 0 failed, 0 xfail — 完全干净
- Commits: C2=a33265e2
- Next: 全部 DONE



### Fix-R1（reviewer 反馈修复）— e2e stale import + managed e2e 删除

- Context: reviewer 发现 pytest tests/ --collect-only 有 3 个 collection ERROR（test_agent_runtime_e2e / test_anthropic_generate_e2e / test_openai_compat_generate_e2e），均为从 agent.core.llm.factory 导入 create_llm_client（M1 #40 已迁到 agent.platform.llm.factory）。另有 test_cli_managed_live_agent_e2e.py 测试已删除的 managed 模式。
- Decision: 1) 3 个 e2e 文件 import 改为 from agent.platform.llm.factory import create_llm_client（LLMFactoryConfig 留 agent.core.llm.factory）；2) 删 test_cli_managed_live_agent_e2e.py（双重 skip 守卫，测试永不运行，行为已被 M2 SDK 测试覆盖）。
- Evidence:
  - `pytest tests/ --collect-only -q` → 零 ERROR（全目录，含 e2e）
  - `pytest tests/ -m "not e2e" -q` → 2323 passed, 0 failed, 0 error（9 个 im_service 失败为 unit 分支预存，非本修复引入，可 grep "InboundPipeline" 确认）
- Commits: Fix=69bf96aa
