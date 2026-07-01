# bugfix-450: running subagent resume delivery

## Relations

- Related: feat-337
- Related: feat-449

## 原始报告

> http://127.0.0.1:8011/chat/15f966bf556a4d8492681bbc5bb56280 主agent给subagent发了resume prompt了。但是subagent收到了吗？你去从jsonl实际分析下

> 所以这是个bug吧，为啥有这个问题

> 你分析哪种做法最合理

> 看下当初设计这个现有做法的unit

> 看当时是怎么设计的。

> 继续

> 所以resume subagent压根就没成功过？

> 当时的feature的spec中还没有这个需要测的场景吗

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 修复这个问题。

## 澄清记录

- Q1: 这单的范围是只修 running subagent 的 resume/follow-up 必须真实投递并被消费，还是也顺手重做 subagent continuation / notification / output_file 相关的其他后台任务语义？
  A(原话): ok
  Agent 解读: 按推荐范围推进：只修 running subagent resume/follow-up 这条链路；其他后台任务语义只做必要回归验证，不扩大重构。

## 现象与复现

用户在 IM 会话 `15f966bf556a4d8492681bbc5bb56280` 中要求主 agent 给正在运行的 fix worker subagent 发送 resume prompt，让它汇报当前进度。主 agent 的 `Agent(agent_id=..., prompt=...)` 工具调用返回 `message_queued`，并向用户报告“已向 fix worker 发送 resume 消息”。

实际取证结果显示，这条消息只在主 agent 侧显示为 queued，没有进入 subagent：

1. 主 agent 会话 JSONL：`/Users/czj/nano-assistant/workspace/luban/.nanoassistant/sessions/sess_a6633fce2b4b3ed5.jsonl`
   - line 249：主 agent 启动后台 subagent，返回 `agent_id: abfdbf8376f766225`。
   - line 260：主 agent 调用 `Agent(agent_id="abfdbf8376f766225", prompt="请暂停当前工作，立即回报当前进度...")`。
   - line 261：工具结果为 `status: message_queued`。
2. subagent 会话 JSONL：`/Users/czj/nano-assistant/workspace/luban/.nanoassistant/sessions/sess_a6633fce2b4b3ed5/subagents/sess_c7f266dbd76ae6d8.jsonl`
   - 文件停在 line 85，最后写入时间为 2026-06-30 11:21:58 本地时间。
   - 没有出现主 agent 在 12:19 发送的 resume prompt。
   - 没有后续 LLM request 或 tool result 证明 subagent 收到并处理了该消息。
3. LLM proxy 日志：
   - subagent 对应目录 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-06-30_11-13-37_165_sess_c7f266dbd76ae6d8` 停在约 11:22。
   - 12:19 的 resume prompt 只出现在主 agent 的 LLM request 中，没有出现在 subagent 的 LLM request 中。

用户可见结果是：系统告诉主 agent “Message queued for agent”，但目标 subagent 实际没有收到 resume/follow-up。这会误导主 agent 和最终用户以为已经成功打断或追加指令。

## 影响范围

受影响的是所有仍处于 `running` 状态的 subagent continuation 场景：

- 主 agent 使用 `Agent(agent_id=..., prompt=...)` 给 running subagent 追加指令、要求汇报进度、调整范围或停止当前方向时，工具返回成功但消息不会进入 subagent。
- 用户通过主 agent 间接要求“让那个 subagent 先汇报 / 改方向 / 继续查某件事”时，会得到虚假的成功反馈。
- 多 agent 编排流程中，orchestrator 向正在工作的 worker 发送 resume/follow-up 的协作语义不可信。

不受此问题直接影响的路径：

- subagent 已经 terminal 后，再用 `Agent(agent_id=..., prompt=...)` 续接的新一轮 run。这条路径走 JSONL/session 恢复或 terminal resume，不是本次取证中的假 queued 路径。
- 后台任务完成通知、读取 `output_file`、`task_stop` 等能力本身不是本单修复目标；本单只要求它们在相关回归范围内不被破坏。

未发现数据损坏。主要风险是控制面假成功：主 agent 根据错误的 tool result 作出后续计划，用户以为 subagent 已经收到指令，实际工作流继续偏离。

## 用户场景

主 agent 启动一个后台 subagent 处理较长任务。任务运行期间，用户或 orchestrator 发现需要补充指令：可能是让 worker 立即汇报当前进度，可能是要求它改查另一个方向，也可能是让它先停下正在做的部分工作。

用户不会直接操作 subagent 的内部 runtime；用户只会在主对话里告诉主 agent“给那个 worker 发个 resume / 让它汇报”。主 agent 通过 `Agent(agent_id=..., prompt=...)` 把这条 follow-up 发给已存在的 subagent。此时系统可以返回“消息已排队，等 subagent 下一安全点处理”，但这个反馈必须是真的：subagent 后续应能实际收到这条消息，并把它纳入同一个 worker 会话。

如果系统无法把消息交给仍然活着的 running subagent，就不应该告诉主 agent 已经成功排队。对用户而言，最坏情况可以是明确失败或要求重试；不能是静默丢消息后仍显示成功。

## 验收标准

### Requirement: running subagent follow-up 真实投递

#### Scenario: 用户要求正在运行的 subagent 汇报进度
- **GIVEN** 主 agent 已启动一个仍在运行的后台 subagent
- **WHEN** 用户要求主 agent 给该 subagent 发送 resume/follow-up，让它汇报当前进度
- **THEN** 主 agent 不应只得到虚假的成功反馈
- **AND** 该 subagent 后续应能实际响应这条 follow-up，或在可读的 subagent 输出中体现它收到了这条 follow-up

#### Scenario: follow-up 在安全点处理
- **GIVEN** subagent 正在执行一个工具轮次或等待当前模型响应完成
- **WHEN** 主 agent 给该 subagent 发送 follow-up
- **THEN** 当前执行不应被中途破坏
- **AND** follow-up 应在下一安全点进入同一个 subagent 会话继续处理

### Requirement: 不再返回假 queued 状态

#### Scenario: 目标 subagent 无法接收 running follow-up
- **GIVEN** 主 agent 持有某个 subagent 的 `agent_id`
- **WHEN** 主 agent 尝试发送 follow-up，但系统无法确认目标 running subagent 能接收该消息
- **THEN** 主 agent 不应看到表示已成功排队的结果
- **AND** 用户应能从主 agent 的后续反馈中知道这条 follow-up 没有被当作已送达处理

### Requirement: 既有后台任务体验不退化

#### Scenario: 已完成 subagent 继续会话
- **GIVEN** subagent 已经完成并保留可读输出
- **WHEN** 主 agent 使用同一个 `agent_id` 继续该 subagent 会话
- **THEN** 用户仍能看到它作为同一个 subagent 的后续工作继续完成，而不是新建无关 worker

#### Scenario: 用户读取后台输出
- **GIVEN** 后台 subagent 已启动或已完成
- **WHEN** 主 agent 或用户读取该 subagent 的 `output_file`
- **THEN** 输出文件仍然可用于了解 subagent 的过程和结果

## 范围与非目标

- 在范围：修复 running subagent 的 resume/follow-up 假成功问题。
- 在范围：确保 `message_queued` 对用户和主 agent 的语义可信。
- 在范围：补上能防止“只测 registry 入队、不测 subagent 消费”的回归验证。
- 在范围：验证 terminal subagent resume、后台完成通知、`output_file` 读取、`task_stop` 不被本修复破坏。
- 非目标：重做整个 background task 系统。
- 非目标：改变 subagent 的用户可见 ID、`output_file` 读取方式或后台完成通知产品语义。
- 非目标：新增一个单独的后台任务查询工具。
- 非目标：允许 follow-up 中途打断正在执行的工具、shell、文件编辑或 LLM stream。

## 根因分析（RCA）

### 直接根因

running subagent continuation 的消息队列没有消费者。

当前 `Agent(agent_id=..., prompt=...)` 对 running subagent 的处理逻辑是：

1. 从 background task registry 找到 `agent_id` 对应的 running subagent record。
2. 调用 `BackgroundTaskRegistry.enqueue_agent_message(agent_id, prompt)`。
3. 立即返回 `status: message_queued`。

但是实际运行 subagent 的 worker 不读取 `BackgroundTaskRegistry._pending_messages`，也没有把这条 pending message 注入到 subagent 的下一次 LLM request 或 transcript。`drain_agent_messages()` 只被测试直接调用，生产 runtime/agent loop 没有消费它。

这导致 `message_queued` 只是“写入 registry 内存 list 成功”，不是“目标 subagent 已接受待投递消息”。

### 原始设计意图追溯

该行为来自原始 unit `feat-337-cc-background-subagents`，设计目标是对齐 Claude Code 的后台 agent task 体验。

原始设计明确要求保留的能力：

- running subagent 收到 `Agent(agent_id=..., prompt=...)` 时，不启动第二个并发 run。
- prompt 进入该 subagent 的 pending message 队列。
- subagent 在安全点消费 pending messages：当前 LLM response 完成、当前工具执行批次完成、下一次 LLM request 构建前。
- 消费时，按 FIFO 把 pending messages 作为 user-role input 追加到该 subagent runtime session 和 transcript。
- 主 agent 可立即收到 `message_queued`，但该状态的语义应是“已被投递机制接收，等待目标 subagent 下一安全点处理”，不是“写进无人消费的 registry list”。

修复必须保住的不变量：

- 不能为了避免假成功而删除 running subagent follow-up 能力。
- 不能在 subagent 正在执行 tool、shell、文件编辑或 LLM stream 中途强行打断。
- 不能为同一个 running subagent 启动第二个并发 run 来处理 follow-up。
- 必须保持 FIFO 追加语义。
- 一旦向主 agent 返回 `message_queued`，后续必须能在 subagent transcript / 下一轮 LLM request 中观察到该消息被交付。

### 回归 / 引入点

这不是近期回归，而是 `feat-337` 首次落地时就存在的半实现。

引入 commit：

- `3555e11c36234322017484ee59b9e1b90f7108f8`
- commit message: `feat(337): CC-style background tasks`
- 时间：2026-04-29 16:45:22 +0800

该 commit 同时引入了：

- `src/agent/platform/tools/builtins/agent.py` 中 running continuation 返回 `message_queued` 的逻辑。
- `src/agent/core/background_tasks/registry.py` 中 `_pending_messages`、`enqueue_agent_message()`、`drain_agent_messages()`。
- `tests/integration/background_tasks/test_agent_continuation.py` 中只断言 registry 能 drain 到 pending prompt 的测试。

### 为什么能进来

验收和测试把“入队成功”误当成“投递成功”。

`feat-337` 的 spec/design 中已经写了 running follow-up 必须在下一安全点被 subagent 消费，但验收标准和测试策略没有把“真实进入 subagent transcript / 下一次 LLM request”列成必须验收项。最终测试只做了：

1. 启动一个 running subagent。
2. 发送 follow-up。
3. 断言工具返回 `message_queued`。
4. 手动调用 `registry.drain_agent_messages(agent_id)`，确认 registry list 里有 prompt。

这个测试没有驱动真实 subagent worker 到下一安全点，也没有检查 subagent JSONL 或 LLM request。因此实现只完成了“pending list 存储”，缺失“runtime 消费”仍然通过了验收。

## 修复方向

本单修复 running subagent resume/follow-up 的用户可见语义：主 agent 对 running subagent 发送 follow-up 后，不能只得到一个虚假的 `message_queued`。该消息必须被目标 subagent 的 live runtime 接收，并在下一安全点作为 user-role input 进入同一个 subagent 会话；用户和主 agent 后续应能从 subagent transcript、LLM request 或最终输出中看到该 follow-up 的影响。

高层要求：

- `message_queued` 只能在系统已经把消息交给可消费的 live subagent 投递链路后返回。
- 如果目标 subagent 已经不再 running，应走 terminal resume 语义或返回明确失败，不得继续返回假 queued。
- 保留安全点消费，不允许中途打断 tool execution 或 LLM stream。
- 保留同一 `agent_id`、同一 subagent transcript/output file、FIFO 顺序。
- 增加回归测试：测试必须证明 running follow-up 真实进入 subagent runtime session / transcript / 下一次 LLM request，而不是只检查 registry 里存在 pending string。
- 回归验证 terminal subagent resume、后台完成通知、`output_file` 读取和 `task_stop` 不因本修复退化。
