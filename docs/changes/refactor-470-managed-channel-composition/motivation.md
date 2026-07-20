# refactor-470: 收回 managed channel composition ownership

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-461, refactor-463, feat-464

## 原始诉求

> 有没有巨石单文件的问题

> personal_assistant/main.py的问题，确实不适合笼统的重构，应该深入分析。你分析吧

> 加到你的架构review报告中吧

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 专门做Candidate 05

## 澄清记录

- Q1: 这个 unit 是否完整覆盖 Candidate 05——既收回 managed channel ownership，也把 `GatewayRuntime`、进程生命周期、heartbeat runner、kernel adapter 等已成形深模块整体迁出 `main.py`？
  A(原话): 对
  Agent 解读: 本 unit 完整覆盖 Candidate 05；已成形的深模块只整体迁移，不重新拆解或改变其既有行为，同时清理 `main.py` 的 test-only re-export。
- Q2: 验收回归面是否覆盖 Gateway 的全部现有用户行为，包括消息路由与回复、managed channel 热调和与离线自治、IM 重连、启停、heartbeat 和 cron？
  A(原话): 成本可能过高
  Agent 解读: 用户对逐项覆盖 Gateway 全部现有行为的验收成本有明确顾虑；尚未确认是缩小重构范围，还是保留完整范围并缩减为分层、代表性回归。
- Q3: 成本控制上，是否保留完整 Candidate 05 的重构范围，但只对直接受影响的关键旅程做用户侧验收，其余行为依靠现有自动化回归？
  A(原话): 测试可能受影响的，哪些受影响的，你来判断
  Agent 解读: 用户授权 Agent 基于实际迁移边界与调用链判断受影响的测试和用户旅程；重构范围仍按 Q1 的完整 Candidate 05，不要求人工覆盖 Gateway 全部契约。
- Q4: 旧 standalone YAML → managed manifest 的自动导入与 legacy export 不属于长青契约；本次是把它们继续搬进新 owner，还是干净截止、只保留 `channels.bootstrap` 协议？
  A(原话): 好
  Agent 解读: 用户确认干净截止：删除自动导入、明文 cleanup、legacy export 及专属兼容测试，不保留 bootstrap provider/applied no-op callback 或 alias；`channels.bootstrap` wire handshake 仍存在并直接回空 items。旧明文 YAML Feishu 仍可沿现有 standalone static channel 路径启动，但不再自动出现在 IM managed channel 中。仍依赖自动导入的部署须在升级前使用当前版本完成一次迁移。

## 现状痛点

`personal_assistant.main` 是 Gateway 的进程入口。终端用户通过 Web IM 或飞书与 Agent 对话，运维者通过该入口启动、停止和重启 Gateway；进程还负责 heartbeat、cron、IM 重连和 managed channel 的动态配置。这个入口承载的产品行为广，但“入口广”本身不是问题：已经成形的 `GatewayRuntime`、进程生命周期、heartbeat runner、IM bootstrap client 和 kernel adapter 都有窄而连贯的职责，删除它们只会把生命周期复杂度重新摊回调用方。

真正的问题集中在 composition ownership：当前 `main.py` 有 3,987 行，其中 `build_runtime()` 单个函数占 927 行，并用 25 个嵌套 closure 同时连接和实现运行策略。managed channel 的凭据解封、缓存迁移、provider 构建、Agent 能力激活、状态上报、ACK/retry、重连对账等不变量滞留在 composition root；其中能力激活还穿透 Agent 配置同步对象的 private API。于是维护者修改一个 channel 生命周期行为时，必须同时理解配置、IM 连接、状态 outbox、provider 和 live Agent 状态的隐含协作关系。

文件还是测试 service locator：当前 38 个测试文件从 `personal_assistant.main` 导入 30 种符号，其中一部分只是入口为测试重新导出的其他 owner 实现。生产代码没有把 `main` 当公共库使用，但测试布局让移动真实 owner 时产生广泛、低价值的 import churn，也容易把“入口仍能导入私有符号”误当成行为契约。

若不治理，后续新增 provider、修改状态确认或调整重连收敛时，仍会经过同一个串行集成热点；而若只按行数拆文件，又会把现有深模块拆成薄 wrapper 和共享状态，增加 interface 而没有消除复杂度。

## 目标状态

本变更完整覆盖 Candidate 05，但不新增产品能力：`main` 只保留命令入口、顶层 composition 和启动委托；managed channel 的完整控制生命周期有单一、可说明的 owner，composition 不再实现 credential、provider、status、retry 或 reconcile policy，也不穿透其他 owner 的 private state。

已经成形的 Gateway runtime、进程生命周期、heartbeat runner、IM bootstrap client 和 kernel adapter 保持现有深度与职责，整体迁移到真实所有者位置，不重新拆解其内部生命周期。测试直接面向真实 owner；只为旧 `main` namespace 存在的 compatibility re-export 被删除，不再建立第二套兼容表面。

成功标准是 ownership、locality 和测试表面变清楚，不是达到某个文件行数。重构后，current `credentialRef` / encrypted manifest 配置格式、持久化数据、IM/Gateway 协议、channel identity、会话历史和用户可见行为均保持不变。唯一明确退休的行为是 Q4 所述非契约 legacy bridge：旧明文 YAML channel 继续作为 standalone static channel 启动，但新版不再替它自动生成 managed manifest、回写 `credentialRef` 或提供 legacy export。

## 用户侧验收标准（不变性）

本单元只把**直接经过迁移边界**的旅程列为用户侧验收面，不重复验收 Gateway 的全部长青契约。入站并发、图片、权限审批、群背景、运行中插话和回复渲染等既有 owner 不变，由原有自动化回归守护。

### Requirement: Managed channel 在线控制行为保持一致

#### Scenario: 在线保存后无需重启即可使用
- **GIVEN** Gateway 已连接 IM，用户为某 Agent 保存一份有效的飞书 channel 配置
- **WHEN** IM 把最新配置下发到该 Gateway
- **THEN** 对应飞书 Bot 无需重启 Gateway 即可连接，用户能在飞书发消息并在原对话收到正确 Agent 的回复，与变更前一致
- **AND** IM 通道页显示真实连接终态，Agent 原有 skills 不被移除，所需飞书文档能力仍可用

#### Scenario: 无效配置不伪装成功且不影响其他 Bot
- **GIVEN** 同一 Gateway 上已有其他正常工作的飞书 Bot
- **WHEN** 用户保存一个凭据无效或权限不完整的 managed channel
- **THEN** IM 通道页显示真实失败或降级诊断，不把该配置展示为已正常应用
- **AND** 其他 Bot 的连接和消息收发不受影响，与变更前一致

#### Scenario: 停用、删除或替换只作用于目标 channel
- **GIVEN** 同一 Gateway 上有多个 managed channel
- **WHEN** 用户停用、删除或替换其中一个 channel
- **THEN** 目标 Bot 按现有语义停止或切换，其他 Bot 继续工作
- **AND** 已有 IM 影子会话和消息历史不被删除，channel identity 与会话连续性保持现有规则

### Requirement: Managed channel 离线自治与重连收敛保持一致

#### Scenario: IM 离线重启后缓存 channel 仍可用
- **GIVEN** 某 managed channel 已成功应用并缓存，随后 IM 服务不可达
- **WHEN** 运维者重启 Gateway，用户从该飞书 Bot 发送消息
- **THEN** Bot 仍从本地缓存启动并正常回复，本次 IM 同步允许暂时缺失，与变更前一致

#### Scenario: IM 恢复后收敛到最新配置
- **GIVEN** Gateway 与 IM 断连期间，IM 中的 desired channel 配置发生变化
- **WHEN** Gateway 重连并完成对账
- **THEN** channel 自动收敛到 IM 当前配置，失败或未确认结果继续按现有规则重试
- **AND** 旧状态不覆盖当前 channel 状态，用户无需手工重启 Gateway

### Requirement: Gateway 服务生命周期保持一致

#### Scenario: start、stop、restart 结果不变
- **WHEN** 运维者按现有命令启动、停止或重启 Gateway
- **THEN** 后台单实例、启动反馈、优雅关闭和超时升级结果与变更前一致
- **AND** 已接纳的运行在关闭时进入明确终态，不遗留另一套 Gateway 或 Kernel 进程

#### Scenario: 新节点自动绑定行为不变
- **GIVEN** Gateway 首次连接一个尚未绑定 owner 的 IM 节点，并启用现有 auto-bind 配置
- **WHEN** 运维者启动 Gateway
- **THEN** 节点自动完成绑定且不打开浏览器，随后进入正常连接与配置对账，与变更前一致

### Requirement: Heartbeat 与 Cron 主动行为保持一致

#### Scenario: Heartbeat 有内容时冒泡、无内容时静默
- **GIVEN** 某 Agent 已启用 heartbeat
- **WHEN** heartbeat 到点且分别遇到有可冒泡内容或无可行动内容的情况
- **THEN** 有内容时仍在 canonical 直聊中发送可追问的消息，无内容时仍保持静默，与变更前一致

#### Scenario: Cron 定时与手动运行保持现有语义
- **GIVEN** 某 Agent 已启用 cron 并存在可运行任务
- **WHEN** 任务到点或 Agent 手动触发该任务
- **THEN** 任务仍按现有隔离 session、结果投递和运行历史语义完成，不串到其他 Agent

## 影响范围

- Gateway 入口、runtime resource graph、后台进程生命周期、IM bootstrap、heartbeat/cron runner 和 kernel adapter 的物理归属与 import 路径。
- managed channel 的凭据与 manifest cache、provider runtime 构建、Agent 能力激活、状态/metadata 上报、ACK/retry、重连对账和关闭顺序。
- `personal_assistant.main` 的测试表面：真正的入口与 lifecycle 命令仍从入口测试；runtime delivery、Agent 配置解析等 test-only re-export 改为从真实 owner 测试并删除旧转发。
- **必须按行为重验**：managed channel manager/store/apply/status/outbox/reconcile 集成，Gateway runtime 启停与资源关闭，IM bootstrap/auto-bind，heartbeat/cron runner，外部 channel 冒烟链路。
- **仅需迁移 import 并跑原回归**：InboundPipeline 的并发/插话/图片/群背景、permission、runtime delivery observer 等未改变 owner 的测试；不为它们新增重复的人工验收旅程。
- 不改变 IM、Kernel、CLI 或外部 channel 的协议，不由本 unit 在线迁移用户配置/会话/消息数据，不增加新 provider 或用户设置。旧 YAML 部署若希望进入 managed control，必须在升级前由当前版本完成迁移；新版不会自动迁移。

## 迁移与回滚策略

1. **行为切片迁移**：先以现有测试固定直接受影响的用户行为，再按 managed channel control、runtime lifecycle、后台进程、heartbeat/cron、bootstrap/adapter 的完整职责切片迁移；每个切片保持可独立验证和回退。
2. **单一 owner 切换**：同一策略在任一时刻只有一个执行 owner；不长期保留双写、双启动、feature flag 或从 `main` 转发到新位置的兼容 shim。
3. **成熟深模块整体迁移**：`GatewayRuntime` 等已经封装生命周期不变量的实现只改变物理归属与依赖接线，不借本单元重写内部算法或扩展产品语义。
4. **测试随 owner 迁移**：入口命令测试保留在 `main` 表面；其余测试先切到真实 owner，再删除 test-only re-export。测试文件拆分继续遵守单文件大小契约，不以放宽 guardrail 换取迁移便利。
5. **回滚边界**：任何切片若无法证明上文直接受影响的 channel、启停、auto-bind 或 heartbeat/cron 行为不变，则整体回退该切片；回滚代码即可恢复旧 composition，不改变或回写用户数据。
6. **Legacy 截止**：删除 standalone YAML → managed manifest 的自动导入、明文 cleanup 与 legacy export；保留 `channels.bootstrap` wire handshake 和 standalone static channel 启动。实现与测试不得把已删除路径改名后续命。
