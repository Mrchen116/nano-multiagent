# feat-446-fix-r1-product: product-path reachability fixes — Tasks

> 对齐: ../design.md v1 + acceptance.md Round 1

## 目标

Make the reviewer-reported IM product paths reachable from the real Web IM flows without changing unrelated runtime ownership.

## 退出标准

- [ ] Agent detail exposes a usable Skills/statistics entry from the real detail/config flow.
- [ ] Conversation list right-click exposes a clear F2 distill entry and enters multi-select.
- [ ] IM config/usage boundaries do not silently overlay a mismatched live agent payload onto the requested agent.
- [ ] `/skill:<name>` ownership boundary is identified if runtime changes are required.
- [ ] Focused frontend/backend regressions pass.
- [ ] True browser validation records screenshots for Agent detail Skills and F2 distill entry.

## 测试策略

- 被测行为（来自退出标准）：Agent detail in-context Skills entry; conversation row right-click menu entry; live config response agent identity guard.
- 已有测试在：`src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`（扩展）、`src/IM/frontend/src/features/chat/v2/components/conversation-sidebar.test.tsx`（扩展）、`tests/im_service/integration/test_agent_config_api.py`（扩展）。
- 落层/目录/marker：frontend vitest component/integration tests, backend `tests/im_service/integration/`, marker: 无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：Playwright screenshots under `/tmp/feat446-fix-r1-product-*.png`.

用户路径分类：bug-regression

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | Agent detail Config tab shows Skills nav and in-context statistics entry; conversation list shows context menu entry. |
| loading | Existing Agent detail query loading coverage retained; no new loading state. |
| empty | Existing Skills empty dashboard test retained. |
| error | Existing Skills offline/error test retained. |
| disabled | Distill start button disabled until selection; running/no-transcript rows disabled in distill mode. |
| submitting | Existing F2 dialog submit pending state retained. |
| permission denied | N/A; auth covered by API route tests elsewhere. |
| long content | N/A; no new long text surface beyond existing dashboard rows. |
| missing/nullable data | Conversation rows without transcript stay disabled in distill mode. |
| mobile viewport | Browser QA will cover mobile Agent detail/F2 entry. |
| desktop viewport | Browser QA will cover desktop Agent detail/F2 entry. |
| dark mode（如项目支持） | N/A. |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| Reviewer sees allowlist but cannot find statistics | Agent detail vitest clicks in-context "View statistics" entry + browser screenshot | 是 |
| Right-click silently does nothing visible | Conversation sidebar vitest right-clicks row, sees menu item, enters checkbox mode + browser screenshot | 是 |
| Wrong live payload pollutes requested agent | IM integration test sends mismatched `agent.config` response and verifies no overlay | 是 |
| `/skill:` no tool row/stat increment | Static ownership check + documented runtime handoff; no IM-only test because root is `src/agent` | 否 |

## Roadpoints

### R1 — Product reachability and IM boundary hardening

- 步骤:
  - Add red regressions for Agent detail statistics entry, conversation right-click entry, and live config identity guard.
  - Implement minimal UI/API fixes.
  - Run focused tests, build, and true browser QA.
  - Record unresolved runtime/script handoffs.
- 验证:
  - `npm run test -- ...`
  - `pytest -q tests/im_service/integration/test_agent_config_api.py ...`
  - `npm run build`
  - Browser screenshots under `/tmp`.
