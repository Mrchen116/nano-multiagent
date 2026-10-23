# gateway/heartbeat-cron.md (delta for feat-645)

## MODIFIED Requirements

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

Heartbeat保留当前主上下文、配置节律、HEARTBEAT任务选择、活跃时段、忙时跳过和无事静默行为。Cron采用原生定时工具，在创建它的主会话中到期执行并沿用上下文，不为每个任务或每次运行建立独立会话。Heartbeat 由对应 Feature 控制；Cron Feature 提供功能指导和完整工具依赖，定时工具与必要执行服务由有效工具及已保存安排保障，不以 Feature 作为额外调用门槛；IM不是调度源。

#### Scenario: 原主对话到期执行
- **GIVEN** 主Agent在single_thread聊天或global主工作会话创建定时任务
- **WHEN** 任务到期
- **THEN** 定时输入进入创建它的同一会话并沿用上下文；结果按该模式的产品发言/路由规则交付，后续可追问。
- **AND** 不把旧隔离上下文的结果再次回灌到主会话。

#### Scenario: 主对话重启后继续定时任务
- **WHEN** 节点恢复一个有待触发任务的主会话
- **THEN** 任务使用该数字人的有效模型、工具、Skill、身份与审批规则执行，不因冷恢复退回默认配置。

#### Scenario: 未启用的Agent两套机制都不跑
- **GIVEN** 某 Agent 的 Heartbeat 与 Cron 均关闭，也未选择调度工具、没有 active 安排或已接收调度工作
- **WHEN** 调度tick或手动运行请求到达
- **THEN** 不创建对应运行，手动运行得到明确不可用结果；重新启用按各自错过时间规则恢复。

#### Scenario: 配置与任务管理即时生效
- **WHEN** 用户通过既有配置入口合法启停主动能力，或主Agent通过原生定时工具创建、查看、更新和删除任务
- **THEN** 管理结果反映实际生效状态，其他Agent任务不受影响；删除停止未来触发，已入队输入不被冒充撤回。

#### Scenario: 过期一次性任务恢复后补发
- **GIVEN** 一次性提醒在节点停止期间到期
- **WHEN** 服务恢复并成功恢复绑定主会话
- **THEN** 按原生行为补发该提醒，不再采用旧的过期跳过策略。

#### Scenario: 周期任务错过多个周期不刷屏回填
- **WHEN** 节点恢复错过多个周期的任务
- **THEN** 每个周期任务仅投递最近一次到期内容，不逐次补齐积压；同一主会话的到期周期任务可按原生方式合批。

#### Scenario: 立即运行与执行历史
- **WHEN** 主Agent请求立即运行已有可用任务或查询其执行历史
- **THEN** 手动运行返回接收结果并使用与到期触发相同的主会话与来源规则；历史区分手动/定时、接收/运行/终态、结果或错误，不以定时入队收据冒充执行成功。
- **AND** 不存在或不可运行任务明确拒绝；一次性已入队任务仍可执行，失败如实记录，不执行另一条任务。

#### Scenario: 定时任务不获得实时人工同意
- **WHEN** 定时输入在主会话中触发执行，或主会话此前正在等待人工确认
- **THEN** 该输入仍是定时来源，不成为新的人类授权或待确认问题的回答；任务内工具照常接受Auto及无人值守规则约束。

#### Scenario: 新会话不静默改绑旧安排
- **WHEN** 用户在single_thread聊天创建新上下文
- **THEN** 已有定时安排仍绑定创建时的会话，不静默迁移到新上下文；任务管理和结果仍有明确的原聊天归属。

#### Scenario: Heartbeat有事才在正确上下文冒泡
- **WHEN** 已启用Heartbeat到点且助手空闲、处于活跃时段并有可行动任务
- **THEN** single_thread使用owner canonical直聊上下文，global使用数字人主上下文处理，并按原规则反馈。

#### Scenario: Heartbeat忙碌、窗口外和无事静默
- **WHEN** Heartbeat评估时助手正忙、处于activeHours外或没有可行动任务
- **THEN** 跳过或以HEARTBEAT_OK静默，不生成用户可见噪声；错过多个周期不逐次补跑。

#### Scenario: Heartbeat节律和任务内容来源不变
- **WHEN** 配置声明顶层节律，HEARTBEAT文件声明任务及可选子节律
- **THEN** 按配置顶层节律及activeHours运行，文件负责内容与任务子节律，文件顶层every不覆盖配置。

#### Scenario: 自动工作沿用模型备用策略
- **WHEN** Heartbeat或Cron遇到主模型可用性失败，且尚未产生真实公开输出
- **THEN** 沿用Agent有序备用链、粘性和切换说明；配置变化可重置，整链失败如实说明，不伪装执行成功。

## ADDED Requirements

### Requirement: Cron SHALL 保护生效安排并兑现单工具操作

#### Scenario: Task 或 active 安排阻止关闭 Cron
- **GIVEN** Task Feature 开启，或该 Agent 存在 active 定时安排
- **WHEN** 用户关闭 Cron
- **THEN** 关闭被拒并说明需要先处理的依赖或安排，业务状态不被修改
- **AND** 到期但尚未完成的 active 一次性安排仍受保护，inactive 历史不阻碍关闭

#### Scenario: Feature 关闭时单独创建提醒
- **GIVEN** Cron Feature 关闭且仅 schedule_create 工具被单独启用
- **WHEN** Agent 合法创建提醒并到达触发时间，包含重启恢复后
- **THEN** 该安排实际执行，Feature 保持关闭，不附带提供其他未选工具或 Cron 额外指导；原身份、来源与审批规则保留

#### Scenario: Heartbeat 与 Cron 独立关闭
- **GIVEN** Heartbeat 没有已接受或未确认的工作，Cron 也无开启 Feature 依赖、active 安排或相关在途调用
- **WHEN** 用户分别关闭这两项 Feature
- **THEN** 可分别关闭并按共享依赖规则调整关联工具，保留历史；HEARTBEAT 文件内容和未来 tick 不构成关闭阻碍
