# feat-619: Issue 模板与标签

## 原始需求

> #174 Issue 模板与标签 考虑下这个issue怎么解决

> 就按这个方案实施，完成验证后提 PR，历史 Issue 先不批量处理。

来源：https://github.com/Mrchen116/nano-multiagent/issues/174

## 澄清记录

用户确认前一轮方案：四个表单、四维标签、清单与幂等同步、仅新建事件补分诊状态、简短规范；完成验证后 PR，不批量处理历史 Issue。没有未决需求。

## 用户场景

贡献者从 Bug、Feature、Design task、Maintenance 四个入口描述问题或目标；不清楚所属区域也能提报。维护者按类型、区域、优先级和状态分诊。通过 CLI/Agent 新建的 Issue 也进入待分诊列表，已有状态不被覆盖。维护者重复同步标签不会删除其他标签或改动历史 Issue 的标签归属。

## 验收标准

### Requirement: 引导提报足够上下文

#### Scenario: 四类网页提报
- WHEN 贡献者进入新建 Issue 页面并选择任一表单
- THEN 看见与用途对应的问题、背景、预期结果和验证信息字段，且必填内容缺失时不能提交。
- AND 影响区域允许“不确定”，相关资料可选；普通贡献者（Read/Triage）的模板选择页没有空白 Issue 入口，维护者保留 GitHub 的 Maintainers only 原生例外。

#### Scenario: 默认分诊标签
- WHEN 提交 Bug、Feature、Design task 或 Maintenance
- THEN 都进入待分诊；Bug、Feature、Maintenance 分别带 bug、feature、tech-debt 主类型，Design task 不预判类型；不默认优先级。

### Requirement: 所有新建入口都能进入分诊

#### Scenario: CLI 创建无状态 Issue
- WHEN CLI/Agent 新建没有状态标签的 Issue
- THEN 自动补待分诊状态，不猜测类型、区域或优先级，不发送提醒评论。

#### Scenario: 保留已指定状态
- WHEN 新建 Issue 已带任意状态标签
- THEN 自动化不再添加其他状态，也不改动原有标签。

### Requirement: 标签可重复维护

#### Scenario: 重复同步
- WHEN 维护者重复同步标签清单
- THEN 清单内标签名称、颜色、说明一致，清单外标签保留，历史 Issue 的标签归属不被批量修改。

## 范围与非目标

范围：Issue Forms、四维标签清单与同步工具、opened 分诊兜底、维护规范与文档入口、隔离真实 GitHub 验证、PR。
非目标：历史 Issue 分类、删除旧标签、自动分类/优先级判断、评论机器人、同步 change unit 生命周期、产品运行时变更、自动合并。
