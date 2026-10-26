# IM agents-nodes Specification (delta for bugfix-662)

## MODIFIED Requirements

### Requirement: 真人管理者可以独立启用和停用 Agent

#### Scenario: 从 Agent 入口停用
- **WHEN** 有权管理该 Agent 的真人在 Web 详情或工作视图、或原生 iOS 既有管理入口停用它
- **THEN** 立即提交停用，不需模型回答、二次确认或先保存其他设置；空闲 Agent 同样进入停用
- **AND** 不连带停止其他 Agent，不保存未提交的配置草稿

#### Scenario: Web 列表与详情保持紧凑且停用状态可辨认
- **WHEN** 用户浏览 Web Agent 列表、详情侧栏或详情标题
- **THEN** 列表与侧栏不逐项展示启停按钮，正常已启用状态不额外占行；已停用以名称旁的紧凑标签显示
- **AND** 详情页集中提供「停用 / 启用」操作；停止中、停止未确认或读取失败保留状态反馈及相应说明、重试入口
- **AND** 设备在线与 Agent 是否启用分别表达，不能相互替代

#### Scenario: 非管理者和 Agent 自身
- **WHEN** 非管理者或 Agent 工具尝试改变开关
- **THEN** 操作被拒，不能通过普通消息、任务或节点配置上报解除停用；原有可见性仍适用
