# bugfix-420: task_stop 后台任务后多发空壳 `<task-notification>`，与 tool_result 重复

## Relations

- Related: bugfix-417（PR #116，前台双通道治理）、feat-337-cc-background-subagents（commit 3555e11c，本机制引入单元）
- Refs: bugfix-418（#117，前台跨事件循环崩溃，与本条无关，仅相邻）
- Closes: #123

## 原始报告

> ## 现象
>
> IM 上让 agent 派一个**后台** subagent，再让它 `task_stop` 掉。LLM 在同一条停止动作里收到**两条几乎逐字重复**的信号：
>
> 1. `task_stop` 工具的 **tool_result**：`Task stopped. task_id: a890... status: killed output_file: /.../sess_5f38...jsonl`
> 2. 下一轮 user 输入里又来一条 **`<task-notification>`**：
>    ```xml
>    <task-notification>
>      <task-id>a890c8f0ef965ffd7</task-id>
>      <agent-id>a890c8f0ef965ffd7</agent-id>
>      <output-file>/.../sess_5f38...jsonl</output-file>
>      <status>killed</status>
>      <summary>Agent "Explore nano-multiagent repo" killed</summary>
>      <error>stopped by user</error>
>    </task-notification>
>    ```
>
> 第二条 `status killed` / `output-file` 与第一条全重，**没有任何新增 payload**——纯噪声重复。
>
> 实测：proxy log `2026-06-22_11-10-19_599_sess_a6bc5b8677ab20ec/2026-06-22_11-16-11_260-req`，消息 [16]（tool_result）+ [17]（task-notification）。
>
> ## 与 bugfix-417 / bugfix-418 的关系
>
> - **不是回归**：`task_stop` 后发通知是 `feat-337-cc-background-subagents`（commit 3555e11c，M7-task-stop）的原始设计（`task_stop.py:26` 工具描述就写「a notification will be sent to the parent session」；design.md:465-467「标记 killed → 对父会话发送 killed notification」）。
> - **bugfix-417（PR #116）只治了「前台」双通道**，其 M7 设计 item ③ 明确**保留**「run_in_background + task_stop 仍发通知」。所以本条是 417 故意没碰的相邻面。
> - 与 bugfix-418（#117，前台跨事件循环崩溃）无关。
>
> ## 根因
>
> `feat-337` 把 CC 的「终态即通知父会话」复刻成了**无差别统一通知**：`registry.kill()`（`core/background_tasks/registry.py:158`）没有 `complete()` 那样的 `notified` 抑制参数，`task_stop.py` 对 bash / subagent 一视同仁调 `registry.kill(reason="stopped by user")` → 终态转换经 notifying-store wrapper 统一发通知，**不区分「谁触发的终态」、也不带部分结果**。
>
> ## CC 的正确设计（参考源码已核实）
>
> CC `src/tasks/stopTask.ts:67-95` 按任务类型分两支：
>
> ```ts
> // Bash: suppress the "exit code 137" notification (noise). Agent tasks: don't
> // suppress — the AbortError catch sends a notification carrying
> // extractPartialResult(agentMessages), which is the payload not noise.
> if (isLocalShellTask(task)) {
>   // 标 notified:true → 抑制 model-facing <task-notification>，只给 SDK 发终止事件
> }
> ```
>
> - **停后台 bash** → **抑制**通知（避免「exit 137」噪声）；LLM 只看到 tool_result。
> - **停后台 subagent** → **保留**通知，但通知里带 `<result>` = 子 agent 被杀前最后一段 assistant 文字（`enqueueAgentNotification({status:'killed', finalMessage})` → `LocalAgentTask.tsx:302/310-315`）。`finalMessage` 来自全程累积的 `assistantMessages`，abort 只停循环不清消息，杀完从尾部抽最后一个 text block（`query.ts:1696-1710`）；没攒到则省略 `<result>`。即通知是**带半成品的有用回执**，非冗余。
>
> 对照我们：bash 没抑制、subagent 通知是空壳（缺 `<result>`）——CC 两条分支我们都偏了。
>
> ## 修复方向（对齐 CC）
>
> - **停后台 bash** → 抑制 model-facing `<task-notification>`（给 `registry.kill` 加 `notified=True` 能力 / 或在 task_stop 路径标 notified），与 bugfix-417 前台同 principle。
> - **停后台 subagent** → 让通知携带部分结果：从子 agent 已落盘/已累积 transcript 抽最后一段 assistant 文字塞进 `<result>`（我们 runtime_runner 已有等价 helper `_extract_assistant_text`），杀太早没产出则省略 `<result>`。
>
> ## Severity
>
> minor（冗余/噪声；空壳 killed 通知可能轻微误导模型以为有结果返回，但内容明确写 killed）。建议走独立小 bugfix（spec→design），spec 阶段把上述 CC `stopTask.ts` / `LocalAgentTask.tsx` / `query.ts` 证据钉进去。

## 澄清记录

- Q1: 停后台 subagent 时，通知该怎么处理？（停后台 bash 抑制通知两方案一致，无分歧）
  A(原话): 对齐 CC：带部分结果（推荐）
  Agent 解读: 停后台 subagent 保留 `<task-notification>`，但通知里 `<result>` 携带子 agent 被杀前最后一段 assistant 文字；杀太早没产出则省略 `<result>`。停后台 bash 抑制 model-facing 通知（LLM 只看 tool_result）。这是完整对齐 CC `stopTask.ts` 两分支，而非「subagent 也一并抑制」的最小止噪方案。

## 现象与复现

**环境**：IM Web 前端 + Gateway，agent 走后台 subagent 派发。

**复现步骤**：
1. 在 IM 上让某 agent 派一个**后台** subagent（`run_in_background=true`），例如「Explore nano-multiagent repo」。
2. 子 agent 还在跑时，让父 agent 调 `task_stop` 把它停掉。
3. 观察父会话收到的消息序列。

**期望**：父会话（LLM）收到**一条**明确的停止信号——`task_stop` 的 tool_result 说明任务已 killed。

**实际**：父会话收到**两条几乎逐字重复**的信号——
- tool_result：`Task stopped. task_id: a890... status: killed output_file: /.../sess_5f38...jsonl`
- 紧接着下一轮 user 输入里又一条 `<task-notification>`，其 `<status>killed</status>` / `<output-file>` / `<task-id>` 与 tool_result 全重，且**无 `<result>` 半成品**——纯噪声重复。

**实测证据**：proxy log `2026-06-22_11-10-19_599_sess_a6bc5b8677ab20ec/2026-06-22_11-16-11_260-req`，消息 [16]（tool_result）+ [17]（task-notification）。

后台 bash 停止路径同理：`task_stop` 后会多发一条携带 killed/exit 信息的 `<task-notification>`，与 tool_result 重复（对应 CC 抑制的「exit 137」噪声）。

## 影响范围

- **谁受影响**：所有在后台派 subagent / bash 后又主动 `task_stop` 的会话（IM agent、个人助手、coding CLI 均可触发）。
- **严重度**：minor。功能不受损，停止动作本身正确（任务确实被 killed）。问题是**冗余噪声**：
  - 停 bash：多一条无新增 payload 的 killed 通知。
  - 停 subagent：多一条**空壳** killed 通知——缺 `<result>`，且与 tool_result 重复。空壳 killed 通知**可能轻微误导模型**以为有结果返回（实际只有 status），但内容明确标 killed，误导有限。
- **数据损坏**：无。纯交互信号层面的冗余/丢失（子 agent 半成品产出未回传给父会话）。

## 目标状态 / 验收标准

> 此 bugfix 的「用户」是消费通知的父会话（LLM）；其可观察面是父会话收到的消息流（tool_result + 后续 user-role 的 `<task-notification>`），reviewer 可经真实旅程 + proxy log 观察验收。

### Requirement: 停后台 bash 不再多发冗余通知

#### Scenario: 停一个仍在跑的后台 bash
- **GIVEN** 父会话派了一个后台 bash 任务且它仍在运行
- **WHEN** 父会话调 `task_stop` 停掉它
- **THEN** 父会话只收到 `task_stop` 的 tool_result 一条停止信号
- **AND** 后续不再出现与该 tool_result 重复的 `<task-notification>`（model-facing 通知被抑制）

### Requirement: 停后台 subagent 的通知携带半成品产出

#### Scenario: 子 agent 已产出文字后被停
- **GIVEN** 父会话派了一个后台 subagent，它在被停前已产出至少一段 assistant 文字
- **WHEN** 父会话调 `task_stop` 停掉它
- **THEN** 父会话收到一条 `<task-notification>`，`<status>` 为 `killed`
- **AND** 该通知带 `<result>`，内容是子 agent 被杀前最后一段 assistant 文字（带回半成品，而非空壳）

#### Scenario: 子 agent 尚无任何产出就被停
- **GIVEN** 父会话派了一个后台 subagent，它在产出任何 assistant 文字前就被停
- **WHEN** 父会话调 `task_stop` 停掉它
- **THEN** 父会话收到的 `killed` 通知**省略** `<result>`（不发空 `<result>`）

#### Scenario: 停止动作本身仍生效（不变量回归）
- **WHEN** 父会话对任意后台任务（bash / subagent）调 `task_stop`
- **THEN** 该任务确实进入 killed 终态（子进程树被杀 / LLM run 被 abort），与修复前一致

## 范围与非目标

- **范围**：仅 `task_stop` 停止**后台**任务（`run_in_background=true`）后的 model-facing `<task-notification>` 行为——bash 抑制、subagent 携带部分结果。
- **非目标**：
  - 不碰**前台**任务的双通道（bugfix-417 / PR #116 已治理）。
  - 不碰后台任务**自然终态**（正常 completed / failed）的通知行为——那条路径已携带 `result_text`，不在本次范围。
  - 不改 tool_result 的内容/格式（它已是准确的停止回执）。
  - 不引入新的通知字段/协议（只在既有 `<result>` 上做有/无与内容填充）。

## 根因分析（RCA）

### 直接根因

`feat-337-cc-background-subagents`（commit 3555e11c，M7-task-stop）复刻 CC「终态即通知父会话」时，把它实现成了**无差别统一通知**，丢掉了 CC `stopTask.ts` 的按任务类型分支：

1. `src/agent/core/background_tasks/registry.py:158` 的 `kill()` 签名缺少 `complete()` 那样的 `notified: bool = False` 参数——**没有抑制通知的能力**。对照 `complete()`（registry.py:124）已有 `notified` 参数，杀的路径却没有。
2. `src/agent/platform/tools/builtins/task_stop.py:81` 对 bash / subagent 一视同仁调 `registry.kill(task_id, reason="stopped by user")`，**不分任务类型**。
3. 终态转换经 `src/agent/platform/background_tasks/wiring.py:122-128` 的 `_NotifyingStore.update()` 统一发通知：`record.status in {completed,failed,killed} and not record.notified` → `_deliver_notification(...)`。因为 kill 出来的 record `notified=False`，通知必发。
4. 通知里 `<result>` 由 `notifications.py:41` 的 `record.result_text` 决定。`kill()` 路径**从不设置 `result_text`**（只有 `_worker` 正常完成走 `on_complete` 时才有），所以 subagent killed 通知必然空壳。

### 为什么这种错能进来

- feat-337 的 design.md:465-467 只写了「标记 killed → 对父会话发送 killed notification」，**没有区分 bash vs subagent、没有要求携带部分结果**——设计层就把 CC 两分支拍平成一条，复刻保真度不足（未对照 `stopTask.ts:67-95` 的 `isLocalShellTask` 分支与 `extractPartialResult`）。
- bugfix-417（PR #116）治理「前台双通道」时，其 M7 设计 item ③ **明确保留**「run_in_background + task_stop 仍发通知」——是有意识地没碰这块相邻面，不是回归。所以本条是 417 边界外、feat-337 原始设计就偏了的面。

### 原始设计意图追溯（必须保住的不变量）

feat-337 引入后台 subagent + task_stop 的意图：父 agent 能在子任务还在跑时主动叫停，并**得到任务的最终状态回执**。

- 不变量 1：`task_stop` 后子任务确实进入 killed 终态（进程树被杀 / LLM run 被 abort）——**本次修复不得破坏**。
- 不变量 2：父会话仍能感知「这个后台任务停了」——tool_result 已承担此职责；通知层的改动**不能让父会话完全失去停止感知**（停 bash 时 tool_result 仍在，故抑制通知安全；停 subagent 时保留通知并增信息量）。
- 修复方向是**降噪 + 增信息量**，绝不是「为消噪声把通知整个砍掉」导致 subagent 半成品产出永久丢失。

## 修复方向（对齐 CC，高层方案；行级实现在 milestone）

按任务类型分两支处理 `task_stop` 后的终态通知：

1. **停后台 bash → 抑制 model-facing `<task-notification>`**
   - 给 `registry.kill()` 增加 `notified: bool = False` 能力（对齐 `complete()`）；或在 task_stop 路径对 bash 标 `notified=True`。
   - 效果：LLM 只看到 tool_result，与 bugfix-417 前台同 principle（终止信号只走一条通道）。

2. **停后台 subagent → 保留通知，但携带部分结果**
   - 从子 agent 被杀前的 transcript（已累积 / 已落盘）抽最后一段 assistant 文字，塞进通知 `<result>`。runtime_runner 已有等价 helper `_extract_assistant_text`（runtime_runner.py:105）。
   - 杀太早、子 agent 尚无任何 assistant 产出 → 省略 `<result>`（不发空 `<result>`）。
   - 保留 `<status>killed</status>` 与 `<error>stopped by user</error>`：让父会话知道这是用户主动停止、且带回半成品产出——通知从「空壳冗余」变成「带半成品的有用回执」。

> 实现层待 design 拍板的开放问题（spec 不决）：部分结果取自**内存累积 transcript**（abort 路径回传）还是**落盘 output_file**（task_stop 读文件）；abort 与 kill 终态转换的时序如何保证 `<result>` 反映到 abort 点的产出。这些不改变用户可观察行为（父会话最终都看到带 `<result>` 的 killed 通知），留给 `change-design-author`。
