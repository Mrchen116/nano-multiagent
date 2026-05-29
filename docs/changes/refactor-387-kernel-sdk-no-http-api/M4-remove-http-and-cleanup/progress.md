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
- Next: R2 — 删 coding_cli 死 HTTP 文件

