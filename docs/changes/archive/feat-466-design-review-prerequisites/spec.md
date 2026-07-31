# feat-466: Design 验收前置保障

> 状态：Completed。行为由提交 `e3d9182fb` 进入 `main`；本文件随 unit 冻结为历史。

## Relations

- Related: feat-464

## 原始需求

> .agents/skills/change-design-author/SKILL.md 有没有写reviewer验收条件如果不够，需要跟用户要？比如说，docs/changes/feat-464-im-channel-settings/design.md，需要飞书App ID/Secret，而在当前环境又找不到的话，需要design阶段问用户要，否则review无法进行下去

> 分析下，skill应该怎么改。做个克制的修改，不要改无关的内容

> 很好，这本身也算一个需求，帮我写个spec，然后一同提交

> reviewer的skill有没有写要去design中读这个？另外你的skill太强调安全了，不要复制之类的，这些不用强调，本身模型自己就很严格限制自己了，skill再写的话，更限制他工作了。少写点

## 澄清记录

- Q1: 这个需求是否只约束 `change-design-author` 及其 design 模板，不同步修改 reviewer/orchestrator？
  A(原话): 够了
  Agent 解读: 按推荐范围收口，只改 design-author 及其模板。

## 用户场景

用户用 `change-design-author` 对齐技术方案时，会把真实用户旅程写成 reviewer 必验退出标准。某些旅程依赖仓库外的账号、凭据、测试租户、第三方对象、权限状态或硬件。如果 design 阶段只写“要真栈验收”，却没有确认这些前置是否可获得，reviewer 到最后才会发现旅程无法进行，只能留下 `inconclusive`。

目标状态是：design-author 在定稿前从 reviewer 旅程反推必要前置，记录资源来源和可用性检查方式。如果当前环境找不到必验资源，design-author 在 design 阶段向用户索取，而不是把阻塞留给 reviewer。reviewer 走旅程前读取这些前置；未落实时要求回 design 阶段补齐。

## 验收标准

### Requirement: Design 阶段提前收口 reviewer 的必验前置

#### Scenario: 真实旅程需要仓库外资源
- **GIVEN** design 中的 reviewer 必验旅程依赖账号、凭据、测试租户、第三方对象、特定权限状态或硬件
- **WHEN** design-author 准备定稿 design
- **THEN** 用户在 reviewer runbook 中看到必要资源、来源和可用性检查方式

#### Scenario: 真实旅程没有仓库外前置
- **GIVEN** design 中的 reviewer 必验旅程不依赖仓库外资源
- **WHEN** design-author 准备定稿 design
- **THEN** 用户在 reviewer runbook 中看到验收前置被明确标记为“无”

### Requirement: 缺失的必验资源在门禁 2 前解决

#### Scenario: 当前环境找不到必验资源
- **GIVEN** reviewer 必验旅程依赖的仓库外资源在当前环境不可获得
- **WHEN** design-author 检查验收前置
- **THEN** design-author 在 design 阶段请用户提供所需资源
- **AND** 在必验前置落实前不宣布门禁 2 通过

#### Scenario: 用户无法提供必验资源
- **GIVEN** 用户无法为 reviewer 必验旅程提供所需的仓库外资源
- **WHEN** design-author 确认验收前置无法落实
- **THEN** 用户被明确告知需要回到 spec 阶段调整验收范围，或明确授权替代验证
- **AND** fake 或单测不会在未经授权时被默认当作真栈验收的替代

### Requirement: Reviewer 消费 design 中的验收前置

#### Scenario: 验收前置已落实
- **GIVEN** reviewer runbook 列出了必验前置且资源可用
- **WHEN** reviewer 准备走真实用户旅程
- **THEN** reviewer 按 runbook 确认前置后开始验收

#### Scenario: 验收前置缺失或未落实
- **GIVEN** reviewer runbook 没有列出必要前置，或列出的资源不可用
- **WHEN** reviewer 准备走真实用户旅程
- **THEN** orchestrator 收到“回 design 阶段补齐验收前置”的明确回报
- **AND** reviewer 不自行降级验收口径

## 范围与非目标

- 在范围:
  - `change-design-author` 识别、记录并在门禁 2 前收口 reviewer 必验的仓库外前置。
  - design 模板为验收前置提供明确落点。
  - 缺失前置时向用户索取，并阻止门禁 2 误通过。
  - `change-reviewer` 走旅程前读取并确认 design 中的验收前置。
- 非目标:
  - 修改 `change-orchestrator` 的现有路由，或 `change-reviewer` 的验收 / `inconclusive` 判定语义。
  - 为第三方平台创建账号、应用、租户或凭据管理系统。
  - 追溯修改已定稿的 `feat-464` design；它只是本需求的触发案例。
