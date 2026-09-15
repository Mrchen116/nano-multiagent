# bugfix-562: 保留被撤回草稿的对话可见性语义

## Relations

- Refs: `docs/changes/archive/feat-544-group-reply-revalidation/`

## 原始报告

> “分析下为啥他会发一个mention”

> “`draft_withheld → reply_process` 的投影的作用是啥，我不太清楚你的内部实现”

> “卧槽，为啥没有这个，得修。”

> “第二个问题，system reminder怎么改，你先给我审下”

用户确认 reminder 应说明“上一段文本是在新消息到达前形成、发布前被撤回、参与者从未收到”，让模型依据这个共享事实自然续答；无需加入“最多只会保留为明确标记未发送的 Process 记录”等对当前续答没有帮助的实现说明。

## 现象 / 复现

在单线程群聊 `c_40adlyhu` 中，Agent 已生成包含完整 heredoc 的回复时收到新消息：

- Kernel transcript 将 8841 字符候选记录为 `output_status.state=withheld`，并继续同一 run 的重校验；
- 该候选没有公开发送，后续模型却把它当成参与者可能见过的“上一条消息”，让对方使用其中的 heredoc；
- Web IM 中前后两个 Agent 气泡均已正常完成，但两者的 `reply_process_json` 都为空，且对应时间段没有 `reply_process.updated` 事件，用户无法从 Process 看到被撤回草稿及其重校验关系。

引入该能力的 `feat-544-group-reply-revalidation` 原本要求同时保持两个不变量：过期候选不得成为公开回复；完整候选仍应作为 Process 事实可追溯，并与消费新消息后的回复段关联。

### Requirement: 被撤回草稿可追溯

#### Scenario: 新消息使完整候选过期

- **GIVEN** 单线程群聊中的 Agent 已形成完整候选
- **WHEN** 新消息在候选发布前到达，Kernel 发出 `draft_withheld` 并消费该消息继续运行
- **THEN** 候选正文不得成为公开回复
- **AND** Web IM Process 必须保留完整草稿、前后回复段关系以及本次重校验所依据的新消息

#### Scenario: 气泡切换的 ack 丢失或延迟

- **GIVEN** IM 已接收气泡切换，但 Gateway 未正常取得该次 ack
- **WHEN** 同一 run 随后继续产生正文或正常结束
- **THEN** Process 事实仍须通过幂等重放落到正确的前后气泡
- **AND** 正文投递不得依赖 Process 展示成功

### Requirement: reminder 传达真实共享上下文

#### Scenario: 模型重做未发送的候选

- **WHEN** Kernel 将候选标记为 withheld 并开始下一次模型调用
- **THEN** system reminder 明确说明紧邻的 assistant 文本在新消息到达前形成、发布前被撤回且参与者未收到
- **AND** 明确更早已成功发布的 assistant 消息仍属于共享对话
- **AND** 要求模型依据更新后的对话状态和原始回复规则继续，必要时补全收件人仍需要的信息

## 根因

`feat-544` 在 Gateway observer 中把一轮重校验拆成多次独立 WebSocket 写入：先单独投影 `draft_withheld`，再完成旧气泡、创建新气泡，最后分别写入 handoff 和 revalidation Process。Process 内容只存在于当前事件和瞬时 `RunDeliveryContext` 标记中。

生产现场证明 Kernel 已产生 withheld 记录，IM 也完成了旧气泡关闭和新气泡创建；但随后没有任何 Process 持久化事件，并出现 `IM observer steer bubble roll failed`。当前异常路径会停止后续 Process 写入并清除气泡局部状态；后续正文可以通过正常气泡投递路径恢复，但没有数据源能重建或幂等重放已经跳过的草稿、handoff 和 revalidation，因此出现“正文正常、Process 永久为空”的部分成功状态。

现有 `tests/unit/personal_assistant/test_reply_revalidation_delivery.py` 直接使用始终成功的 fake ack，覆盖了理想事件顺序，却没有覆盖“IM 已接受切换、Gateway 未取得 ack”这一真实跨进程失败边界。短 reminder 则由 `d7429f4fd` 将此前更完整的共享状态说明压缩成 `previous reply was NOT SENT`，丢失了“参与者从未收到紧邻草稿”和“更早成功发布内容仍可见”这两个区分，模型因而可能把草稿内容当成对方已有上下文。

修复必须保留：公开正文发布仍由 Kernel 的 revision 门禁决定；Process 只记录事实，不把草稿变成公开回复；重复投影按稳定 item id 幂等；全局 Agent 的 inbox / `send_message` 语义不受影响。

## 修复

- `d2f77ab68` 将 withheld reminder 改为已确认的共享上下文说明：紧邻 assistant 文本在新消息到达前形成、发布前撤回且参与者未收到；更早已发布消息仍属于共享对话；模型从更新后的状态按原始回复规则继续，并在需要公开回复时补全对方仍需的信息。该提交还先把 Process 帧改为可重放发送，但独立 code review 发现 handoff / revalidation 仍位于 `turn_start` ack 屏障之后，不能覆盖生产故障。
- `96dd42754` 将气泡切换改为一个可收敛的协议动作：Gateway 为 `turn_start` 提供稳定幂等键，并把 handoff / revalidation 过渡事实作为 sidecar 一并发送；IM 创建或复用同一气泡后，以稳定 item id 将事实落到前后气泡。若第一次请求已被 IM 接受但 ack 丢失，Gateway 用同一键重试并取回同一气泡 ID，后续正文和收尾继续写入该气泡。
- draft 仍在收到 `draft_withheld` 时先进入原有 FIFO 重放队列；公开正文仍由 Kernel revision 门禁决定，不依赖 Process 单项 ack。
- 未改变 global Agent journal、inbox 或 `send_message` 路径。

## 验证

测试策略：扩展现有最低层 owner 测试；Gateway observer 真实模拟“IM 已接受 `turn_start`、ack 丢失”，验证重试复用同一气泡且后续正文可投递；IM handler 测试重复提交同一 `turn_start`，验证只创建一个气泡并幂等保留前后 Process。Kernel 测试保护 reminder 的共享可见性语义。没有新增测试文件或一次性验收脚本。

- 首轮修前失败复现同时覆盖 Process ack timeout 与 reminder 缺失，结果 2 failed；首轮实现后 2 passed。
- 独立 code review 用生产相同时序复现：`turn_start` 已生效但 ack 丢失时，只留下 draft，handoff / revalidation 未入队，正文也失去新气泡目标；该 P1 阻塞首轮交付。
- 纠正后的最窄复验：
  - `pytest -q tests/unit/personal_assistant/test_reply_revalidation_delivery.py::test_reply_process_and_body_survive_accepted_turn_start_ack_loss tests/im_service/unit/test_gateway_handler.py::test_turn_start_replay_persists_reply_process_transition_once`
  - 结果：2 passed。
- 相关 Kernel / Gateway / IM 回归：
  - `pytest -q tests/unit/agent/test_output_revalidation.py tests/unit/personal_assistant/test_reply_revalidation_delivery.py tests/unit/personal_assistant/test_steer_bubble_roll.py tests/im_service/unit/test_reply_process.py tests/im_service/unit/test_gateway_handler.py`
  - 结果：49 passed。
- 连接、持久化与 relay 回归：
  - `pytest -q tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_runtime_delivery_task_tracker.py tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/im_service/unit/test_event_bridge.py tests/im_service/unit/test_repositories_message.py tests/im_service/unit/test_gateway_reply_fanout.py`
  - 结果：92 passed。
- 全量本地非 E2E 门禁：`pytest -q -m 'not e2e'`，结果：3893 passed，35 deselected。
- 静态检查：受影响的 7 个 Python 文件执行 `ruff check`、`ruff format --check` 与 `git diff --check`，均通过。
