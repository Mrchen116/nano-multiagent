# IM - Agents and Nodes Specification — feat-540 delta

> 落点: `docs/specs/im/agents-nodes.md`
> 投影自: feat-540 spec.md 验收标准 + design.md 决策 1-4

## ADDED Requirements

### Requirement: Agents 列表条目右缘标注归属设备,状态由头像角标表达

Agents 设置首页、agent 详情页与新建页的左侧列表中,每个 agent 条目右缘右对齐显示其归属设备名,与 Account 页显示的设备名一致;agent 的在线/离线状态由条目头像右下角角标表达,条目右缘不出现独立状态圆点。条目的显示名与 Agent ID 两行完整呈现、行高不随设备名增加;设备名仅自身超长时截断,不占用名字两行的宽度。设备离线时设备名照常显示;无归属信息的条目右缘留空,不显示占位符或错误文案。移动端列表同样标注。

#### Scenario: 多设备下逐条标注
- **GIVEN** 当前账号有多台设备且各有若干 agent
- **WHEN** 打开 Agents 设置首页的左侧列表,或打开任一 agent 详情页 / 新建页左侧的同款列表
- **THEN** 每个条目的右缘显示该 agent 归属设备的名字,与 Account 页显示的设备名一致
- **AND** 各条目的设备名右对齐,在所有条目间位置一致

#### Scenario: 设备设置别名时显示别名
- **GIVEN** 某 agent 归属的设备设置了别名
- **WHEN** 查看列表
- **THEN** 该条目右缘显示该别名,与 Account 页该设备的展示一致

#### Scenario: 设备离线仍显示归属
- **GIVEN** 某 agent 归属的设备当前离线
- **WHEN** 查看列表
- **THEN** 该条目右缘仍显示该设备名

#### Scenario: 无归属信息的条目右缘留空
- **GIVEN** 某 agent 没有任何设备归属信息
- **WHEN** 查看列表
- **THEN** 该条目右缘留空,不显示占位符或错误文案

#### Scenario: 移动端同样标注
- **WHEN** 在移动端打开 Agents 列表
- **THEN** 每个条目同样显示归属设备名

#### Scenario: 名字两行与行高不被挤压
- **WHEN** 查看携带设备标注的列表条目
- **THEN** 显示名行与 Agent ID 行完整呈现,设备名仅自身超长时截断,不占用名字两行的宽度
- **AND** 条目行高不随设备名增加

#### Scenario: 状态由头像角标表达
- **WHEN** 查看列表条目
- **THEN** 条目的在线 / 离线状态从头像右下角角标辨认
- **AND** 条目右缘不出现独立的状态圆点

### Requirement: 三处列表条目文字在深色侧栏上清晰可读

Agents 设置首页、agent 详情页与新建页的左侧列表在桌面端深色侧栏上,条目的显示名与 Agent ID 以浅色文字呈现、清晰可读,选中与 hover 底色上保持可读,三处观感一致。

#### Scenario: 深色侧栏文字可读
- **WHEN** 在桌面端查看列表
- **THEN** 未选中条目的显示名与 Agent ID 以浅色文字呈现在深色侧栏上,清晰可读
- **AND** 选中与 hover 底色上文字保持可读
