# Delta

## docs/specs/im/ios-client.md — ADDED
### Requirement: 原生日常页面优先呈现任务内容与下一步
#### Scenario: 创建与模型服务
- **WHEN** 用户新建助手或维护本人的模型服务
- **THEN** 创建先呈现名称与用途，技术设置按需展开；模型服务有常驻原生入口，保存、验证、失败与恢复遵循 agents-nodes 契约；模型选择使用可辨认的服务与模型名称，底层选择值不改变。
#### Scenario: 工作与任务阅读
- **WHEN** 用户阅读工作结果、任务总览与子任务结构
- **THEN** 先看到运行状态和可读内容，诊断信息按需展开；任务提供紧凑状态定位与结构总览，原有权限、分页含义不变。
#### Scenario: 表单与完整阅读
- **WHEN** 用户使用默认或辅助大字号阅读和编辑
- **THEN** 正文可完整换行，字段保留标签，每页有明确主保存动作，展开内容不修改所在页标题。

## docs/specs/im/personal-agent.md — ADDED
### Requirement: Agent 列表突出本人的 PA 配置入口
#### Scenario: 双端查找
- **WHEN** 已有 PA 的主人打开 Web 或原生 iOS Agent 列表
- **THEN** 本人的 PA 位于可辨认的优先区，沿用普通助手行样式，整行打开现有配置，无额外 Configure 按钮；其他用户 PA 不获得此入口或管理权限；搜索保留原联系人匹配字段，从有草稿的配置页切换时先确认是否放弃。
#### Scenario: 无 PA 或读取失败
- **WHEN** 尚无 PA 或读取暂时失败
- **THEN** 普通 Agent 列表保持可用，失败可重试且不当作未创建。

## docs/specs/im/ios-client.md — ADDED（用户追加）
### Requirement: 消息身份与时间不占用正文气泡
#### Scenario: 手机会话阅读
- **WHEN** 用户阅读单聊或群聊
- **THEN** 单聊省略重复对方名称，群聊和只读 Agent 协作的对方名称在气泡上方；时间作为首条、间隔5分钟或跨日的独立分隔；正常完成状态不重复显示，进行中和失败反馈保持可见。
