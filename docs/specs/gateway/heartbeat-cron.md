# gateway (personal_assistant) - Heartbeat and Cron Specification

> 对齐: feat-552
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

heartbeat 与 cron 两套本地主动机制的 per-agent 开关、调度和错过周期语义契约。

## Requirements

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

Heartbeat保留当前主上下文、配置节律、HEARTBEAT任务选择、活跃时段、忙时跳过和无事静默行为。Cron采用原生定时工具，在创建它的主会话中到期执行并沿用上下文，不为每个任务或每次运行建立独立会话。两者各受对应Agent开关控制；IM不是调度源。

#### Scenario: 原主对话到期执行
- **GIVEN** 主Agent在single_thread聊天或global主工作会话创建定时任务
- **WHEN** 任务到期
- **THEN** 定时输入进入创建它的同一会话并沿用上下文；结果按该模式的产品发言/路由规则交付，后续可追问。
- **AND** 不把旧隔离上下文的结果再次回灌到主会话。

#### Scenario: 主对话重启后继续定时任务
- **WHEN** 节点恢复一个有待触发任务的主会话
- **THEN** 任务使用该数字人的有效模型、工具、Skill、身份与审批规则执行，不因冷恢复退回默认配置。

#### Scenario: 未启用的Agent两套机制都不跑
- **GIVEN** 某Agent的Heartbeat与Cron开关均关闭
- **WHEN** 调度tick或手动运行请求到达
- **THEN** 不创建对应运行，手动运行得到明确不可用结果；重新启用按各自错过时间规则恢复。

#### Scenario: 配置与任务管理即时生效
- **WHEN** 用户通过既有配置入口启停主动能力，或主Agent通过原生定时工具创建、查看、更新和删除任务
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

### Requirement: 心跳与 cron 走该 Agent 同一条模型备用链

Heartbeat tick 与 cron 执行使用与人工聊天相同的主模型 + 有序备用链及粘性规则。复用已有 Kernel session（含心跳优先使用的 canonical 直聊）时，第一次 admit 与随后经 `submit_message` 打进内核的 model 都必须是该 session 的 `candidates[0]`（有粘性就是备用）；不得省略、也不得再把保存的主模型当 explicit 打进去。主模型因可用性失败且该 run 尚未投出真实正文或工具时间线时，先投下带模型名的失败提示（若该路径对用户可见），再按备用链改用能用的模型并完成本次 tick/任务。成功切换且向用户发出可见内容时，内容前带与聊天相同的轻量切换说明。没配备用或整链耗尽时，每个失败候选留下带模型名的失败提示，没有伪装成功。

#### Scenario: 心跳在主模型不可用时仍能完成 tick
- **GIVEN** Agent 配备用列表
- **WHEN** 一次心跳 tick 时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该 tick 按备用链改用能用的模型并完成
- **AND** 若这次心跳向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明

#### Scenario: 心跳复用已粘备用的直聊时仍用备用
- **GIVEN** 某 Agent 的 canonical 直聊已粘在备用模型 B
- **WHEN** 下一次心跳 tick 复用该 Kernel session
- **THEN** 该 tick 第一次就用 B，入队显式传入 B，不因传入保存的主模型或省略 model 而被内核拒
- **AND** 不先再撞已经失败的主模型

#### Scenario: 定时任务在主模型不可用时仍能跑完
- **GIVEN** Agent 配备用列表
- **WHEN** 一次 cron 任务执行时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该次执行按备用链改用能用的模型并完成
- **AND** 若这次任务向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明

### Requirement: 自动任务执行保留配置任务与实时人工同意的区别

#### Scenario: Cron及手动运行的来源
- **WHEN** 到期或立即运行启动已保存任务
- **THEN** 主模型与Auto看到真实定时来源和任务说明；与真人同轮到达时各段来源分开，不因共用主会话成为实时人类输入。

#### Scenario: Heartbeat与后台通知
- **WHEN** 周期唤醒、任务完成或失败信息进入会话
- **THEN** 它们不能充当待确认问题的回答；需要人工决定时按既有交互/无人值守分流处理。

#### Scenario: 调度操作与任务内动作分别审核
- **WHEN** Agent创建或更新定时安排，随后执行任务内工具
- **THEN** 审批可取得实际调度参数和指令；任务内动作单独走共享Auto，定时安排本身不授权任意副作用。

#### Scenario: 全局Heartbeat与普通全局运行区分交互
- **WHEN** Heartbeat复用global主会话，且审批无有效结论或达到拒绝阈值
- **THEN** 仍按原无人值守fallback处理：显式allow可执行，默认或显式deny不执行，结果区分配置决定和模型判断。
- **AND** 主会话的人工交互选择不覆盖本次自动来源；普通global wake和global child将未获准原因反馈主Agent，不能仅按session归属混用两类交互。
