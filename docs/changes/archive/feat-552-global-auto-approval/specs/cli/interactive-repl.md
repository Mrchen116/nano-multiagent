# Interactive REPL — feat-552 delta

目标：`docs/specs/cli/interactive-repl.md`。依据 spec R1/R5/R6、design D3/D6/D7。

## ADDED Requirements

### Requirement: Auto 理解多轮确认并保留现有人工入口

#### Scenario: 已授权的常规工作
- **WHEN** 用户要求项目内修改、测试或 loopback 开发服务
- **THEN** 使用更新后的策略判断实际范围，不因旧笼统服务规则反复确认。

#### Scenario: 回答具体提议
- **WHEN** 真人回答 assistant 的明确提议
- **THEN** 审批按 CC 启用分支获得前文和回复，未获真人回应的当前旁白不构成授权。

#### Scenario: 有效拒绝达到阈值
- **WHEN** 当前 session 连续或累计有效自动拒绝达到阈值
- **THEN** 本次动作走现有人工入口；批准按成功处理，拒绝不执行；不新增永久暂停锁或配置切换。

#### Scenario: 审批故障
- **WHEN** 审批模型未给有效结论
- **THEN** 用户看到实际故障原因，沿既有人工路径处理，故障不计入有效拒绝次数。

#### Scenario: 继续使用已有配置
- **WHEN** 用户升级后使用原 global/workspace 配置
- **THEN** 配置根与逐字段覆盖规则不变，不要求迁移或新增必填项；新默认策略和扩展规则键可说明。
