# M9 — 原子 steer 与 binding reuse 热路径

## Goal

修复 Round 4 code review 识别的两个 session owner 缺口：public `try_steer` 必须把“确认目标 active run、注入、返回同一 run identity”钉成原子契约；binder 在第一次权威确认 workspace ownership 后，稳定 revision 的后续消息不能继续 O(history) 扫描 session JSONL。

## Exit criteria

- [ ] SDK/run registry 提供 expected-run compare-and-inject 原子语义；失败保证零注入、零隐式新 run。
- [ ] coordinator 传入自己持有的 active marker，并只按实际同一 run 登记/清算 follower；A→B 切换竞态不串 run、不丢回复、不重复 submit。
- [ ] binder 对 restart 首次接管、revision/workspace 变化保留权威验证；同进程稳定 reuse 为 O(1)，不重复读取完整 transcript。
- [ ] 永久竞态、restart/mismatch/invalidation 与复杂度回归通过，测试文件符合规模规范。
- [ ] 聚焦测试、`ruff check .` 与 `pytest -m "not e2e"` 全部通过。
- [ ] milestone 分支合入并推送 `unit/refactor-463`，随后清理 milestone worktree/branch。

## Test strategy

- SDK/registry contract：确定性暂停 A active lookup，在 B 接管同 session 后恢复，证明 expected A 不会注入 B；成功时返回 identity 与实际 controller 一致。
- coordinator public regression：forced active-switch 下 follower/lifecycle/history 只归属一个 run，fallback 最多一次。
- binder interface/performance regression：对稳定 binding 重复 resolve，权威 session lookup 只在首次接管发生；restart、workspace mismatch、publish/invalidate race 保持既有结论。
- 非前端改动，无 frontend build/test 要求。

## Roadpoints

### R1 — Atomic expected-run steer

- [ ] C1 红测：锁定 A→B 切换窗口与 coordinator follower identity。
- [ ] C2 实现：在 registry/SDK 源头提供 compare-and-inject，coordinator 传入 marker。
- [ ] C3 文档：记录契约、竞态与测试证据。

### R2 — O(1) stable binding reuse

- [ ] C1 红测：锁定稳定 reuse 不重复扫描、restart/mismatch 仍验证。
- [ ] C2 实现：由 binder provenance 缓存已验证 ownership，并保留 generation/recheck。
- [ ] C3 文档：记录复杂度边界与验证证据。
