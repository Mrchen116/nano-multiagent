# feat-349-M4: fix-hook-mode-and-meta-styling — Tasks

> Post-acceptance fix milestone（round 1）。由 orchestrator 亲自实施（派发的 worker 因额度限制未能启动）。

## 目标

修 round 1 验收报告（`acceptance.md`）中的两个 in-unit issue：

- **Issue #1 [BLOCKING]** — `_filter_hook_registry` 丢 `mode` 字段，`self_improvement` 的 `agent_end` background 注册被降级为 observe，`fork_conversation` 永不注入，自进化流程（AC-1/2/3/4）整体失效。
- **Issue #3 [MINOR]** — IM `sender_type=system` 消息渲染为普通聊天气泡，无视觉区分。

Issue #2（PA Gateway user_id 持久化）已判定为 out-of-unit 预存问题，转 GitHub issue #10，不在本 milestone 范围。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | `_filter_hook_registry` 透传 `mode` 字段 + 单测 | DONE |
| R2 | IM system 消息渲染核查（活跃 v2 路径） | DONE |
| R3 | 全量回归 + 验收 | DONE |

## 退出标准

- `_filter_hook_registry` 透传 `mode`，单测断言 background 注册过滤后仍为 background；
- bootstrap 集成验证：PA + LC 两产品 bootstrap 后 `self_improvement` hook 在 `background_handlers_for("agent_end")` 中、未泄漏到 observe；
- IM 活跃聊天路径（v2）将 `sender_type=system` 渲染为视觉区分的轻量 meta 提示；
- 全量 `tests/unit/` + `tests/contract/` 相对 main 基线无新增失败。
