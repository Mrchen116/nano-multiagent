# Interactive REPL — feat-552 delta

目标：`docs/specs/cli/interactive-repl.md`。依据 spec R1/R5/R6、design D5/D7。

## ADDED Requirements

### Requirement: Auto 减少常规任务误拒并保留人工入口

#### Scenario: 已授权的本地工作
- **WHEN** 用户要求项目范围内修改、测试及 loopback 开发服务
- **THEN** Auto 按实际范围执行，不因笼统的服务规则重复询问。

#### Scenario: 有效拒绝达到阈值
- **WHEN** 根会话连续或累计自动拒绝达到阈值
- **THEN** 后续需审核的动作使用原人工入口；批准本次可恢复 Auto，拒绝不直接执行；确定性低风险工具仍可用。

#### Scenario: 审批故障
- **WHEN** 审批模型无法得出有效结论
- **THEN** 动作未执行，用户看到实际故障原因；故障不当作普通策略拒绝累计。

### Requirement: 权限配置升级具有明确诊断

#### Scenario: 存在旧 workspace Auto 配置
- **WHEN** CLI 启动采用新的 Auto 机制
- **THEN** 告知哪些键未采用及用户配置迁移位置，不静默扩大权限；无需改配置的默认用户可以正常使用。
