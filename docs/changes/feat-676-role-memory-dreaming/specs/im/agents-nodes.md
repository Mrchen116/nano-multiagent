# IM agents-nodes Specification (delta for feat-676)

## ADDED Requirements

### Requirement: 记忆是内置能力，客户端只控制自动 Dreaming

#### Scenario: 新建和已有 Agent 的文档记忆模式
- **WHEN** 用户在 Web 或 iOS 创建、配置 Agent
- **THEN** 不提供记忆总开关，文档记忆模式的 Dreaming 默认开启并可单独关闭；关闭不关闭记忆读取、即时更新、更正或明确请求的整理。
- **AND** 保存与实际应用状态沿用已有配置反馈，失败保留草稿，不宣称已经生效。

#### Scenario: 临时旧模式
- **GIVEN** 节点文件选择旧记忆模式
- **WHEN** 用户查看或保存网页配置
- **THEN** 页面不呈现旧机制、模式切换、旧自进化说明或开关；无效的 Dreaming 控件不显示，保存其他设置不改变文件专属配置。

### Requirement: Skill 创建与后台自动自进化分离

#### Scenario: 在任务中保存成熟方法
- **WHEN** Agent 有相应 Skill 与工具权限，需要创建可复用方法
- **THEN** 可以使用 skill-creator 与受控写入能力；现有 Skill 继续可发现和使用。
- **AND** 技能创建开关不启动后台 fork 自进化，用户不被告知普通任务结果已自动发布为 Skill；后台自动复盘保持暂停且不暴露 UI 控制/介绍。
