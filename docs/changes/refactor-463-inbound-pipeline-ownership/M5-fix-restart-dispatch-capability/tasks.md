# refactor-463-M5: 重启后的 live dispatch capability — Tasks

> 对齐: ../design.md（post-verification fix, round 2）
> 输入: `../verification.md` Round 2 CRITICAL-1

## 目标

把 `gateway_dispatch_url` 明确建模为 Gateway 进程级 live capability：重启后复用同一持久化 Kernel session/history 时，`send_message` 在调用时解析当前 listener，而不是继续读取旧进程写入 durable session metadata 的端口。

## 根因与修复边界

- M4 正确把 listener 改成端口 `0` 并在 bind 后发布实际 URL，但新 session 把该 URL 固化进 metadata；binder restart reuse 只刷新 reply context/provenance，session metadata 仍是旧端口。
- `SendMessageTool` 每次执行都从 `ToolContext.session_metadata` 读 URL，因此“重启续接”和“工具投递”两个单独通过的场景组合后失败。
- 正确 owner 是 process-scoped `InternalDispatchEndpoint`。composition 应在构造 PA Kernel 前创建它，把 `current_url` 作为 callable/provider 注入 `build_pa_kernel()` / `SendMessageTool`；tool 每次调用时解析 live URL。
- production 注入 provider 后，不得在 provider 返回空时回退 stale session metadata；未 bind/已 clear 应 fail-fast。未注入 provider 的独立 tool/测试仍可使用 metadata 兼容，不改变通用 ToolContext 或 Kernel session schema。
- 不能用强制创建新 Kernel session、删除 persistent binding、固定回 8089、全局环境变量或修改历史 JSONL 绕过；session id、历史、binding schema/key/reply context 与 IM API 都保持。

## 退出标准

- [ ] 永久交叉回归：端口 A 创建并持久化 session；新 Gateway owner 发布端口 B 并复用同 binding/session；真实 `SendMessageTool` 只请求 B，A 零请求，session id 与历史不变。
- [ ] provider 在每次 tool call 解析，而非 tool/kernel 构造时快照；同一进程 endpoint publish/clear 后行为随 live 状态变化。
- [ ] 生产 provider 未 ready/已 clear 时给明确 fail-fast，不回退 session metadata；无 provider 的 standalone tool 继续兼容 metadata。
- [ ] 新 session 当前 URL、双 Gateway 不冲突、restart continuity、provenance/ack/history 既有测试保持。
- [ ] 最窄测试、相关 contract、`ruff check src tests`、`git diff --check`、`pytest -m "not e2e" -n 4 --dist worksteal` 全绿。
- [ ] 隔离真栈 durable evidence：同 conversation Gateway restart 后继续原 session/history，再调用真 `send_message` 完成投递；服务与运行时文件清理。

## 测试策略

- `SendMessageTool` 单测覆盖 provider 优先、provider live 轮换、provider 空值 fail-fast、无 provider metadata 兼容。
- Gateway/Kernel integration 使用真实持久化 binding + 真 Kernel session metadata，至少两个实际本地 listener 记录请求；不能只断言 metadata 字符串。
- 真栈走 `scripts/e2e-up.sh` / restart 路径、公开 IM 消息与 SQLite/session JSONL 对账；高位端口，结束执行 `e2e-down.sh`。

## Roadpoints

### R1 — 注入 live endpoint provider 并锁定 restart/reuse 交叉行为

- 状态: TODO
- 步骤: 先提交 tool provider 与端口 A→B persistent reuse 红测，再让 composition 在 Kernel 之前构造 endpoint owner并注入 PA tool，保留无 provider metadata compatibility。
- 验证: send_message tool + build_runtime/listener + persistent binder/Kernel integration 聚焦测试。

### R2 — 真重启签收与全量门禁

- 状态: TODO
- 步骤: 跑同 conversation/session 真 restart→send_message 旅程并落 evidence；更新 tasks/progress，跑全量门禁并清理服务。
- 验证: `ruff check src tests`; `git diff --check`; `pytest -m "not e2e" -n 4 --dist worksteal`; 隔离真栈 durable evidence。
