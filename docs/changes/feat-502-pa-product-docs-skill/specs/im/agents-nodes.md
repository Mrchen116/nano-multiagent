# IM Agent and Node Specification (delta for feat-502)

## ADDED Requirements

### Requirement: PA 产品说明书 skill 可默认启用和关闭

Gateway 当前版本提供产品说明书 skill 时，IM 把它作为普通全局 skill 呈现在 Agent 配置中。新建 Agent 采用 Gateway 声明的默认选择；已有 Agent 的显式 skills 列表保持权威，资源刷新不改写选择。

#### Scenario: 新建 Agent 默认选中产品说明书

- **WHEN** 用户在在线节点下新建 PA Agent 并查看 skill 选择
- **THEN** 产品说明书出现在全局 skill 列表中并默认选中

#### Scenario: 已有显式选择不因升级改变

- **GIVEN** 某 Agent 已保存不含产品说明书的显式 skills 列表
- **WHEN** Gateway 升级、刷新内置资源并重新连接 IM
- **THEN** 该 Agent 原有选择保持不变，产品说明书显示为未选中

#### Scenario: 用户关闭或重新开启产品说明书

- **WHEN** 用户在 Agent 配置中取消或重新选中产品说明书并成功保存
- **THEN** 该 Agent 后续新回复分别不再使用或恢复使用产品说明书
