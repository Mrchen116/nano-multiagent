> Delta baseline: branch canonical at `89c47478b054b8d788022752213ff6d494b5f9d9`; replaces read-only workspace tool cards with plugin management.

## MODIFIED Requirements

### Requirement: Agent 配置页展示 workspace 自动工具的实际可用状态

Agent 设置通过独立“插件”页签管理当前 workspace 的已安装 DSH 插件包，包括没有工具、已停用和加载失败的插件。显示可读名称、描述、版本及真实运行状态，并提供开关、详情和卸载确认。静态工具权限沿用原有控件；自建工具不因保存无关配置加入静态名单。插件页明确作用于共享 workspace，关闭为整体停用且保留安装包，卸载为独立操作；均不重建聊天。

#### Scenario: 安装后查看与保存配置
- **GIVEN** Agent 已在 workspace 自助安装工具并实际可用
- **WHEN** 用户打开配置页并保存无关配置
- **THEN** 插件页显示对应包已启用，静态名单不添加工具名

#### Scenario: 关闭管理能力
- **GIVEN** workspace 插件仍安装但 Agent 管理工具已关闭
- **WHEN** 用户重新打开插件页
- **THEN** 用户仍能查看及管理安装包；页面说明插件运行状态与 Agent 工具调用权限分别控制，不把包启用等同工具可调用

#### Scenario: 不提供工具的插件仍可管理
- **WHEN** 用户打开插件页
- **THEN** 已安装的非工具插件也出现在列表中；可以关闭、重新开启、展开详情或确认卸载

#### Scenario: 开关和卸载即时提交且反馈准确
- **WHEN** 用户点击开关或确认卸载
- **THEN** 无需另存 Agent 表单；忙碌时显示等待，终态按实际运行结果展示，操作失败保留诊断和重试入口
- **AND** 同 workspace 的其他 Agent 共享这一选择，其他 workspace 不受影响；卸载保留源码和用户文件

#### Scenario: 离线、空列表与中断可区分
- **WHEN** 无插件、读取失败或待执行操作期间节点重启
- **THEN** 页面分别显示空状态、无法确认或重新读取的实际状态，未完成操作可重试，不把离线或未知结果当成成功
