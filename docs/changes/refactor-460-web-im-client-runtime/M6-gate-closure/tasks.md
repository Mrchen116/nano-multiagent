# refactor-460-M6: gate-closure — Tasks

> 对齐：../design.md（Round 4 verifier 与 full-diff code review 追加）

## 目标

关闭 M5 合入后的独立门禁问题：新 external 会话首帧必须在 fresh cache 与权威查询失败后仍可恢复分类；跨账号、REST history 与 live event、失败终态、发送失败、多气泡和通知持久化不得互相污染。

## 退出标准

- [x] external 权威分类强制绕过 fresh conversations cache；失败项保留并在 recovery 后重试。
- [x] refresh singleflight 按 user id + refresh token snapshot 隔离，A 的失败结果不能被 B 复用或清除 B 的 flight。
- [x] history 请求飞行期间，同一消息的 created/delta/completed 等 live 更新在该次 stale reset 中完整保留，下一次权威 reset 仍可收敛。
- [x] `message.completed.delivery_status=failed` 保留为 failed，不被 reducer 改写为 completed。
- [x] composer 仅在异步发送成功后清稿；失败保留正文/附件，pending 窗口同步阻止重复提交。
- [x] multi-bubble roll 后，新气泡收到真实正文即重建 bubble-local visibility，终态不会误 tombstone。
- [x] completion accumulator 状态 identity 未变化时不重复写 sessionStorage。
- [ ] 最终独立只读 verifier/code review 通过（全量自动化门禁已通过）。

## 测试策略

- Frontend：auth session、toast hook、workspace integration、stream reducer、message pane、user-stream validation 的窄回归；随后 full Vitest 与 production build。
- Gateway：真实 observer event 序列验证多气泡第二泡正文与 terminal；相关 pipeline/lifecycle tests。
- 门禁：`ruff check src tests`、`pytest -m "not e2e"`、最终 delta verifier 与 code review。浏览器验收只允许 Codex 内置隔离浏览器；本 milestone 不修改 Chrome、macOS 或系统权限。

## Roadpoints

### R1 — external classification authority 与失败恢复（DONE）

- `fetchQuery` 明确 `staleTime: 0`，不接受 fresh cache 作为新 external 会话首帧的权威结论。
- authority failure 保留 pending classification；recovery 刷新 conversations 后重试，账号切换清空旧 pending。

### R2 — gate-confirmed continuity races（DONE）

- refresh flights 按 session snapshot 分桶。
- REST reset 对请求飞行期间触达的 message id 使用 live row，一次 reset 后清保护集。
- failed completion、composer async commit、multi-bubble visibility 与 accumulator persistence 各自补红测并修复。

### R3 — docs / full gates / independent closure（IN PROGRESS）

- 校正 design 中 canonical validation、notification owner、milestone 演进与 M4 epoch max 措辞。
- 完成全量门禁，将只读 verifier/code review 结论追加到 unit 证据。
