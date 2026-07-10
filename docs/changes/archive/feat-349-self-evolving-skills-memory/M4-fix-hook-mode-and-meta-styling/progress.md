# feat-349-M4 Progress

## 基线

- 分支：直接在 `unit/feat-349`（HEAD `7f61f295`）上实施 —— orchestrator 亲自收尾，派发的 M4 worker 因 LLM 额度限制未能启动（0 token / 0 tool use）。fix 范围仅 2 文件，等同 M3 的 fix-up commit `003ed60e` 直接补提到集成分支的处理方式。
- 输入：`acceptance.md` round 1（verdict fail，blocking 1 / major 1 / minor 1）。

---

### R1 — `_filter_hook_registry` 透传 `mode` 字段

- Context: round 1 Issue #1（blocking）。`platform/bootstrap.py:_filter_hook_registry()` 重新注册 hook 时调 `filtered.on(...)` 没传 `mode=registration.mode`，导致 `self_improvement` 的 `agent_end` 注册（`mode=BACKGROUND`）被重建为默认 `OBSERVE`。OBSERVE 模式的 hook context 不会被注入 `fork_conversation`（`dispatch_observe` 会 strip），`on_agent_end` 第一行 `if fork_fn is None: return` 直接退出 —— 自进化流程从不触发，AC-1/2/3/4 全废。
- Decision: 在 `_filter_hook_registry` 的 `filtered.on(...)` 调用补 `mode=registration.mode`。
- Rationale: M1 给 `HookRegistration` 加了 `mode` 字段，但 M1 当时没同步更新 platform 层的这处 re-registration（M1 范围是 `core/hooks/`，bootstrap 在 `platform/`）。这是 M1 引入新字段后 platform 层的连带遗漏，本质属 feat-349 自身的接线 bug。
- Evidence:
  - 单测：`tests/unit/test_platform_bootstrap.py::test_filter_hook_registry_preserves_background_mode` —— 注册一个 `mode=BACKGROUND` 的 hook，过滤后断言 `background_handlers_for("agent_end")` 仍含该注册且 `mode == BACKGROUND`，且未泄漏到 `handlers_for`（observe/intercept 路径）。`test_platform_bootstrap.py` 13 passed。
  - bootstrap 集成验证（命令行实跑）：
    ```
    PA: self_improvement in background=True, leaked into observe=False
    LC: self_improvement in background=True, leaked into observe=False
    ```
    修复前 `self_improvement` 会出现在 observe handlers；修复后两产品 bootstrap 后均正确落在 `background_handlers_for("agent_end")`。
  - 链路闭合：bootstrap → background 注册 ✅（本 R）→ runtime 对 background hook 注入 `fork_conversation` 并 fire-and-forget ✅（M1 已测）→ `self_improvement.on_agent_end` 读 nudge 计数并 fork review ✅（M3 已测，10 tests）。唯一断点（bootstrap 过滤丢 mode）已修复并双重验证。
  - Entry: bootstrap 集成路径实跑（见上）。
  - E2E/Regression: 全量 `tests/unit/` 31 failed（与 main 基线 `72801295` 逐字节一致，0 新增）；`tests/contract/` 34 failed（与基线逐字节一致，0 新增）。
- Rollback: revert `bootstrap.py` 一行 + 删 `test_filter_hook_registry_preserves_background_mode`
- Commits: 见本 milestone 收口 commit

### R2 — IM system 消息渲染核查（活跃 v2 路径）

- Context: round 1 Issue #3（minor）。reviewer 报告 `sender_type=system` 消息渲染成普通聊天气泡，引用 `message-pane.tsx` 第 1008 行。
- Decision: **不改代码** —— 核查发现 reviewer 引用的是**未路由的 v1 死代码**。
- Rationale:
  - `src/app/router.tsx` 的 `chat` / `chat/:conversationId` 路由用 `ChatWorkspacePageV2`（`features/chat/v2/`），活跃的 message-pane 是 `features/chat/v2/components/message-pane.tsx`（411 行）。reviewer 引用的第 1008 行属 `features/chat/components/message-pane.tsx`（v1，1109 行），全仓除自身外无任何 import，是死代码。
  - 活跃 v2 `MessageBubble`（`message-pane.tsx:297-303`）对 `message.sender.type === "system"` 已 early-return 渲染为独立的 `<div className="chat-bubble-system">`，无 avatar、无气泡卡片。
  - `styles/global.css:1481` 的 `.chat-bubble-system`：`align-self: center` + `text-align: center` + `color: var(--im-text-muted)` + `font-size: 0.75rem` —— 居中、muted、弱化，正是 spec AC-4 要求的"轻量 meta 提示，不是 agent 发的聊天消息"。
  - `git diff 72801295..unit/feat-349 -- src/IM/frontend/` 为空：feat-349 未改任何前端文件，该 system 渲染逻辑是 feat-349 之前就存在的、已合规的实现。
- Evidence: 上述代码 + CSS + 路由引用核查。活跃产品路径已满足 AC-4，无需改动。Issue #3 系 reviewer 对死代码文件的核查误判。
- Rollback: N/A（无改动）

### R3 — 全量回归 + 验收

- Context: R1 改了 `platform/bootstrap.py`，需确认无回归。
- Evidence:
  - `tests/unit/`（`--ignore test_m170_rerun_acceptance.py`）：31 failed，与 main 基线 `72801295` 的失败列表逐字节 diff 一致 → 0 新增。
  - `tests/contract/`：34 failed，与基线逐字节一致 → 0 新增，依赖方向校验无破坏。
- Next: 合入 `unit/feat-349`，orchestrator 走 §7 提 PR。
