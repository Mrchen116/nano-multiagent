# bugfix-426-M1 — Progress

## [对齐] design 多模态措辞 vs 内核 text-only 现实（开工前 orchestrator 确认）

- Context: design 决策2/3 写「注入携带完整多模态 parts、content 为 list 时不强转 text」，
  暗示 LLM 边界走多模态 content。
- 现实核查（grep 证据）:
  - `agent/core/agent/state.py:87-103` `render_user_text()` 把 parts 渲染成纯文本，image→`[image:placeholder]`，返回 str。runtime 用 `user_text`(str) 喂 loop（loop.py:202-207 `build_chat_messages(user_text=...)`）。
  - 图片仅作为 `input` hook 的 `images` 字段传出（runtime.py:387），但全仓**无任何 hook 消费它把图片塞回 LLM 消息**（grep `images`/`image_url` 命中均为工具/read 无关项）。即正常 submit 路径今天图片也到不了模型。
  - anthropic mapper（providers/anthropic/mapper.py:147-151）对 user 角色消息 `content:[{"type":"text","text": message.content}]`——若 content 传 list 会把 list 塞进 text 字段，**直接坏**。openai_compat 透传 list 但 gateway 建的 part 形状 `{"type":"image","image_url":<url>}` 与 vision 格式 `{"type":"image_url","image_url":{"url":...}}` 不匹配。
- Decision（orchestrator 确认）: 注入复用 submit 同款 `parse_input_parts + render_user_text`，content 为 str。
  - 决策2 真实意图 = 「注入与 submit 走完全相同的 parts→message 转换、带不带附件无差别」；
    用 render_user_text 正好让该字面成立（两条路径都是 placeholder+全文），不引入与既有不一致的多模态平行物、不碰坏 mapper。
  - 决策3「content 为 list 时不强转 text」在此前提下 moot（注入 content 本就是 str），registry stranded 续跑 `{"type":"text","text":msg.content}` 对 str 已正确。
  - 决策3 仍要做：stranded 续跑 origin 跟随注入来源（用户 steer→USER）+ inject_pending_message/pending 承载 origin。
  - 真多模态打通是预存内核限制（与本 unit 无关、submit 也没通），不在本 unit 范围。
- delta-spec 多模态措辞由 orchestrator 收尾归并按现实校正。

## R1 — RunController pending 承载 origin + stranded 续跑修正（决策3）

- Context: stranded 续跑（registry terminal-path）硬编码 `origin=BACKGROUND_TASK`，
  会把用户 mid-run steer 在 run-end 竞态路径错标来源。pending 队列原只存 LLMMessage、不带 origin。
- Decision:
  - `run_control.py`：新增 frozen `PendingMessage(message, origin)`；`enqueue_message(message, origin)`、
    `drain_pending()` 返回 `list[PendingMessage]`。
  - `loop.py:262-264`：drain 消费侧改 `llm_messages.append(pending.message)`（行为不变，仅取 .message）。
  - `registry.py`：`inject_pending_message(session_id, message, origin=RunOrigin.USER)` 加 origin；
    terminal-path stranded 续跑用 `_group_pending_by_origin` 把 drained 项按**连续同 origin**分批，
    每批 submit 一个续跑 run 带该 origin（保 FIFO + 各批正确归属），不再硬编码 BACKGROUND_TASK。
  - `wiring.py`：background_tasks 注入调用点显式传 `origin=RunOrigin.BACKGROUND_TASK`（维持其现状语义）。
- Rationale: origin 随消息走是最小且正确的载法——decision3 要求续跑跟随注入来源；分批分组保住
  「连发多条混合来源」时各自归属，同时不破坏 FIFO（incident Q3 按序全注入）。
- Evidence:
  - Tests: `tests/unit/agent/runs/test_run_control_pending_origin.py`（enqueue/drain 保 origin+FIFO、drain 清空）；
    `tests/unit/test_runs_registry.py::test_stranded_continuation_follows_injected_origin`（gated runtime
    保 run 活跃→inject(origin=USER)→放闸→续跑 run origin=USER）。窄相关全绿：
    `test_run_control_pending_origin + test_runs_registry` 14 passed；
    扩跑 `agent/background_tasks + agent/runs + test_agent_runtime + test_background_hook_fork` 123 passed。
    ruff check + format 通过。
  - Entry: 内核内部能力，无独立产品入口（R2 经 Kernel.submit 接出、R3 经 Gateway，R4 live 端到端）。本 R 入口验证延后至 R2-R4。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 续跑 origin 回归用例已落库（上方 stranded 测试），防 refactor 再次错标。
  - Visual/Interaction: N/A
- Rollback: `git revert` C2（fix R1）+ C1（test R1）。
- Commits: C1=test R1（红）, C2=fix R1, C3=本次 docs。
- Next: R2 — Kernel.submit(steer) + RunInfo.injected。

## R2 — <pending>

## R3 — <pending>

## R4 — <pending>
