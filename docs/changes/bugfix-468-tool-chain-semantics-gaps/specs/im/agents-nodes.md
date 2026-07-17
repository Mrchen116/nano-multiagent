# Delta: IM - Agents and Nodes (bugfix-468)

> 对齐: bugfix-468
> 上级: [IM Specification](../../../../../specs/im/spec.md)

## MODIFIED

### Requirement: 设置 detail 页工具勾选态按存储真值渲染

agent 设置 detail 页的工具面板按存储的 `tool_allowlist` 渲染勾选态:存储为空时全部不亮,不再按
capabilities `default_on` 显示为默认全开;用户勾选/取消直接写显式名单,空名单作为合法配置可表达、
可保存、刷新后保持。

#### Scenario: 存储为空全不亮
- **GIVEN** agent 的存储 `tool_allowlist` 为空
- **WHEN** 打开该 agent 的设置 detail 页
- **THEN** 工具面板全部不亮

#### Scenario: 显式清空保存后保持
- **GIVEN** agent 当前启用若干工具
- **WHEN** 用户取消全部勾选、保存、刷新页面
- **THEN** 工具面板保持全部不亮
