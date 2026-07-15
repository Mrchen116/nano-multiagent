# refactor-463-M4 — Progress

## 启动基线

- Context: Round 1 verification/acceptance/code review 已确认 M3 的 owner 迁移方向正确，但 active run、旧 session、unattended session 与显式空权限仍缺少 revision provenance 闭环；M4 从 `9aab3c065` 的批准修复计划开始。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` → `3358 passed, 1 skipped, 22 warnings`（32.05s）。
- Leader alignment: M4 按 A/B/C/D 四组 finding 逐 Roadpoint 完成 TDD 三提交；动态 prompt 只验证公开 `custom_prompt`，不恢复废弃的 `system_prompt`。

## R1 — 闭合 revision/run-control 与权限 provenance

- Context: coordinator active marker 只保存 run id，配置 publish 后 stop/steer 会重新 resolve 新 session；internal dispatch/fork/heartbeat/background delivery 也会在 await 后重新读取当前 catalog/binding，旧 revision 的 work 因而可能被重标、丢失或污染新 session。`Kernel.create_session()` 还用 truthiness 处理 allowlist，使显式 `[]` 退化为产品默认工具。
- Decision: coordinator active marker 升级为持有原 binding 与 Agent snapshot 的不可变 handle，active steer/stop/model/workspace 全部使用该 handle。binder 成为 session/binding provenance 的唯一捕获 owner，原子返回 snapshot + write guard，并为 inbound、fork、heartbeat/cron session 登记来源。internal dispatch 在发 IM 前捕获 origin provenance，缺失时 fail-fast，await 后只用捕获事实完成 semantic bind/history。background subscriber 直接闭包捕获原 `ReplyContext`。heartbeat 专用 session cache按 Agent revision 分代，生产 shim 以专用 `create_agent_session()` 接收捕获 snapshot。Kernel 把 `None` 与显式空 allowlist 分开处理。
- Rationale: 当前 catalog revision 只决定新 admission；已接纳 work 的控制、prompt/tools、历史和投递必须沿创建时 provenance 完成。事实捕获与 stale-write 判定集中在 binder，调用方不再跨 await 拼装 catalog、binding 与 generation。专用 unattended 创建接口不把 Gateway snapshot 参数泄露给通用 kernel-client protocol 或既有测试替身。
- Evidence:
  - C1 red: active publish→stop/steer、旧 session dispatch、fork lookup/publish race、empty allowlist、heartbeat revision 与旧 subscriber reply context 共 6 个稳定失败；commit `6c2bdd88d`。
  - Focused: 相关 coordinator/binder/dispatch/fork/background/heartbeat/Kernel 集成回归 → `37 passed, 2 warnings`；`ruff check` → passed。
  - Full: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` → `3364 passed, 1 skipped, 22 warnings`（33.33s）。
  - Entry: public `SessionRunCoordinator` 测试证明 publish/invalidate 后 steer 与 stop 仍命中原 session；public binder + `InternalDispatchHandler`/fork handler 测试证明旧 session 只使用旧 workspace/revision guard且不能恢复 stale binding；真 `Kernel.create_session(enabled_tools=[])` 集成回归证明 runtime tool registry 为零工具；heartbeat 与 background public owner 回归证明 revision 分代和原 reply context 保留。最终四条隔离真栈旅程在 R4 统一签收。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - Visual/Interaction: N/A。
- Rollback: 回退 C2 `9e300138e` 恢复 M3 末态；C1 可随同回退。R1 没有改变 session key、binding schema、IM API 或外部 channel 协议。
- Commits: C1=`6c2bdd88d`；C2=`9e300138e`；C3=本次 docs commit。
- Next: R2 先以永久红测锁定 subscriber/cron/dispatcher/shutdown accepted-work 的线性化与 terminal delivery，再修复 shutdown resource graph。
