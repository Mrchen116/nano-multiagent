# refactor-459: 深化 IM 持久化 module

## Relations

- Related: bugfix-362
- Related: feat-340

## 原始诉求

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 深化 IM 持久化 module。开始spec和design阶段。

## 来源

- 架构审查报告：`docs/research/architecture-reviews/architecture-review-20260711-105616-395a54b5.html` 的 Candidate 01

## 澄清记录

- Q1: 本 unit 是否严格保持用户与 Gateway 可观察行为不变，不借机修复现有行为问题；发现的问题另立 bugfix？
  A(原话): 无需和我沟通，独立直到做到design阶段。我最终review
  Agent 解读: 用户授权按推荐独立决策。本 unit 采用严格行为不变范围；实施中发现的现有行为缺陷不混入本 refactor，另行记录为 bugfix 候选。

## 现状痛点

IM 当前对外承担账号与 owner 隔离、会话和消息持久化、浏览器实时事件、Agent / Node 配置、Gateway relay
等职责。这些用户行为本身已经由 `docs/specs/im/` 定义，本 unit 不改变它们。

内部现状没有形成可信的持久化 seam：部分 WebSocket / application 调用方既调用 repository 方法，
又越过 repository interface 直接读取连接、执行 SQL 或控制 commit。于是同一业务动作所需的查询、映射、
幂等和事务知识分散在多个调用方；测试也会直接植入私有 connection 或 waiter 状态，无法把 repository
interface 当作稳定 test surface。

这种结构不会立刻表现为一个单独的新功能故障，但会持续放大变更风险：owner 隔离、节点上下线、群聊回复
上下文、agent 间投递、shadow conversation、事件回放等行为一旦调整，维护者必须跨 WS、application 与 infra
同时理解 schema 和事务顺序。遗漏任一处，就可能产生用户看不到会话、状态不收口、事件不回放或跨租数据
错误等回归。

## 目标状态

- IM 的持久化规则集中在一个有深度的 persistence module 后面；WS / application 调用方只表达业务意图，
  不再掌握 SQLite schema、查询拼接或 commit 顺序。
- persistence module 的 interface 成为调用方和测试共同使用的 test surface；删除该 module 会让查询、映射、
  幂等和事务复杂度重新散回多个调用方，证明它提供了真实 depth，而非增加传递式抽象。
- 继续使用 IM 当前 concrete SQLite persistence，不为单一 adapter 引入假想 port，也不把实现跨到 Gateway、
  `personal_assistant` 或 `agent` 包。
- 对终端用户、浏览器前端与 Node Gateway 保持严格行为不变；不修改公开 HTTP / WebSocket 契约，不改变现有
  用户数据语义，不借 refactor 顺带修复已知或新发现的产品缺陷。

## 用户侧验收标准（不变性）

现有用户仍通过 Web IM 管理会话、消息、Agent 与 Node；Gateway 仍通过既有 WebSocket 完成注册、中继和过程
事件上报。重构前后的页面、HTTP 响应、WebSocket 帧、持久化结果与重启恢复行为保持一致，没有新增操作入口、
配置项或迁移动作。

### Requirement: 账号隔离与会话消息行为保持不变

#### Scenario: owner 只能访问自己的会话与消息
- **GIVEN** IM 中存在两个不同 owner 的账号及各自会话
- **WHEN** 任一 owner 在 Web IM 或 HTTP 数据面列出、读取、创建或更新会话与消息
- **THEN** 可见范围、成功结果与跨租访问失败语义均与重构前一致

#### Scenario: direct 与 group 会话继续稳定持久化
- **WHEN** 用户创建 direct 或 group 会话、发送消息并重新加载历史
- **THEN** 会话参与者、消息顺序、分页结果与发送状态均与重构前一致

#### Scenario: 外部 channel shadow conversation 保持幂等
- **WHEN** Gateway 重复同步同一外部会话及其用户消息
- **THEN** shadow conversation 的复用、发送者显示、实时出现与重复抑制行为均与重构前一致

### Requirement: Gateway 注册、状态与 relay 行为保持不变

#### Scenario: Node 注册和状态变化继续实时可见
- **WHEN** Gateway 注册、心跳、断连或因超时被判定离线
- **THEN** owner 在浏览器看到的 Node / Agent 状态、错误信息和状态变化时机与重构前一致

#### Scenario: relay 投递与回执继续收口
- **WHEN** 用户消息经 IM relay 到 Gateway，并由 Gateway 上报 sent、completed 或 failed 回执
- **THEN** 用户看到的消息投递状态、失败反馈和幂等行为均与重构前一致

#### Scenario: group reply context 与 agent 间投递保持不变
- **WHEN** 群会话中的 agent 回复完成，或 agent 向既有目标发送消息
- **THEN** 应收到事件的参与者、目标会话、消息可见性和重复抑制均与重构前一致

### Requirement: 过程事件与重启恢复保持不变

#### Scenario: 工具、思考、权限与终态事件实时展示并可回放
- **WHEN** 一个 agent run 产生文本、思考、工具调用、权限请求、用量与终态事件
- **THEN** 浏览器实时展示及刷新后的历史结果均与重构前一致，不丢失、不重复、不改变顺序或终态

#### Scenario: 使用既有数据库重启 IM
- **GIVEN** IM 已持久化用户、会话、消息、Agent、Node、relay 与事件数据
- **WHEN** 运维者停止并重新启动 IM 后重新进入 Web IM，Gateway 重新连接
- **THEN** 既有数据、owner 隔离、历史回放和后续收发能力均与重构前一致，且不要求用户执行额外迁移动作

## 影响范围

- **包含**：IM 包内目前越过 persistence seam 的会话、消息、事件、Node / Agent、relay 辅助查询与事务路径；
  与这些路径直接相关的 repository interface 和回归测试。
- **包含**：为了让 persistence interface 成为 test surface，对现有 IM 测试组织做必要迁移，删除依赖调用方私有
  connection 的浅测试，补充通过公开业务入口和 persistence interface 的行为验证。
- **不包含**：任何 Web IM 页面或交互改版、HTTP / WebSocket 契约变化、数据库产品替换、跨包共享 persistence、
  Gateway / agent 内核改造。
- **不包含**：借机修复 owner 可见性、relay、事件回放或其他已知/新发现的行为缺陷；此类问题单独立项。
- **不包含**：仅因 `repositories.py` 文件较大而机械拆文件。文件布局服从 depth 与 locality，不作为目标本身。

## 迁移与回滚策略

- 迁移按现有可观察行为分批收口，每一步先由当前行为测试锁定结果，再把调用方持有的持久化知识移动到目标
  persistence module；迁移期间不同时维护两套业务语义。
- 本 unit 不要求用户数据迁移，不改变现有 SQLite schema 与公开契约。已有数据库可直接由重构后的 IM 使用。
- 任一阶段若出现用户可观察回归，停止后续迁移并回退该阶段代码；整个 unit 可通过 revert 恢复原实现，无需
  回滚数据库或要求用户修复数据。
- 实施中若发现现有产品行为本身错误，保留复现证据并另立 bugfix，不通过改变本 unit 的回归基线来“顺便修复”。
