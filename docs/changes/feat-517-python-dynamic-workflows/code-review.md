# feat-517: Code Review

## Review scope

- Base: `cd071e649d3fe4fe7a2f392643a49c8f87825898`
- Reviewed implementation head: `6d34578c3`
- Mode: `full`
- Phase 1: 独立 finder 检查完整 unit diff、运行时线程边界、权限生命周期、持久化与产品命令入口。
- Phase 2: 独立 code verifier 逐条复核 7 项候选；resume 项由独立 change-verifier 复现。下列 8 项均为 `CONFIRMED`。

## Round 1

- Result: Issues found
- Findings:
  - [P1] resume 不校验 parent session，且把合法 `terminal_ordinal=0` 当成缺省值，既可跨会话复用结果，也会破坏真实完成顺序。
  - [P1] Workflow manager 使用新线程，但 child 在该线程读取只在父 turn `ContextVar` 中有效的模型和默认工具；默认 allowlist 会直接失败，显式 allowlist 会静默回退默认模型。
  - [P1] 停止等待 child 工具授权的 Workflow 时，取消路径不从 `PermissionBroker` 移除请求，也不发送 `permission_resolved`；父会话授权卡会永久 pending，Gateway binding 无法清理。
  - [P1] AST 只在 loop body 末尾插 checkpoint，`continue` 可绕过检查点，使 pause/stop/close 对此类循环永久失效。
  - [P1] 提示词承诺 `workflow({"scriptPath": ...})`，runtime 却只接受字符串；合法的 nested artifact 调用会在进入 child 前失败。
  - [P1] CLI suggestions 会发现 `/namespace:name`，但 REPL command gate 禁止 `:`，提交后会作为普通用户文本发给模型，无法进入 named Workflow dispatch。
  - [P1] clean child worktree 删除前没有归档其中唯一的 session transcript；dirty/cleanup-failed worktree、child session 与 transcript locator 也没有进入 run snapshot、SDK、CLI 或 PA 详情。
  - [P1] 未命名空间 `SavedWorkflowRegistry.resolve("name")` 用 plain `item.name` 重建索引，排序靠后的同名 plugin 会覆盖 project/personal/bundled winner，使 `/name` 错执行 plugin。
- Independent corroboration: change-verifier 另行复现 canonical pipeline 首阶段传 `None`、terminal sidecar 丢字段、phase/Agent telemetry 缺失、规模 advisory、nearest CLI config 与 journal recovery 问题；这些记录在 `verification.md`，不重复增加本报告 finding 数。

## Resolution plan

- 在父 tool turn 内拍下模型、effort、resolved enabled tools 与 skills，manager thread 中只消费该 immutable launch snapshot。
- 取消 permission requester 时原子移除 broker pending，生成 deny 终态并向父 session 发布一次 `permission_resolved`。
- loop checkpoint 改到每次迭代入口；pipeline 首阶段接收 current item；nested runner解析 parent-workspace 相对 `scriptPath`。
- resume 在后台 run 注册前做 parent-session 校验，并以显式 `is None` 处理 terminal ordinal。
- 对 transcript/worktree/terminal payload/phase 与 Agent telemetry 建立一条真实 manager → registry/SDK → CLI/PA 纵向契约。
- CLI command gate 接受 namespaced name；plain saved lookup 排除 plugin，plugin 仅由显式 namespace 解析。

## Closure

### Round 2

- Result: Issues found
- The original eight findings are closed. Independent recheck confirmed the
  parent runtime snapshot, permission cancellation cleanup, loop checkpoint,
  nested artifact mapping, session-scoped resume, namespaced CLI dispatch,
  transcript/worktree diagnostics, and plain-name registry precedence.
- One new P1 was found: a tagged Workflow child permission was read by the
  background stream drain while the main REPL reader already owned stdin. This
  could make approval keys race with normal message input.

### Round 3

- Result: Pass
- Tagged child permissions now enter the existing
  `_CliPermissionPromptCoordinator`. The stream drain only queues the request,
  waits for the coordinated decision, and submits it; it never reads stdin.
- The permanent REPL test keeps an input read active and verifies that the
  picker runs exactly once on that same reader thread, preserves the child
  question/options, and submits exactly one `allow_session` decision.
- Focused closure verification: 54 tests passed; Ruff passed; no new P1/P2 was
  found.

Final verdict: **PASS — 0 open P1/P2 findings.**

### Round 4

- Result: Pass
- The Round 2 acceptance fixes were reviewed as delta `4dcf1f64a..6d34578c3`.
- Restart recovery reloads runs by workspace and parent session, validates the
  owner again, creates a new run from the original script and args, and reuses
  only the durable completed-Agent cache. Cross-session resume remains denied
  with a precise diagnostic.
- Workflow child runtime model and effort are persisted only for Workflow
  child sessions. Idle terminal continuation resolves the exact parent
  session runtime; ordinary Agent launches and unrelated sessions keep their
  existing behavior.
- Incremental verification: 104 tests passed; Ruff and diff checks passed; no
  new P1/P2 was found.

Final post-acceptance verdict: **PASS — 0 open P1/P2 findings.**
