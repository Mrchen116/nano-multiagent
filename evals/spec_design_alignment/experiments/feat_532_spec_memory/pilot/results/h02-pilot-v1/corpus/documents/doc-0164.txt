# bugfix-497: 影子会话 Agent 回复去重与富时间线恢复

## Relations

- Related: feat-447
- Related: bugfix-471
- Related: bugfix-491
- Related: bugfix-496
- Refs: #231

## 原始报告

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 解决[https://github.com/Mrchen116/nano-multiagent/issues/231](https://github.com/Mrchen116/nano-multiagent/issues/231) 问题二

- Issue: https://github.com/Mrchen116/nano-multiagent/issues/231
- 关键原文：「每条 Agent 可见回复出现 **两次**。」

## 澄清记录

- Q1: 如果 IM 在整个 run 期间离线、从未生成 live 富气泡，恢复后需要补齐到什么程度？
  A(原话):
  > 对
  >
  > 恢复后幂等补出唯一的 Agent 正文气泡；如果 live 富气泡已经存在，则 mirror 必须对齐同一条消息，保留其思考、工具、token 和耗时。本期不要求完整重建 IM 离线期间从未落库的思考/工具时间线。
  >
  > 没理解为啥感觉左右脑互驳。前一句和后一句矛盾的？
  >
  > 其实离线的话，后续补的消息，是存在哪里的？就是哪里来的消息，如果“追溯重建离线期间的思考、工具、token、耗时。”，从代码上是不是很不和谐的
  >
  > 意思是现在有些信息是在IM上唯一存储的，gateway没有存，所以无法复原。对吧
  >
  > 我其实希望能完全复原。
  Agent 解读: 即使 IM 在整个 run 期间离线、从未接收 live 运行事件，恢复后也应完整还原该 run 的富时间线，而不只是补一条 Agent 正文；现有存储边界不能降低这一产品目标，所需的持久化与重放契约留给 design 阶段决定。

- Q2: 恢复富时间线时，是直接呈现最终历史状态，还是重演当时的流式过程？
  A(原话): 对
  Agent 解读: 恢复后直接呈现完整的最终历史状态；正文、思考、工具及其顺序和终态、token、耗时与在线时一致，但不重演打字效果、工具运行中动画或原始等待时长。这里的 token “与在线时一致”指保留现有归属口径：中间气泡没有独立 token usage，最终气泡承载整轮累计 usage；本 unit 不虚构或分摊不存在的逐气泡 usage。

- Q3: 如果 IM 先收到部分 live 时间线，随后中途断线，恢复时应如何处理已经存在的半条气泡？
  A(原话): 好
  Agent 解读: 恢复时继续补全原有气泡及其时间线，不删除、不替换、不新增副本；最终结果与全程在线时一致。

- Q4: 这项“单一富消息身份 + 完整离线恢复”只保证飞书，还是适用于所有使用影子会话的外部 channel？
  A(原话): 对
  Agent 解读: 定义为所有外部 channel 的通用行为，以飞书作为本期真实验收入口。

- Q5: IM 恢复连接后，影子会话是否应自动补全；如果用户正打开该会话，是否无需刷新就看到它收敛为完整时间线？
  A(原话): 对
  Agent 解读: 恢复应自动发生；打开中的会话实时补全，刷新或重新进入后看到相同且唯一的最终结果，不需要用户手工触发。

- Q6: 上线修复后，是否需要处理已经写入 Web IM 历史的重复 plain 气泡？
  A(原话): 以前的不管了。新的没问题就行
  Agent 解读: 本 unit 只保证修复上线后的新消息与新恢复过程，不迁移或清理既有重复历史。

## 现象与复现

外部 channel 消息触发 Agent run 时，内部 Web IM 影子会话会先通过 live 投递形成一条完整气泡：正文之外还包含思考、工具时间线、token、耗时和运行终态。相同 Agent 输出随后又被 durable shadow mirror 通过 HTTP 写成另一条仅有正文的消息。因此用户看到相同文案连续出现两次，后一条既重复又缺少上下文。

Issue #231 的生产样例中，同一文案「在呢 bro，有啥事直接说。」形成两行：

- `2026-08-04T02:46:58Z`：live 写入，包含 `kernel_message_id`，显示完整富气泡；
- `2026-08-04T02:47:01Z`：mirror 写入，包含 caller idempotency key，但没有 `kernel_message_id`，只显示正文。

当前代码可稳定复现同一 run 的两条写入：

1. 外部 channel 消息进入已存在的 IM 影子会话，IM 与 Gateway 保持连接；
2. Agent 产生一条可见回复并结束本轮；
3. live observer 依次投递气泡开始、正文增量和完成事件，IM 得到一条富气泡；
4. 同一完成边界又触发 durable shadow mirror，向相同会话创建一条 plain Agent 消息；
5. 打开或刷新影子会话，能看到同文案的两条独立气泡，后一条没有思考、工具、token 或耗时。

期望是每个逻辑 Agent 气泡在影子会话中始终只有一条：在线时保留 live 富时间线；IM 全程离线或中途断线时，恢复后自动收敛为与全程在线相同的完整历史状态。

## 影响范围

- 已在生产飞书影子会话中确认；根因位于共享 external shadow delivery 链路，因此所有使用该链路的外部 channel 都属于产品影响面。
- IM 在线且 live 投递成功时，用户会看到每个 Agent 可见气泡重复出现，第二条信息降质；多气泡 run 会把这种干扰重复到每个可见输出。
- 重复行会永久进入 IM 历史，刷新、重新进入和分页后仍存在，破坏用户对消息顺序、运行过程和指标归属的判断。
- IM 全程离线时，现有 durable 数据不足以完整恢复思考、工具、token 和耗时；仅补正文不能达到用户要求的富时间线恢复体验。
- 没有证据表明 Kernel 会话上下文或外部 channel 回复被破坏；数据影响是 IM 历史新增了降质副本，并且离线期间的富时间线可能无法恢复。
- 按澄清结论，本 unit 不迁移或清理修复上线前已经产生的重复历史。

## 根因分析（RCA）

### 直接根因

同一外部 run 的 Agent 输出由两个彼此不知道对方结果的 IM 写入者处理：

1. live observer 通过 Gateway 与 IM 的 WebSocket 打开 Agent 气泡，持续写入正文、思考和工具事件，结束时写入 token、耗时相关事实、终态及该气泡的 Kernel message identity；
2. 同一个 observer 在外部回复边界把正文与稳定输出身份写入 Gateway 本地 durable shadow saga，并异步调用 shadow mirror HTTP 创建 Agent 消息；
3. HTTP mirror 只携带自己的 caller idempotency key、Agent sender 和正文，不携带 live 已创建气泡的身份或富时间线；
4. IM 的 HTTP 幂等只会复用相同会话中具有同一 caller idempotency key 的消息。live 气泡没有该 key，mirror 消息也没有 live 气泡的 Kernel identity，所以 IM 合法地把它们保存为两条消息。

durable mirror 因而只做到了“自身重试不重复”，没有做到“与已经成功的 live 写入代表同一条消息”。异步 mirror 通常稍晚完成，正好形成 Issue #231 中“先富、后瘦”的时间顺序。

### 原始设计意图与必须保住的不变量

`feat-447` 引入外部 channel 影子会话时，原始目标是让外部用户消息、Agent 回复、思考和工具过程完整同步到内部 IM；飞书触发的回复回到飞书并同步 IM，IM 影子入口触发的回复只留在 IM。M11 进一步要求 Web IM 中每个用户可见 Agent 气泡在外部 channel 只镜像一次，最终气泡不得重复。

`bugfix-471/M2` 后续引入 durable external shadow saga，目标是 IM 离线或 Gateway 重启后仍能按稳定外部事件和输出身份补齐用户消息、Agent 输出与配置边界，同时不阻塞外部 channel 回复。该能力的意图是恢复缺失的原时间线，不是在 live 已成功时再创建一条可见副本。

`bugfix-491` 又要求 stale owner 自愈后继续重放既有 pending saga；本次修复不能通过跳过 pending、删除 durable recovery 或阻塞外部回复来消除重复。

修复必须同时保住：

- IM 暂时离线、Gateway 重启或恢复过程不得阻塞外部 channel 主回复；
- 一个 run 可以产生多个 Agent 气泡，每个逻辑气泡分别保持正文、思考、工具、耗时与终态，并原样保持在线口径的可选 token usage（当前仅最终气泡承载整轮累计 usage）；
- live 与 recovery 共同指向同一条用户可见气泡，重复执行恢复仍只得到一条；
- IM 全程离线时，恢复后仍能完整还原富时间线的最终历史状态；
- IM 中途断线时，恢复补全已存在的半条气泡，不替换或新增副本；
- 外部入口与 IM 影子入口的上下文连续性、回复去向和群聊语义保持不变。

### 回归引入点

commit `a660cc942f5a8654ccd88b478f9033583ed885a3`（`feat(bugfix-471/M2/R2): 持久化边界投递与外部影子事务`）引入 durable shadow output 表、observer 的 shadow output prepare/mirror 调用，以及只写正文的 HTTP Agent mirror。该提交让 mirror 自身具备稳定重试身份，但没有把 live 已创建的 IM 气泡与同一 durable output 关联起来。

### 为什么这种错能进入主线

- `bugfix-471` 正确关注了“外部回复前先持久化 source fact”和“IM 恢复后可以重试”，但把 live 投递与 recovery 补写当成两条并行成功路径，没有定义二者对同一用户可见消息的唯一所有权。
- shadow sync 测试证明相同 caller idempotency key 会复用 HTTP mirror，live observer 测试证明富气泡会持久化逐气泡 Kernel identity；缺少一个跨边界回归，验证两条路径同时开启时最终仍只有一条富气泡。
- 真实离线验收验证了 user anchor、Agent mirror 与配置边界能够补回且各自重放唯一，但没有覆盖“IM live 已成功后 recovery 不得另插消息”，也没有逐项对比恢复后的思考、工具、token、耗时是否与在线路径一致。
- 当前 durable shadow output 只保存输出类型、Kernel identity 和正文。验收把“Agent mirror 已出现”当成恢复完成，没有把“完整富时间线可恢复”列为交付门禁，导致降质补写也能被判断为成功。

## 用户场景与目标状态

用户在飞书或其他外部 channel 与 Agent 对话，同时可能在 Web IM 打开对应影子会话。IM 在线时，同一个 Agent 输出只形成一条气泡：用户可以在这条气泡中查看正文、思考过程、工具调用、token、耗时和最终状态，刷新或重新进入后仍是同一条完整记录。

如果 IM 在 run 开始前已经离线，外部 channel 的对话继续正常进行。IM 恢复或 Gateway 重启恢复后，影子会话自动出现这段对话的完整最终历史：多条 Agent 气泡、各段思考、工具时间线、按既有归属落在最终气泡的整轮 token usage 和逐气泡耗时都与全程在线时一致。恢复只呈现完成后的历史，不重新播放打字、工具运行动画或原始等待时间。

如果 IM 在 run 中途断线，用户可能已经看见半条气泡。恢复后系统在原位置补全这条气泡和后续时间线，既不删除已有内容，也不插入 plain 副本。用户正打开会话时无需刷新即可看到它自动收敛；刷新后的历史与 live 收敛结果一致。

该行为是所有外部 channel 影子会话的通用产品语义，本期使用飞书真实消息作为验收入口。修复只保证上线后的新消息与新恢复过程，既有重复历史保持原状。

## 验收标准

### Requirement: 在线影子会话只呈现唯一完整 Agent 气泡

#### Scenario: 外部 run 产生一条富气泡

- **GIVEN** IM 在线，用户已打开对应外部 channel 的影子会话
- **WHEN** 外部消息触发的 Agent run 产生正文、思考、工具调用、token 和耗时
- **THEN** 用户只看到一条对应该 Agent 输出的气泡
- **AND** 该气泡完整显示正文、思考、工具时间线、token、耗时和最终状态，不出现同文案 plain 副本

#### Scenario: 同一 run 产生多条 Agent 气泡

- **WHEN** 外部消息触发的同一 run 先产生中间 Agent 气泡，经过工具处理后再产生最终气泡
- **THEN** 用户按原始顺序看到每个逻辑气泡各一次
- **AND** 每条气泡只承载属于自己的思考、工具、耗时和终态；中间气泡的 token usage 保持为空，最终气泡保留整轮累计 usage，不被 mirror 再复制或重新分摊

#### Scenario: 刷新在线产生的影子历史

- **GIVEN** 外部 run 已在影子会话中形成完整富时间线
- **WHEN** 用户刷新页面或重新进入该会话
- **THEN** 用户仍看到相同顺序、相同内容且数量唯一的完整气泡

### Requirement: IM 全程离线后完整恢复富时间线

#### Scenario: IM 离线期间外部 channel 正常回复

- **GIVEN** IM 在外部消息触发 run 前已经不可达
- **WHEN** 用户在外部 channel 向 Agent 发送消息
- **THEN** 用户仍在外部 channel 正常收到 Agent 回复
- **AND** IM 不可达不会阻塞或拖延外部主回复

#### Scenario: IM 恢复后自动补齐完整历史

- **GIVEN** 一个外部 run 在 IM 全程离线期间产生了正文、思考、工具调用、token 和耗时
- **WHEN** IM 恢复连接或 Gateway 重启后恢复同步
- **THEN** 影子会话自动出现与全程在线时一致的完整富时间线
- **AND** 每个逻辑 Agent 气泡只出现一次，正文、思考、工具顺序与终态、逐气泡耗时和在线口径的可选 token usage 均完整保留
- **AND** 用户不需要手工触发恢复

#### Scenario: 恢复呈现最终历史而非重演运行

- **WHEN** 用户打开刚完成离线恢复的影子会话
- **THEN** 用户直接看到已经完成的富时间线
- **AND** 页面不重新播放打字效果、工具运行中动画或原始等待时长

### Requirement: 中途断线后补全原有时间线

#### Scenario: live 富气泡写入一半后断线

- **GIVEN** 用户已在影子会话中看到某 Agent 气泡的部分正文、思考或工具过程
- **WHEN** IM 中途断线，随后恢复连接
- **THEN** 已有气泡在原位置自动补全缺失内容、工具终态、token、耗时和最终状态
- **AND** 用户不会看到原气泡被替换、消失或旁边新增 plain 副本

#### Scenario: 打开的影子会话无需刷新即可收敛

- **GIVEN** 用户在 IM 恢复时仍打开对应影子会话
- **WHEN** 缺失的时间线完成恢复
- **THEN** 当前页面自动显示完整且唯一的最终结果
- **AND** 用户刷新或重新进入后看到相同结果

### Requirement: 外部 channel 共享一致的恢复语义

#### Scenario: 飞书真实消息验证通用行为

- **GIVEN** Gateway 已配置可用的飞书 Bot 和对应 Web IM 影子会话
- **WHEN** 用户分别经历 IM 在线、全程离线恢复和中途断线恢复三种对话场景
- **THEN** 三种场景都满足单一气泡、完整富时间线和自动收敛要求
- **AND** 飞书侧继续按既有行为收到 Agent 回复，不因影子同步状态改变回复内容或去向

## 范围与非目标

- 在范围：
  - 修复上线后由外部 channel 新触发的 Agent run 及其影子会话时间线；
  - 在线 live、IM 全程离线、IM 中途断线和 Gateway 重启恢复；
  - 正文、多 Agent 气泡、思考、工具时间线、在线口径的可选 token usage、耗时和最终状态的完整恢复；
  - live 与 recovery 自动收敛为同一用户可见气泡，打开中的会话无需刷新即可更新；
  - 所有使用影子会话的外部 channel 共享同一产品语义，以飞书作为本期真实验收入口。
- 非目标：
  - 迁移、合并或删除修复上线前已经存在的重复 plain 气泡；
  - 在恢复时重演流式打字、工具运行动画或原始等待时长；
  - 改变飞书等外部平台当前接收哪些思考、工具遥测或系统事件；
  - 改变普通 Web IM 会话的展示设计、外部/IM 触发源路由、群聊上下文或权限审批语义；
  - 处理 Issue #231 的 Feishu listener 孤儿进程问题；该问题由独立 unit 跟进。

## 修复方向

让 live 投递与 durable recovery 共同维护一条逻辑 Agent 消息：live 已创建气泡时，恢复只补全同一气泡；live 从未创建时，恢复才创建一次。外部 run 产生的用户可见富时间线事实必须在 IM 不可达和 Gateway 重启后仍可用于完整重建，且恢复完成后向打开中的 Web IM 会话发布同一最终状态。

具体由哪个组件持久化富事件、如何统一 live 与 recovery 身份、如何重放和确认完成，属于 design 阶段的实现决策。方案必须保留外部回复优先、IM 离线自治和稳定幂等恢复，不得通过禁用 live、删除 durable mirror 或只补 plain 正文来规避问题。
