# M11 Progress

## 2026-07-16 — R1 completed

- Context: foreground `GatewaySessionBinder` 与 unattended `_KernelClientShim` 分别把同一 `LiveAgentSnapshot` 投影为 prompt/tools/features/skills；两套规则已经在 empty features 上出现 `None` 与 `{}` 的可观察漂移。
- Decision: 新增 typed `AgentSessionCapabilities` 与公开 `project_agent_session_capabilities()` owner；两个 session 创建入口只保留各自的 title/metadata/provenance 生命周期，并复用同一能力投影。
- Rationale: capability 规则必须由 snapshot 到 Kernel kwargs 的单一 owner 决定；场景差异只作为 prompt 的 scenario 输入，不能复制 skills/tools/features 的空值语义。
- Evidence:
  - Tests: C1 `e9906904f` 精确 2 red（empty features parity + 缺共享 owner）；C2 `631a9ada1` 后 binder/unattended/architecture/size 聚焦 `28 passed`，全仓 Ruff 通过，非 e2e `3433 passed, 1 skipped, 20 deselected`。
  - Entry: 通过 `GatewaySessionBinder.resolve()` 与 `_KernelClientShim.create_agent_session()` 两个生产 session 创建入口，对同一 snapshot 的 prompt/enabled_tools/features/skills 做结果对账；restricted 配置完全一致，empty features 统一为 canonical foreground `None`，empty tools 保持显式 `[]`，empty skills 保持 `None`。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 永久回归位于 `tests/unit/personal_assistant/test_unattended_session_skills.py`；本 roadpoint 是进程内 composition 重构，不需要服务或 LLM。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型）。
- Rollback: 回退 C2 `631a9ada1` 将恢复双投影与 empty features 漂移；C1 会重新阻断。
- Commits: C1=`e9906904f`, C2=`631a9ada1`, C3=本提交。
- Next: R2 neutral IM HTTP transport seam。

## 2026-07-16 — R2 completed

- Context: config sync 本身定义通用 IM URL/header helper，shadow sync 与 composition root 再跨 owner 导入其 underscore 私有符号；传输归一化因此被错误绑定到 Agent 配置业务 owner。
- Decision: 新增中立公开 `im_http_transport` owner，导出 `normalize_im_http_base_url()` 与 `build_im_http_headers()`；config sync、shadow sync、bootstrap/auth/attachment 路径全部直接消费该 seam，并删除旧私有 helper。
- Rationale: URL scheme 与鉴权 header 是所有 IM HTTP adapter 共享的 transport policy，不属于配置同步；公开中立 owner 让任一业务 adapter 可删除而不带走其他 consumer 的基础传输能力。
- Evidence:
  - Tests: C1 `9dbd6c281` 为 8 red；C2 `5c0f955c1` 后 transport/shadow/config/auth/auto-bind/architecture/size 聚焦 `40 passed`，全仓 Ruff 通过。非 e2e 首跑仅既有 40ms watchdog 时序用例失败；该用例独立连续 5 次通过，未改或放宽测试，完整重跑为 `3441 passed, 1 skipped, 20 deselected`。
  - Entry: public transport tests 覆盖 HTTP/HTTPS/WS/WSS、非法 scheme、带/不带 token；现有 `IMAgentConfigSync`、`IMShadowConversationSync`、`_IMBootstrapClient`、IM auth 与 attachment fetch 的生产入口回归保持全绿。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 永久回归位于 `tests/unit/personal_assistant/test_im_http_transport.py` 与 `tests/contract/test_gateway_inbound_ownership_contract.py`；本 roadpoint 不改变网络协议，无需启动服务或 LLM。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型）。
- Rollback: 回退 C2 `5c0f955c1` 将恢复 config-sync 私有 helper 与跨 owner import；C1 会重新阻断。
- Commits: C1=`9dbd6c281`, C2=`5c0f955c1`, C3=本提交。
- Next: rebase latest `origin/unit/refactor-463`，重跑聚焦/全量门禁，合入并清理 milestone。
