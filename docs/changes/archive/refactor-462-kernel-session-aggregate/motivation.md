# refactor-462: Kernel session aggregate

## Relations

- Related: feat-330, feat-394, refactor-406, feat-428, bugfix-437, feat-445

## 原始诉求

> Kernel session aggregate

> 我原本这个仓库设计是希望类似CC的源码那种设计。你看看refactor-462的设计和CC的源码的设计。看看有没有不足的地方。如果有，先不用改。先跟我汇报

> 希望是最终架构。

## 澄清记录

- Q1: 本轮是否需要逐项等待用户确认，还是可由 agent 基于代码证据自主完成 spec 与 design？
  A(原话): 这两个事情，你分别派一个subagent去做完change-spec和change-design。然后你派独立的change-design-reviewer去找问题。明白吗？先跟我对齐想法。
  Agent 解读: 本 unit 由独立 subagent 完成 change-spec + change-design，完成后交独立 reviewer 审查。
- Q2: 除独立 reviewer 外，root 是否还需自行核对设计有没有偏离原治理目标？
  A(原话): 对的。你在派reviewer的同时，你要自己检查，是否符合你想治理的问题。不要走歪了。开始干
  Agent 解读: 用户已批准开始，并授权 agent 依据 live code 自主拍板；设计必须治理 session ownership 的浅 seam，`AgentRuntime` 的改形只服务于消除多 session 双 owner，不能泛化成无关的 runtime 重写。
- Q3: refactor-462 是只做当前架构的稳定化中间站，还是要成为类似 Claude Code conversation ownership 的最终架构？
  A(原话): 希望是最终架构。
  Agent 解读: 不能以加固全局多 session manager 作为终点；设计阶段必须让每个 session 成为独立、长期存活的 conversation module，同时保留 Nano 多 session 常驻进程的产品约束。

## 现状痛点

内核已经以 `agent.sdk` 作为唯一对外面，CLI 与 Gateway 都在进程内持有同一类 Kernel。用户现有的多轮对话、重启恢复、带外消息、上下文压缩、会话分叉、取消恢复和工作区提示均依赖 session 状态在内存与 JSONL 之间保持一致。

当前实现把这份一致性知识拆散了：会话持久化入口在 `SessionManager`，但 `AgentRuntime` 同时持有 history、config、path、lock、memory snapshot、file state、prompt slots 等多组以 session id 为键的平行状态，并直接穿透 manager 的 store/writer 处理定位、修复、写入、flush、失效、压缩和 fork。其它生产调用方也能穿透同一 seam。结果是一次 session 生命周期变更必须跨多处同步维护；过去已经出现带外 append 被旧缓存遮蔽、compaction 只改盘或只改内存、close 漏清 session 槽位等真实回归。

这份分散所有权还跨越了两个真实并发域：普通 run 在 `RunsRegistry` 的专用 event loop 执行，manual compact / whole fork 等 SDK 调用可从产品 event loop 进入，而同步 `append_message` 又可在 run 尚未因 cooperative interrupt 退出时直接改同一份 JSONL。同一 owner loop 上还存在由 `RuntimeRunner` 直接提交的 subagent run，当前不属于 RunsRegistry 的 shutdown task 集合。若只把锁搬进 manager 而不同时收口 loop owner、task completion ownership 与消息 parent 链线性化，结果会是同一 `asyncio.Lock` 被跨 loop await、shutdown 漏掉仍持 lease 的 task，或 stop append 与残余 run write 形成 sibling branch；记录虽在文件中，却可能不在下一轮 materialize 的可达主链上。

另一个容易被缓存掩盖的入口是进程重启后的首次操作：用户或 cron 可以在任何 run cold-load 之前直接同步 append 已有 session。此时“链尾尚未初始化”和“合法空链”必须是两个不同状态；否则首条带外消息会错误地以 `parent=None` 建立第二个 root。

这不是简单把 `AgentRuntime` 拆成更多 helper 的问题。真正需要治理的是 session 尚未成为第一等、长期存活的 conversation module：它的生命周期状态散在 `AgentRuntime` 的平行 map、浅 `SessionManager`、`SessionService` 和 run 调度之间。现有 `SessionManager` 近似 store 转发器；若只把这些状态搬进一个全局多 session manager，仍会保留过宽 interface、跨模块事务知识和全局协调复杂度，不能作为最终架构。

## 目标状态

让每个 active session 成为内核中的独立、长期存活 conversation module；Kernel 只负责按 identity 创建、定位和移除这些对象，run 调度只负责 RunRecord、controller、steer/queue 与任务执行，不拥有 session 持久化事务。调用方只表达“提交一轮”“带外追加”“压缩”“fork”“关闭”等高层意图，不再共同掌握 path、writer flush、平行 cache、parent tail、窗口刷新与清理顺序。每个 conversation module 独占自己的 history/config/path、prompt/file window、current turn context，以及一个内部 transcript module；JSONL parent 链分类、tail 初始化、repair、flush 与 compaction/fork commit 全部隐藏在 transcript 内部，不形成第二个可被调用方穿透的 manager。

同一 session 的生命周期操作必须在该 conversation module 内线性化；不同 session 可以并行。同步带外追加、普通 run、manual compact、fork 和 close 必须进入同一会话所有权协议，且调用方不感知 owner loop、lock、generation、ticket 或 writer。所有会改变 JSONL parent 链的 turn 写入必须从持久化可达 `type=turn` 初始化链尾；`tool_call_recovery` 等 control entry 参与同一写入排序但不属于 parent 链，replay 时生成的 synthetic Message UUID 永不成为持久化 tail。

该 conversation module 必须增加 locality，而不是变成一组字段的搬家点或一堆通用 get/set；删除它时，load→repair→state、submit→persist→loop、append/close/fork/compact 等规则应明显重新散落到多个调用方，证明该 module 确实有 depth。JSONL store 继续保持无状态：session 打开时以绑定的 `workspace_root` 定位 transcript，不新增持久化的中心 session→path registry。

本 refactor 不新增 JSONL entry type 或路径规则、不迁移用户数据、不改变 `agent.sdk` 接口，也不改变 CLI、Gateway 或 IM 的预期行为契约。为让新架构中的 conversation object 在进程重启后仍是完整对象，并兑现 canonical 已承诺的“PromptSlots 整会话不变”，`create_session(prompt=...)` 会把 PromptSlots 的纯文本 seed 写入现有 session metadata 的内核保留键；该键不出现在 SDK metadata DTO。此举会修正 live code 在 Gateway 重启后无法重建 PromptSlots 的 grounding drift，但不新增用户能力；旧档案缺失该键时保持当前重启后的空 PromptSlots fallback，不猜测、也不反向迁移产品配置。

## 用户侧验收标准（不变性）

现有用户仍通过 Coding CLI 或 IM/Gateway 使用同一套会话能力。重构前已经成立的对话连续性、重启恢复、带外消息可见性、压缩与 fork 语义、取消恢复和提示快照语义，在重构后保持一致。

### Requirement: 正常会话连续性保持不变

#### Scenario: CLI 多轮对话与恢复
- **GIVEN** 用户已在 Coding CLI 建立并推进一个会话
- **WHEN** 用户继续多轮对话，或重启 CLI 后恢复该会话
- **THEN** 对话上下文、回复与错误呈现和重构前一致，不丢失已持久化历史

#### Scenario: IM/Gateway 多轮对话与重启恢复
- **GIVEN** 用户已通过 IM 与某 agent 产生多轮对话
- **WHEN** Gateway 继续处理下一条消息，或在进程重启后继续同一会话
- **THEN** agent 看到正确历史并正常回复，用户无需重建会话

### Requirement: 带外消息与终止恢复语义保持不变

#### Scenario: 带外追加进入下一轮上下文
- **GIVEN** 一个已运行过至少一轮的会话
- **WHEN** Gateway 在两轮之间追加消息，随后用户继续对话
- **THEN** agent 的下一轮上下文包含该消息，不被旧内存状态遮蔽

#### Scenario: 重启后首次操作就是带外追加
- **GIVEN** 一个已有多轮 JSONL 历史的会话，Kernel 已重启且尚未在本进程运行该会话
- **WHEN** Gateway 或自动化先经现有同步入口追加消息，随后用户继续对话或再次重启恢复
- **THEN** 新消息接在既有链尾，下一轮可看到完整旧历史与该消息，不产生第二个 root 或不可达分支

#### Scenario: 中断或取消后继续会话
- **GIVEN** 一轮运行在等待模型、工具或权限时被用户中断或取消
- **WHEN** 用户随后在同一会话继续对话
- **THEN** 会话可继续运行，未闭合工具调用被恢复，stop 带外消息与中断前后已经承诺持久化的 run entries 都在下一轮可达历史中，且不会永久阻塞或要求重启内核

### Requirement: 长会话与分支语义保持不变

#### Scenario: 上下文压缩后透明继续
- **GIVEN** 一个会话增长到触发自动或手动压缩
- **WHEN** 用户在压缩后继续对话
- **THEN** 会话正常完成并保持压缩后的记忆语义，重启后仍可从 JSONL 重建

#### Scenario: 从指定消息 fork 会话
- **GIVEN** 用户选择已有会话中的一条消息作为 fork 点
- **WHEN** 产品经现有入口创建分支并继续对话
- **THEN** 新会话继承 fork 点当时的上下文并独立演进，源会话不受影响

### Requirement: 会话级提示与文件上下文语义保持不变

#### Scenario: 会话内提示稳定且在压缩边界刷新
- **GIVEN** 会话已冻结产品 PromptSlots、memory/USER 与工作区 `AGENTS.md` 上下文
- **WHEN** 用户在同一压缩窗口内继续对话，随后跨过一次压缩边界
- **THEN** 同一窗口内提示保持稳定，压缩后的下一轮按既有规则刷新，项目指令去重行为不变

## 影响范围

- `agent` 内核的 session 生命周期、运行时会话状态、JSONL 写入协调、fork/compaction 与相关测试会调整。
- `agent.sdk`、CLI、Gateway、IM 的公开接口与用户行为不变。
- 持久化 entry type、路径规则和已有 JSONL 数据不变；新建会话只在既有开放 metadata map 中增加一个 SDK 不可见的内核保留键，用于恢复 PromptSlots seed。

## 迁移与回滚策略

- 一次性迁移现有生产调用方到 per-session conversation module 的高层事务 interface；不保留长期双写、双 cache、全局 live-state manager 或兼容 façade。
- 用现有 SDK/集成行为测试守住多轮、恢复、带外 append、取消恢复、compaction、fork 与 prompt/file state 生命周期；把依赖私有 map 或 `.store/.writer` 的 white-box 测试改写为 conversation interface 行为测试，仍直接测试 JSONL store 自身的测试除外。
- 现有 JSONL 不做数据迁移；新旧代码读取同一格式。新代码创建的 session 会在既有 metadata envelope 中持久化 PromptSlots seed；旧 session 没有该 seed 时继续使用当前的空 slots fallback，不从易漂移的 agent 配置猜回历史 prompt。若实施期出现无法收敛的行为差异，整体回退本 unit 即可，无需数据回滚。
