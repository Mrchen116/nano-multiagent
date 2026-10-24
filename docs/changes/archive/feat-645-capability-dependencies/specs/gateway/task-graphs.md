# gateway/task-graphs.md (delta for feat-645)

## MODIFIED Requirements

### Requirement: Agent 可按讨论结果维护持久任务图

#### Scenario: 创建、查询和增量修改
- **WHEN** 用户要求已配置任务工具的 Agent 保存或调整讨论好的计划或探索结构
- **THEN** Agent 能建立、读取并修改对应任务图，返回同一图的稳定入口。
- **AND** 保存不按图结构调度执行；分配和结果等协作系统消息遵循既有群接收策略。
- **AND** 节点以图内稳定短编号（如 `n1`、`n2`）读取和更新；改名、排序或状态变化不改变编号，不要求 Agent 反复传递节点 UUID。
- **AND** 图本身也使用短且稳定的引用（如 `tg_a1b2c3d4`）；不同图不会因短 ID 重名而覆盖彼此，工具与 Web 链接使用同一个图 ID。


#### Scenario: 配置任务图特性
- **WHEN** 用户在 Agent 配置中合法开启或关闭默认开启的“任务图”特性并保存
- **THEN** 该 Agent 下一轮回复按最新配置采用任务图能力，当前正在回复的一轮不切换，已有聊天历史和任务图记录保留；关闭有效任务能力后不新增 Task 自动续跑，开启后按当前责任重新检查。
- **AND** 开启 Task 通过界面联动选中 task_graph 和完整 Cron Feature；Task 关闭且工具单独选中时普通任务调用仍可用，自动责任注入、恢复和续跑仍要求 Task Feature，预览采用同一配置。
- **AND** 关闭某个 Agent 的特性不撤销用户按所属会话读取既有任务图的 Web/iOS 访问权，也不改变其他 Agent 或输入渠道的权限。

### Requirement: 图操作使用真实会话与账号归属

资源空间资格是前提，任务访问由固定所属会话决定；私人 Agent 仅访问本人私人空间，公司 Agent 须保持 owner 的公司资格。账号归属核实真实主体，不替代会话权限。加入公司不发布私人会话或其任务。

#### Scenario: 真实身份与公司能力
- **WHEN** 有效成员交办已启用任务工具的真实注册 PA Agent 维护任务
- **THEN** 可跨 owner/Gateway 在所属会话范围内读取同一持久图，写入要求会话成员资格；不接受模型指定身份、未核实内核 child、停用 owner 或过期机器连接。
- **AND** 工具选择及既有身份权限生效，普通任务操作不要求 Task Feature 开启；工具不按任务依赖调度执行；协作系统消息按原群策略处理。

#### Scenario: 外部渠道复用现有主人与 Agent 资格
- **WHEN** 飞书等外部渠道的 Agent 调用任务工具
- **THEN** 复用既有 ownerOpenId 及交办规则；IM 校验 Agent/Gateway 的有效身份、目标空间资格与任务能力，不要求外部发言人另行关联 IM 登录账号。
- **AND** 私人 Agent 不要求公司资格但只能读写自身私人任务；公司 Agent 的管理者未加入公司、待批准或停用时无权读写公司任务；ownerOpenId 不替代这些检查，也不自动转换成外部发言人的 IM user_id。
- **AND** 飞书私聊/群的正常沟通、背景与回复去向保持，无全群核验、关联页面或仅发链接限制。

#### Scenario: IM 不可达时任务调用如实失败
- **WHEN** 飞书 Agent 正常对话期间无法连接 IM 任务服务
- **THEN** 普通渠道继续既有本地自治；任务工具明确返回不可用或结果未知，不宣称任务已保存、不创建本地替代图。

#### Scenario: 来源与无来源操作
- **WHEN** Agent 创建或更新节点
- **THEN** 普通绑定会话采用真实聊天，全局会话只记录可核实来源；显式来源未映射时明确失败，不猜测聊天或创建本地影子图。
- **AND** 创建必须解析所属会话，无绑定来源时显式指定已有会话；编辑可不指定讨论来源，但仍需所属会话写入资格，不伪造用户；每次仅更新实际受影响节点的来源和群活动关联，重试保持原记录。

#### Scenario: 返回稳定入口
- **WHEN** Agent 返回任务图及更新结果
- **THEN** 图与节点短 ID 稳定，外部链接指向既有 IM 公开入口；打开后仍验证资源空间资格、所属会话及受保护来源。

## ADDED Requirements

### Requirement: 有 doing 或 waiting 责任 SHALL 阻止关闭 Task

#### Scenario: 按负责人跨会话判断
- **GIVEN** 本 Agent 在任一会话仍负责 doing 或 waiting 节点
- **WHEN** 用户关闭 Task
- **THEN** 关闭被拒，任务、安排与配置保持不变，并提示先暂停或结束这些责任
- **AND** 其他 Agent 的任务、todo/paused/in_review/done/closed 不阻碍本 Agent 关闭

#### Scenario: 没有责任时关闭
- **GIVEN** 本 Agent 没有 doing/waiting 责任，也无其他 Feature 依赖 Task
- **WHEN** 用户关闭 Task
- **THEN** 允许关闭，既有记录与用户访问权限保留，Cron 不自动关闭；后续重新开启只沿既有任务恢复规则处理
