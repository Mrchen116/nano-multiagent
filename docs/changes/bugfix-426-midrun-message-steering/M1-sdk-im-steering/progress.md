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

## R2 — Kernel.submit(steer) + RunInfo.injected（决策1/2）

- Context: refactor-387 删 SDK priority 参数后，产品无 SDK 面注入 affordance。需把 feat-338
  priority="next" 以 submit(steer=True) 进程内形态接出，consumer 不自己查 active run。
- Decision:
  - `dto.py`：`RunInfo` 加 `injected: bool = False`。
  - `kernel.py`：`submit` 加 `steer: bool = False`；新增私有 `_try_inject_active_run`——
    复用 `background_tasks/wiring.py` 已验证范式：`get_active_run_id` 有活跃 run 则
    `inject_pending_message(origin=origin)`，注入成功返回 `_to_run_info(active_record, injected=True)`
    （复用活跃 run_id、不建新 run）；无活跃 run 或 inject 竞态返回 False→退化走正常 submit（injected=False）。
    注入消息 content 用 `parse_input_parts + render_user_text`（图片→`[image:placeholder]`，与 submit 同款）。
  - `_to_run_info(record, *, injected=False)` 透传 injected。
- Rationale: 决策1「consumer 只有一个心智，steer 与否由内核按活跃态决定」——把竞态判断收敛进 SDK，
  默认 False 零破坏既有调用方。竞态（inject 与 run-end 之间）由 R1 stranded 续跑兜底。
- Evidence:
  - Tests（C1 红→C2 绿）：`tests/contract/test_kernel_sdk_behavior_contract.py`：
    `test_submit_steer_idle_session_creates_new_run`（injected=False + 完成）、
    `test_submit_steer_active_run_injects_not_new_run`（injected=True + run_id 复用 + 无新 run）、
    `test_submit_steer_injects_render_user_text_content`（注入 content 为 str、含文本、图片→placeholder）。
    用 `_ThreadGatedClient`（threading.Event 跨注册表后台 loop/主 loop 安全）保 run 活跃。
    contract 全绿 129 passed；contract + R1 窄相关 142 passed（修白名单行号后）。ruff check+format 通过。
  - Entry: SDK 真 Kernel 经 build_kernel 驱动真 run（_llm_client_override），非纯 mock——证明 SDK 面真能注入活跃 run。
  - Frontend State Matrix: N/A | Browser QA: N/A
  - E2E/Regression: 三条 steer 行为契约落库（tests/contract），防 refactor 再次架空 SDK 注入面。
  - Visual/Interaction: N/A
- Rollback: `git revert` C2(R2)+C1(R2)。
- Commits: C1=test R2（红）, C2=feat R2, C3=本次 docs。
- Next: R3 — Gateway inbound steer 接线 + parts helper 抽取。

## [Design 修订待定] R3: steer 进随后被取消的 run 会丢消息（§4 暂停，已上报 orchestrator）

- 现状方案: 决策3 的 stranded 续跑仅在 `_run_worker_async` 正常完成路径（registry.py:655）drain pending。
- 发现的问题: R3 接上 Gateway steer 后，「run 活跃时到达的消息」注入活跃 run；若该 run 随后被
  cancel/abort（看门狗 idle reap / /stop / crash，走 CancelledError 提前退出），注入的 pending
  消息到不了那段 drain → **静默丢弃**，且破坏既有回归 `test_inbound_pipeline_sse.py::
  test_idle_run_is_cancelled_and_next_same_session_message_continues`（hung run 不堵 FIFO）。
- 原因: 决策3 兜底只覆盖正常完成，未覆盖取消/中止终止路径；与 incident「消息不丢失」冲突。
  （background_tasks 注入今天已有同款预存暴露，非新机制缺陷，但 M1 接上用户 steer 后首次对用户可见。）
- 影响范围: 仅本 milestone（registry.py 终止路径 + 该 sse 回归测试）；不影响 M2。
- 候选: A=cancel/abort 终止路径也 drain→stranded 续跑（架构最干净）；B=接受丢失改测试（不推荐）。
- 状态: 已 SendMessage orchestrator，等定夺；R3 实现/测试本地提交、未 push。

## R3 — <pending(等 design 定夺后回填)>

## R4 — <pending>
