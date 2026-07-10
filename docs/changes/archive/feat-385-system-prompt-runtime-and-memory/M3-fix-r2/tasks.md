# feat-385-M3 (M3-fix-r2) Tasks

## 目标

两块独立工作:

**P1 — preview 呈现修正 (Req-4):**
volatile 段 (memory_block / user_profile_block / communication_context) 在预览中
就地以内联占位符呈现 (如 `<运行时注入:agent 的 MEMORY.md 内容>`),保持 prompt
完整形状,不在末尾堆叠说明块。同步修正 spec.md Req-4 措辞。

**B1 — stream_session workspace_root 修复 (Refs #64):**
Gateway SSE 消费链路 stream_session 漏传 workspace_root query param,导致多 agent
(每 agent 独立 workspace_root) 时 GET /stream → kernel session_not_found 404。

## 退出标准

- P1: `/v1/prompt-preview` 端点的 volatile 段就地出现内联占位符,无末尾堆叠块
- P1: datetime 占位符行为不变,stable 段字节一致性测试仍绿
- P1: spec.md Req-4 描述更新为"就地内联占位符"
- B1: stream_session 签名加 workspace_root,请求 query 含 workspace_root
- B1: inbound_pipeline._await_terminal_run_async 透传 workspace_root
- B1: background_session_events.BackgroundSessionEventSubscriber 透传 workspace_root
- 全套 pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e" 全绿 (基线除外)

## 测试策略

后端/API:
- P1: preview 端点单测,断言 volatile 段就地出现为内联占位符(正确 order 位置),
  且无末尾堆叠块/说明块; datetime 行为不变
- B1: client 层 stream_session(workspace_root=X) 发出请求含 workspace_root=X
  (mock transport / 断言请求 URL)
- B1: pipeline 层 _await_terminal_run_async 和 background subscriber 把 agent
  workspace_root 透传到 stream_session (spy/fake kernel client 断言)

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | P1 C1: preview 内联占位符失败测试 | DONE |
| R2 | P1 C2+C3: 实现就地内联 + 删末尾堆叠 + spec.md 修正 | DONE |
| R3 | B1 C1: stream_session workspace_root 透传失败测试 | DONE |
| R4 | B1 C2+C3: 实现 3 文件 5 处改动 | DONE |
