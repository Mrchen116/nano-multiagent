# feat-466: Design 验收前置保障

## Relations

- Related: feat-464

## 原始需求

> .agents/skills/change-design-author/SKILL.md 有没有写reviewer验收条件如果不够，需要跟用户要？比如说，docs/changes/feat-464-im-channel-settings/design.md，需要飞书App ID/Secret，而在当前环境又找不到的话，需要design阶段问用户要，否则review无法进行下去

> 分析下，skill应该怎么改。做个克制的修改，不要改无关的内容

> 很好，这本身也算一个需求，帮我写个spec，然后一同提交

## 澄清记录

- Q1: 这个需求是否只约束 `change-design-author` 及其 design 模板，不同步修改 reviewer/orchestrator？
  A(原话): 够了
  Agent 解读: 按推荐范围收口，只改 design-author 及其模板。

## 用户场景

用户用 `change-design-author` 对齐技术方案时，会把真实用户旅程写成 reviewer 必验退出标准。某些旅程依赖仓库外的账号、凭据、测试租户、第三方对象、权限状态或硬件。如果 design 阶段只写“要真栈验收”，却没有确认这些前置是否可获得，reviewer 到最后才会发现旅程无法进行，只能留下 `inconclusive`。

目标状态是：design-author 在定稿前从 reviewer 旅程反推必要前置，记录可安全使用的来源和可用性检查方式。如果当前环境找不到必验资源，design-author 在 design 阶段向用户索取安全的准备方式，而不是把阻塞留给 reviewer。在前置落实前，用户不会收到“门禁 2 通过”的误导性结论。

凭据本身不是 design 文档的产物。用户应当看到凭据的安全定位或注入方式，而不是 secret 值被复制到 design、Git 或对话记录中。

## 验收标准

### Requirement: Design 阶段提前收口 reviewer 的必验前置

#### Scenario: 真实旅程需要仓库外资源
- **GIVEN** design 中的 reviewer 必验旅程依赖账号、凭据、测试租户、第三方对象、特定权限状态或硬件
- **WHEN** design-author 准备定稿 design
- **THEN** 用户在 reviewer runbook 中看到必要资源、安全来源或注入方式，以及可用性检查方式

#### Scenario: 真实旅程没有仓库外前置
- **GIVEN** design 中的 reviewer 必验旅程不依赖仓库外资源
- **WHEN** design-author 准备定稿 design
- **THEN** 用户在 reviewer runbook 中看到验收前置被明确标记为“无”

### Requirement: 缺失的必验资源在门禁 2 前解决

#### Scenario: 当前环境找不到必验资源
- **GIVEN** reviewer 必验旅程依赖的仓库外资源在当前环境不可获得
- **WHEN** design-author 检查验收前置
- **THEN** design-author 在 design 阶段请用户提供安全的准备方式
- **AND** 在必验前置落实前不宣布门禁 2 通过

#### Scenario: 用户无法提供必验资源
- **GIVEN** 用户无法为 reviewer 必验旅程提供所需的仓库外资源
- **WHEN** design-author 确认验收前置无法落实
- **THEN** 用户被明确告知需要回到 spec 阶段调整验收范围，或明确授权替代验证
- **AND** fake 或单测不会在未经授权时被默认当作真栈验收的替代

### Requirement: 验收前置不泄露凭据

#### Scenario: Runbook 记录凭据的使用方式
- **GIVEN** reviewer 必验旅程需要 secret 或其他敏感凭据
- **WHEN** design-author 把验收前置写入 reviewer runbook
- **THEN** 用户只看到环境变量名、Keychain 项、私密文件路径或其他安全来源
- **AND** design、Git 和对话记录中不出现 secret 值

## 范围与非目标

- 在范围:
  - `change-design-author` 识别、记录并在门禁 2 前收口 reviewer 必验的仓库外前置。
  - design 模板为验收前置提供明确落点。
  - 缺失前置时向用户索取安全的 provision 方式，并阻止门禁 2 误通过。
  - 凭据只记录安全来源或注入方式，不记录 secret 值。
- 非目标:
  - 修改 `change-reviewer` 或 `change-orchestrator` 的现有验收、路由或 `inconclusive` 判定语义。
  - 为第三方平台创建账号、应用、租户或凭据管理系统。
  - 在 design 文档中保存或回显 secret 值。
  - 追溯修改已定稿的 `feat-464` design；它只是本需求的触发案例。
