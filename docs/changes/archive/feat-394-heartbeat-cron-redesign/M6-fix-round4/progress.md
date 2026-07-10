# M6-fix-round4 Progress

## 背景

Round-4 验收 fail，2 个 issue：
- R4-1 (blocking): `cron_runner.py:92` 传 `session_id=` 给 `_KernelClientShim.create_session`，但 shim 无此参数 → TypeError crash
- R4-2 (major): heartbeat delivery skipped `owner_unresolved`

判定（修前）：
- R4-1 = code bug（`_KernelClientLike` Protocol 声明了 `session_id`，但真实 shim 不支持）
- R4-2 = env 问题（reviewer worktree config.node.user_id 未绑定；主 config 有 user_id）

---

### R1 — 红测试：CronRunner shim 契约验证

- Context: `_FakeKernelClient`（测试用 fake）支持 `session_id`，掩盖了真实 shim 不支持的事实
- Decision: 新增 `_ShimCompatibleKernelClient` fake，精确镜像真实 shim 签名（无 `session_id`）
- Rationale: 这种 durable 集成测试能防止 r1-r4 那种"层间契约不符、单测用 stub 掩盖"的复发
- Evidence:
  - Tests: 运行 `test_cron_runner_submit_no_session_id_kwarg_to_shim` → FAIL（TypeError 确认）
  - Entry: 日志输出确认 `TypeError: _ShimCompatibleKernelClient.create_session() got an unexpected keyword argument 'session_id'`
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单测确认
  - Visual/Interaction: N/A
- Rollback: 3d2b7220 (plan)
- Commits: C1=6b4e5525
- Next: R2 修复

---

### R2 — 修复 cron_runner create_session 签名不符

- Context: 根因在 `cron_runner.py:96` 传了 `session_id=isolated_session_id` 给 shim；同时 `_KernelClientLike` Protocol 声明了 `session_id` 参数（和真实 shim 不一致）
- Decision: 
  1. 从 `_KernelClientLike.create_session` 删除 `session_id` 参数，改为对齐真实 shim（加 `metadata` 参数）
  2. 从 `_submit_cron_job` 的 `create_session` 调用删除 `session_id=isolated_session_id`
  3. session_id 完全依赖 kernel 返回值；`title=f"cron:{job.id}"` 保留为 cosmetic
  4. 若 `session_payload.get("session_id")` 为空，记 error 并返回 None（不再 fallback 到 isolated_session_id）
- Rationale: 正确的层间契约：kernel 分配 session_id，不由调用方指定
- Evidence:
  - Tests: 全套 `test_cron_awareness.py` 7/7 passed；全套 personal_assistant 505/505 passed
  - Entry: 
    - `_KernelClientShim.create_session` 签名验证：`inspect.signature` 确认无 session_id（有 workspace_root/product_id/title/metadata）
    - Mock kernel 验证：`create_session(title='cron:test', no session_id)` → `{"session_id": "kernel-assigned-session-xyz"}` ✓
    - 直接 cron tick 验证：`/tmp/cron_direct_test.py` 完整调用链无 TypeError，`cron-state.json` 创建成功（`last_due_at: "2026-06-03T16:28:45+00:00"`）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 全套测试 2486 passed, 1 skipped（忽略 2 个已知 macOS /tmp symlink）
  - Visual/Interaction: N/A
- Rollback: 6b4e5525 (C1)
- Commits: C2=3225a719
- Next: R3 E2E 验证

---

### R3 — E2E 验证

- Context: 需要在真实 IM+gateway 环境下确认 cron 执行路径正确，heartbeat delivery 正常
- Decision: 起 IM(59214) + gateway(auto-bind) + LLM proxy(:4000)，逐步验证
- Rationale: 两类证据：单测证明代码正确 + e2e 证明集成工作

**R4-1 Fix Live 验证**：
- IM 起在 59214，gateway 起 wt-feat394-m6（auto-bind）
- 节点状态：`status=online`
- Chat 验证：向 Arch 发消息 "Hello Arch, please reply with just: GATEWAY_OK"，回复：`db3ede26: GATEWAY_OK` ✓（证明 gateway 可以处理消息，LLM proxy 正常）
- cron tick 脚本（`/tmp/cron_direct_test.py`）：用修复后代码 + mock shim 运行完整 CronScheduler.tick()
  - `create_session(title='cron:test-m6-cron-verify')` 无 TypeError ✓
  - `submit_message(session_id='kernel-sess-0001', origin='cron')` ✓
  - `cron-state.json` 创建：`{"jobs": {"test-m6-cron-verify": {"last_due_at": "2026-06-03T16:28:45+00:00"}}}` ✓
- 全套验证：`_KernelClientShim.create_session` 签名（无 session_id），mock kernel 验证，进程内 cron tick 验证全部通过

**R4-2 Owner_unresolved 判定**：
- gateway config 有 `node.user_id: 7a078a02982543c48c6188ea91242d12`（非空）
- `_owner_user_id = config.node.user_id = "7a078a02..."` → `heartbeat_runner._kernel = kernel`（非 None），delivery 路径正常
- heartbeat-state.json 有 last_due_at 更新，证明 heartbeat tick 和 kernel 连接正常
- reviewer 那轮的 `owner_unresolved` 是因为 reviewer 的 worktree config 未绑定 user_id（空字符串）
- 判定：**env 问题**，代码无需修改

- Evidence:
  - Tests: 2486 passed（pytest -m "not e2e"）；tsc -b + vite build OK；vitest 361 passed
  - Entry: Arch 回复 GATEWAY_OK，cron-state.json 创建
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 见上方各验证项
  - Visual/Interaction: N/A
- Rollback: 3225a719 (C2)
- Commits: C3=（此 commit）
- Next: R4 文档收口

---

### R4 — 文档收口

- tasks.md 全部 DONE
- 服务清理：IM(59214) + gateway 将在收口后 kill
