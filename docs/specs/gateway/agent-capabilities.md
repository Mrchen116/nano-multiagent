# gateway (personal_assistant) - Agent Capabilities Specification

> 对齐: feat-805
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

网页模型接入与真实验证、agent 模型选择、工具白名单、Skill 选择与发现、上下文窗口和内置 skills 自举的 Gateway 契约。自动审批策略与审核证据见[工具审批](tool-approval.md)。

## Requirements

### Requirement: 可选的宿主浏览器与桌面控制

#### Scenario: 按需选择
- **WHEN** 用户关闭宿主操作工具（`computer_use`）
- **THEN** 普通会话与新委派不获得该入口；启用时仅向主会话与显式携带原话引用绑定的外部 CLI Worker 激活公开简短工具入口，按需发现动作与输入（后续 `send` 续跑仅在重新传入原话引用时挂载该工具），并在需要交互网页、复用日常登录态或操作原生窗口的任务中主动使用。

#### Scenario: 两种浏览器身份
- **WHEN** 任务在日常 Chrome 中浏览或明确选择隔离环境（`isolated`）
- **THEN** 日常轨使用节点本机已配对的 Chrome Profile，每个任务独占后台标签页并在后台完成观察、输入与点击，不抢占用户前台窗口焦点；连接或配对不可用时说明原因与恢复入口，且明确要求隔离环境的任务不会回退到日常身份。隔离轨使用独立临时环境。截图同时返回工作区私有图片路径以便按既有发送规则回传聊天；任务结束或关闭最后一页后释放其资源并保留用户日常浏览器。

#### Scenario: 目标窗口失效与同名多窗口消歧
- **WHEN** 任务操作原生桌面窗口，且同应用存在多个窗口但未明确目标，或运行中目标窗口失效、焦点冲突或系统权限不足
- **THEN** 返回明确原因并停止向该目标输入，不自动抢占前台焦点；用户或任务确认唯一目标窗口后可继续。

#### Scenario: 复制和粘贴
- **WHEN** 已认证的节点主人在当前交办中明确请求读取刚复制的内容
- **THEN** 主会话或承接该交办的单一绑定外部 CLI Worker 可直接读取一次系统剪贴板，消费后并发调用、重试、协作者或网页正文均不能再次读取系统剪贴板；普通浏览器复制粘贴仅使用当前任务自己的内存剪贴板。

### Requirement: 携程问道 Skill 随安装版本仅向 PA 默认提供

#### Scenario: 默认配置的 PA 使用旅行查询指导
- **WHEN** PA 使用默认 Skill 发现配置
- **THEN** 可发现并按需加载随包携程问道 Skill，无需另行安装，能力配置默认标记为开启
- **AND** 显式 Skill 选择及实际工具权限继续生效

#### Scenario: 其他 Agent 不默认启用
- **WHEN** Agent 没有 PA 身份，包括其他 Global Agent
- **THEN** 不默认装配本次随包携程 Skill，用户已有自建 Skill 配置保持

#### Scenario: 沿用原版凭证配置
- **WHEN** 用户按携程问道 Skill 发起查询
- **THEN** 凭证配置和缺少凭证时的提示遵循随包原版说明，不提供共享的内置凭证或新增授权界面

### Requirement: 直接真人输入保留原生执行语义与可信来源

直接真人请求保留宿主确认的身份与入口，在原生执行中作为真人输入处理。来源资格只决定哪些机制可使用该输入，具体目标、操作范围和安全审批仍遵循用户意图及既有规则。历史真人记录继续可读，升级不改写已有记录。

#### Scenario: 先执行工具再创建目标
- **GIVEN** 真人已提出需要持续执行的目标
- **WHEN** Agent 在同一轮先读取资料或调用其他工具，再建立目标
- **THEN** 该轮仍保留直接真人来源资格，不因已经执行过工具而被错误拒绝
- **AND** 该资格不构成对无关目标或副作用的同意

#### Scenario: 新真人输入重置重复调用提醒
- **WHEN** 连续重复工具调用之间出现新的直接真人输入
- **THEN** 新输入后的重复计数重新开始，不把新要求前后的调用合成同一段循环

#### Scenario: 系统和委派来源不成为真人同意
- **WHEN** 输入来自系统提醒、定时任务、其他 Agent 或子 Agent 的父任务
- **THEN** 不获得直接真人资格，子 Agent 审批仍返回父 Agent，不向真人弹出子任务审批
- **AND** 真人请求在审批、Workflow、任务关联和工作历史中保留其真实来源；已有历史真人来源继续识别
- **AND** Inbox 的系统唤醒继续保留系统来源，已有 Inbox 来源规则不变

#### Scenario: 原生与兼容 Skill 入口只加载一次
- **WHEN** 真人使用 `/name`、兼容的 `/skill:name` 或标签前缀入口显式调用已启用的 Skill
- **THEN** 同一输入提及同一 Skill 的原生与兼容语法时只加载一次，普通 `/name` 使用原生识别
- **AND** 未启用的 Skill 不因显式调用而重新获得访问权，重启或重复提交已消费输入不重复加载


### Requirement: 写盘失败后由下一次正常激活恢复执行

#### Scenario: 磁盘空间恢复后处理新一轮
- **GIVEN** Agent 因本地记录写入失败暂时无法正常执行，之后本地存储恢复可写
- **WHEN** 用户发送触发 Agent 的新消息，或符合既有调度条件的 Heartbeat 到期
- **THEN** Agent 在同一运行进程内正常处理本轮，先前未落盘的记录可继续写入
- **AND** 空闲期间不发起专门的磁盘恢复检查或补跑失败的轮次。Inbox 待读和 Heartbeat 调度沿用原有规则。

### Requirement: 主模型因可用性失败时按有序备用链换模型，本轮继续回复

两种模式均保持下述候选链、可重试条件、持久 Session 粘性与配置重置规则。以下按聊天隔离、失败气泡、切换说明自动出站和 `/new` 重置的 Scenario 适用于 `single_thread`；global 的粘性归主 Session，改模型配置可重置，失败/切换记录归工作轮次，正式聊天仍显式发言，`/new` 不改变其状态。

Gateway 在每次新回复开始时先组链：有该 Kernel session 的备用粘性则第一次就用粘性模型，否则以 Agent 保存的 `default_model`（空则产品默认）为链头，再加上有序 `model_fallbacks`。本轮候选因欠费/额度、过载/5xx、超时、限流或认证失败而无法完成时，用户先看到带该模型名的失败提示；若该 run 没有产出非失败气泡的真实正文或工具时间线，Gateway 按列表顺序改用下一个候选并继续本轮，用户不必再发消息。明确不可重试的错误（如无效密钥 / 401）很快投下该提示，不对同一模型空转；网络抖动与限流才按既有预算同模型重试。上下文太长不换模型。没配备用或整条链耗尽时，模型连接恢复等待场景中的故障保留当前任务等待恢复；其余失败候选留下带模型名的失败提示，不改用其它 Agent 的模型，也不把未配置的平台默认塞进备用链。自动切换不写回保存的 `default_model`。切到备用时使用该备用模型自己的默认推理档，不沿用主模型保存的强度，也不沿用会话 `/effort`。

同一 Kernel session 在成功改用备用后粘在该备用上，直到该聊天 `/new` 或用户保存该 Agent 的主模型/备用列表。另一聊天各自从链头试起。首次因切换而成功回复时，先投递一句轻量说明「已改用 {model}，因为主模型不可用。」再投递该备用模型的普通助手正文；粘住后不再每条重复。说明走与压缩控制确认相同的出站形态，正文不进这条控制消息。Web IM 上该正文带 token 用量。

#### Scenario: 欠费或服务不可用时本轮仍收到回复
- **GIVEN** Agent 保存了有序备用列表，且当前聊天尚未因失败粘在备用上
- **WHEN** 用户发一条消息，主模型因欠费、额度、服务挂了或过载、超时、限流或认证失败而无法完成本轮，且尚未投出真实正文或工具时间线
- **THEN** 用户先看到带该主模型名的失败提示
- **AND** 若失败是无效密钥等明确不可重试的原因，该提示很快出现，不对同一模型空转
- **AND** 不必再发消息，本轮按备用列表顺序改用下一个能用的模型，并收到该备用模型的普通助手回复
- **AND** Web IM 上该回复带 token 用量；「已改用」是独立短说明，不是把正文写进说明里

#### Scenario: 上下文太长不换模型
- **GIVEN** Agent 配备用列表
- **WHEN** 本轮失败原因是上下文太长
- **THEN** 不改用备用模型，仍走今天的压缩或失败呈现

#### Scenario: 没配备用时失败呈现与现在一样
- **GIVEN** Agent 没有备用列表
- **WHEN** 主模型本轮失败
- **THEN** 失败呈现与变更前一致，不改用节点平台默认模型顶上，也不借用其他 Agent 的模型

#### Scenario: 整条备用链都失败时按现状失败呈现
- **GIVEN** Agent 配备用列表，且主模型与全部备用都因可用性失败
- **WHEN** 用户发一条消息
- **THEN** 每个失败的候选都留下带该模型名的失败提示
- **AND** 用户收不到伪装成功的回复

#### Scenario: 已有真实回复后再失败则本轮不换
- **GIVEN** 本轮已经向该聊天投出过非失败气泡的 assistant 正文或工具时间线
- **WHEN** 当前候选随后因可用性失败
- **THEN** 本轮按现状失败收口，不删除已可见内容再开新气泡

#### Scenario: 首次切换有轻量说明，粘住后不再每条提示
- **WHEN** 某聊天本轮因主模型不可用改用了备用模型并成功回复
- **THEN** 用户先看到轻量说明：已改用该备用模型，因为主模型不可用
- **AND** 同一轮随后出现备用模型的普通助手正文；Web IM 上该正文带 token 用量
- **AND** 不出现必须确认的弹窗或按钮
- **WHEN** 用户再发下一条普通消息且本轮没有再次换到另一个模型
- **THEN** 回复正常给出，不再重复那句切换说明

#### Scenario: 粘在当前聊天，不改写保存的主模型
- **GIVEN** 某聊天本轮已改用备用模型 B
- **WHEN** 用户在同一聊天接着发消息，且没有 `/new`、也没有改该 Agent 的主模型或备用列表
- **THEN** 新回复继续使用 B
- **AND** Agent 保存的 `default_model` 仍是原来的主模型

#### Scenario: `/new` 或改模型配置后重新从主模型试起
- **GIVEN** 某聊天已粘在备用模型上
- **WHEN** 用户发送 `/new`，或保存对该 Agent 主模型或备用列表的修改
- **THEN** 之后的普通消息重新从保存的主模型试起

#### Scenario: 另一个聊天互不影响
- **GIVEN** 同一 Agent 的聊天甲已粘在备用模型上
- **WHEN** 用户在该 Agent 的另一个尚未切换过的聊天乙发消息
- **THEN** 聊天乙仍先使用保存的主模型

### Requirement: Agent 选定的模型在每次新回复开始时生效

Gateway 在每次新回复开始时先组链再 admit：有该 Kernel session 的备用粘性则第一次就用粘性模型，不再先撞保存的主模型；否则按 Agent 当前 `default_model` 选择链头，未选模型时回退产品层全局默认。没有备用列表、也没有该 Kernel session 的备用粘性时，这个链头就是本轮模型，行为与变更前相同。有效模型声明可调推理能力时，对链头先使用 Agent 已保存的 `reasoning_effort` 或该模型推荐 default；若会话已有仍为该模型合法的 `/effort` override，则后者覆盖 baseline，不回写 Agent 配置。模型切换后不合法的 override 被清除而不近似替换；取消 Workflow 只关闭 ultracode mode，仍保留合法普通 override。`default_model` 为空时也可以保存属于平台默认模型的 `reasoning_effort`，且不因此把 Agent 固定到该模型。既有聊天改模型或推理强度不创建空会话，模型与同代 prompt、skills、tools、features 一起生效并保留历史。已经开始的整轮及其采纳的插话继续使用启动时的完整配置。保存主模型或备用列表会使该 Agent 各聊天的备用粘性失效，下一轮新回复从刚保存的链头试起。

#### Scenario: Agent 选定模型和推理强度后对话使用这一组配置
- **GIVEN** 某 Agent 配置模型 B 和 B 支持的推理强度 H
- **WHEN** 用户与该 Agent 开始一轮新交流
- **THEN** 该轮使用 B 和 H

#### Scenario: 改模型或推理强度后旧会话继续聊且保留历史
- **GIVEN** 某 Agent 曾用模型 A 和强度 X 形成历史会话
- **WHEN** 配置改为模型 B、强度 Y 后回到该历史会话发新消息
- **THEN** 新回复使用 B 和 Y，并仍能引用此前聊天历史

#### Scenario: 正在进行的回复不在中途换运行配置
- **GIVEN** Agent 正在用模型 A 和强度 X 回复
- **WHEN** 配置改为模型 B 或强度 Y，且用户插话被纳入当前回复
- **THEN** 当前整轮仍使用 A 和 X，下一轮新回复才使用成功保存的完整配置

#### Scenario: Agent 未选模型时可覆盖产品层默认模型的推理强度
- **GIVEN** Agent 的 `default_model` 为空
- **WHEN** 用户保存该产品默认模型支持的推理强度 H 后开始一轮新交流
- **THEN** 使用 Gateway 产品默认模型和 H 正常回复
- **AND**  Agent 的 `default_model` 仍为空，不持久化该模型名

#### Scenario: heartbeat 复用专用会话时采用当前完整配置
- **GIVEN** heartbeat 专用会话已用配置 A 形成历史
- **WHEN** Agent 更新为配置 B 后开始下一 heartbeat tick
- **THEN** tick 使用 B 的 model、prompt、skills、tools 与 features，并保留该专用会话历史

#### Scenario: cron 新会话使用 Agent 当前完整配置
- **WHEN** cron 为某 Agent 创建会话并开始执行
- **THEN** 新会话使用创建时该 Agent 当前的完整配置；未选模型时使用产品默认兜底

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。公开 Agent profile 提供的提示词文本仅为可见的 Custom Instructions：它作为产品规则后的 `PromptSlots` 追加段出现，不能覆盖公共 PA 提示词，也不走 Kernel 内部完整 override。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。可调用工具的取消选择先立即收缩，后续 dispatch 不再允许该工具，但不中断已开始的调用；新增工具等待当前执行空闲后的完整配置应用。收缩从当前有效选择计算，未配置白名单时默认未选的工具不会因候选名单包含而提前启用。

本次取消选择若会撤销仍被开启 Feature、有效业务责任或正在执行的工具调用需要的能力，保存先被拒绝；只有通过依赖与占用校验的变更才进入上述生效流程。普通运行中不因此阻止无关配置更新。

#### Scenario: 增加工具后继续既有聊天
- **GIVEN** Agent 因未配置某工具而无法完成既有聊天中的任务
- **WHEN** 用户增加该工具后在同一聊天继续
- **THEN** 新回复可使用该工具并理解此前的问题与回复

#### Scenario: 删除工具后保留既成工具历史
- **GIVEN** 既有聊天历史中已有某工具调用及结果
- **WHEN** 用户删除该工具后继续聊天
- **THEN** 新回复不能再执行该工具，但能理解历史调用与结果

#### Scenario: 修改 Custom Instructions、skills 或 features 后继续历史
- **GIVEN** 某聊天已形成历史
- **WHEN** 用户修改会影响后续模型请求的 Custom Instructions、skills 或 features 后发起新交流
- **THEN** 新回复体现完整的新运行配置，并仍能引用修改前历史

#### Scenario: 连续保存多次只采用最终运行配置
- **GIVEN** 某聊天空闲或消息仍在等待处理
- **WHEN** 用户连续成功保存多份 Agent 运行配置
- **THEN** 下一轮新回复使用真正开始时最新的完整配置，不依次重演中间版本

#### Scenario: 配置替换失败不使用混合配置回复
- **WHEN** Gateway 无法把最新完整运行配置持久应用到既有会话
- **THEN** 当前消息以真实失败结束，不以新 model 搭配旧 prompt 或 tools 的混合配置运行

### Requirement: 每模型推理能力由 Gateway 配置声明并安全上报

运维者可在 Gateway config 的 `llm.providers[].models[]` 条目配置 `reasoning: fixed`，或配置含 `default` 与 `levels` 的可调能力。Gateway 只向 IM 上报可调档位、推荐 default 或 fixed 状态；不上传静态请求 body。错误的 reasoning 配置使 Gateway 在启动期拒绝运行。

#### Scenario: 配置新增或调整模型档位后 IM 无需发布即可使用
- **GIVEN** 运维者更新某节点模型的 reasoning 配置并重启 Gateway
- **WHEN** Gateway 上线且 IM 查询该节点能力
- **THEN** IM 看到该节点当前声明的可选档位、推荐项或 fixed 状态
- **AND** 其他节点仍只上报自己的配置

#### Scenario: fixed 模型不接受独立推理强度
- **GIVEN** 某模型配置为 `reasoning: fixed`
- **WHEN** Gateway 收到该模型搭配非空 `reasoning_effort` 的 Agent 配置
- **THEN** Gateway 拒绝该配置而不写入本地配置

#### Scenario: 配置或已保存档位不再合法时不静默替换
- **GIVEN** Agent 的已保存推理强度不再位于其模型当前的 levels 中
- **WHEN** Gateway 要同步该配置或开始下一轮新回复
- **THEN** Gateway 明确拒绝该不兼容配置或运行，不将用户选择静默替换为另一档

### Requirement: Gateway 配置 operation 可幂等恢复

Gateway 对 `agent.create` 与 `agent.config.apply` 接收稳定 operation id 与唯一当前 canonical 候选 fingerprint；该 fingerprint 包含有效的 Skill selection mode。在任何 workspace、local config 或 live publication 变更前，Gateway 先持久化不含 secret 的 `prepared` intent；再以 expected-previous 保护 local config 写入，并将结果变为 terminal applied/rejected receipt。IM 可在 ACK 丢失或重连后查询 `agent.config.operation.status`。同一个 operation 与同一候选 fingerprint 可安全重试，operation id 不得重用到不同候选。IM 与 Gateway 随该变更一起更新，不协商 fingerprint schema，也不支持旧 protocol fallback 或旧 receipt 迁移。

#### Scenario: applied operation 重试不重复写入或发布
- **GIVEN** Gateway 已为某 operation id 持久化同一候选 fingerprint 的 applied receipt
- **WHEN** IM 因超时再次发送相同 create 或 apply operation
- **THEN** Gateway 返回同一 canonical applied result，不第二次创建 workspace 或重复发布该配置

#### Scenario: operation status 使丢失 ACK 可恢复
- **GIVEN** Gateway 已落盘某 operation 的 applied 或 rejected receipt，但结果 frame 未送达 IM
- **WHEN** IM 查询该 operation id 的 status
- **THEN** Gateway 返回已持久化的终态和 canonical payload 或 rejected reason

#### Scenario: Gateway 在任意 config operation 持久边界崩溃后能恢复
- **GIVEN** Gateway 已持久化一个 prepared intent
- **WHEN** 它在 workspace 初始化前、workspace 初始化后、local config 写入后或 live publication 后但 terminal receipt 前崩溃
- **THEN** 同一 operation 的 retry 或 status 以相同的 expected-previous/candidate fingerprint 重新协调该 intent
- **AND** create 不创建第二个 workspace，apply 不第二次持久写入或发布

#### Scenario: operation id 不得重用到不同候选
- **GIVEN** Gateway 已见过某 operation id
- **WHEN** 调用方以不同候选 fingerprint 重试该 operation id
- **THEN** Gateway 稳定拒绝，不改变本地 Agent 配置或既有 receipt

### Requirement: 动态新建 agent 的模型选择持久化

#### Scenario: IM 动态新建 agent 选模型后重启保留
- **GIVEN** 用户在 IM 新建 agent 并选模型 B
- **WHEN** Gateway 重启
- **THEN** 该 agent 仍在、其模型仍是 B,继续用 B 对话

### Requirement: PA 产品说明书按需回答产品问题

PA 随当前安装版本提供可选的产品说明书 skill，覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、外部渠道、启动和常见故障处理。入口经 `skill` 按需加载，再由默认启用的 `read` 只读取当前问题所需的随包专题资料；普通任务不因其启用而加载。用户显式关闭 `read` 后，产品不保证详细手册可读。退役 Coding CLI、DSH 内部和开发流程不属于该手册。

#### Scenario: 在 PA 对话入口询问产品问题

- **GIVEN** 当前 Agent 已启用产品说明书、`skill` 与 `read`
- **WHEN** 用户从 Web IM、飞书或其他 PA 对话入口询问 PA 能力、使用、配置或故障处理
- **THEN** Agent 按需读取产品说明书，并基于当前安装版本直接回答

#### Scenario: 普通任务不加载产品说明书

- **WHEN** 用户提出与 PA 产品自身无关的普通任务
- **THEN** Agent 不因为产品说明书处于启用状态而读取它

#### Scenario: 基础问答离线可用

- **WHEN** 用户询问当前安装版本的 PA 产品能力或使用方法
- **THEN** Agent 可只依据随包手册回答，不要求远端文档服务

#### Scenario: 最新版与本机版本分开回答

- **WHEN** 用户明确询问最新版、升级变化或远端当前行为
- **THEN** Agent 区分查到的官方远端信息与本机安装版本，不把远端行为表述为本机已经具备
- **AND** 远端信息不可用时明确限定为本机手册事实

#### Scenario: 现场状态以实际核实为准

- **WHEN** 用户询问自己的 Agent、节点、渠道或任务当前状态
- **THEN** Agent 在能力允许时核实现场后回答，并区分产品规则与观察结果
- **AND** 无法核实或手册未覆盖时明确不确定，不编造能力、配置或处理步骤

### Requirement: PA 内置 skill 启动自举

Gateway 随包提供 PA 产品说明书与当前产品定义的完整 Lark skill bundle。启动时，Gateway 以当前安装包完整刷新运行态全局 skill root 中所有随包内置名称的目录；这些名称是 PA 托管资源，本地修改和旧版本额外文件不保留。名称不属于当前随包内置集合的用户 skill 不受影响。资源刷新不改变 Agent 的 skills 选择。绑定 Feishu channel 的 Agent 按其 selection mode 发现可用的 Lark bundle，并默认沿用 Gateway 所在机器已登录的 Lark 用户身份；只有各 skill 的既有规则明确要求时才使用其他身份。Agent 的 `skills_selection_mode` 是判断是否物化 allowlist 的权威；历史缺席 mode 时仅在读取时按“非空 names 为 explicit、空 names 为 default”兼容。

#### Scenario: 内置 Computer Use Skill

- **WHEN** Agent 使用默认 Skill 发现配置，或其显式配置允许 `cua-driver`
- **THEN** Agent 可发现并加载随包的官方 CuaDriver Skill 及其操作手册
- **AND** 已启用宿主电脑操作的任务优先使用共享入口；独立 CLI 可用且 Agent 已启用 Bash 时，独立操作继续遵守原有 Shell 审核。

#### Scenario: 新安装发现产品说明书与完整 Lark bundle

- **WHEN** Gateway 使用一个没有 PA 内置 skill 的全局 root 启动
- **THEN** Agent capabilities 和会话可发现产品说明书与完整 Lark skill bundle

#### Scenario: 升级刷新全部随包内置 skills

- **GIVEN** 全局 root 中已有旧版或本地改写的 PA 内置 skill 目录
- **WHEN** 新版本 Gateway 启动
- **THEN** 当前包仍声明的每个内置名称都呈现包内完整内容，旧版额外文件不残留

#### Scenario: 非内置用户 skill 保持不变

- **GIVEN** 全局 root 中存在名称不属于 PA 随包内置集合的用户 skill
- **WHEN** Gateway 刷新内置 skills
- **THEN** 该用户 skill 的目录和内容保持不变

#### Scenario: 刷新失败保留旧完整目录并继续启动

- **GIVEN** 某个内置 skill 在 staging 或切换时失败，且目标已有旧完整目录
- **WHEN** Gateway 执行启动刷新
- **THEN** 该名称恢复旧完整目录、其他名称继续刷新，Gateway 继续启动并暴露失败原因

#### Scenario: backup 清理失败不遮蔽已切换的新版本

- **GIVEN** 某个内置 skill 已成功切换到当前包版本，但旧 backup 的清理失败
- **WHEN** Agent 发现或读取该名称的 skill
- **THEN** Agent 仍只发现 canonical 新版本，旧 backup 不参与 skill discovery
- **AND** Gateway 暴露 cleanup 失败原因并可继续启动

#### Scenario: 共享全局 root 的并发 Gateway 刷新保持完整版本

- **GIVEN** 两个使用不同 config 的 Gateway 共享同一个用户全局 skill root
- **WHEN** 两个 Gateway 并发刷新随包内置 skills
- **THEN** 两次完整 bundle 刷新按顺序执行，不逐 skill 交错
- **AND** 先成功的刷新不被另一失败刷新回滚，Agent 不会发现混合版本 bundle

#### Scenario: 显式 skill allowlist 不因资源刷新改变

- **GIVEN** 某 Agent 已保存 `explicit_allowlist` 并关闭部分内置 skills
- **WHEN** Gateway 刷新资源、连接或重连 IM
- **THEN** 该 Agent 的启用和关闭选择保持不变

#### Scenario: 显式非空 allowlist 的飞书 Agent 获得完整 bundle

- **GIVEN** 飞书绑定 Agent 的 mode 为 `explicit_allowlist`，且本地 skills names 非空并缺少一个或多个 Lark skill
- **WHEN** Gateway 启动静态 `config.channels` 中的该飞书 channel，或调和 IM 托管的该飞书 channel
- **THEN** Gateway 保留已有条目与 `explicit_allowlist` mode，并将完整 Lark skill bundle 加入 allowlist
- **AND** 重复调和不会重复写入或重复列出 bundle skill

#### Scenario: 默认发现的飞书 Agent 不物化 bundle

- **GIVEN** 飞书绑定 Agent 的有效 mode 为 `default_discovery`
- **WHEN** Gateway 启动或调和该飞书 channel
- **THEN** Gateway 不将完整 bundle 物化写入该 allowlist
- **AND** 该 Agent 仍按默认全局 skill discovery 发现内置 skills

#### Scenario: 显式空 allowlist 不因飞书 channel 调和扩宽

- **GIVEN** 飞书绑定 Agent 的 mode 为 `explicit_allowlist`，且 skills names 为空
- **WHEN** Gateway 启动或调和该飞书 channel
- **THEN** Gateway 保留显式空选择，不自动加入 Lark bundle
- **AND** 该 Agent 的下一轮不因 channel 调和重新获得 Skill

#### Scenario: 静态 Feishu Agent 的 IM profile ingress 保留完整 bundle

- **GIVEN** Gateway 的静态 `config.channels` 绑定了一个 `explicit_allowlist` names 非空的 Feishu Agent
- **AND** IM 中该 Agent 已存在一个尚未包含完整 Lark skill bundle 的 mirror profile
- **WHEN** Gateway 连接、重连 IM，或接收该 Agent 的 `config.sync` profile 更新
- **THEN** Gateway 将完整 Lark skill bundle 补齐到该 Agent 的显式 profile 后再应用到本地运行态
- **AND** 该 Agent 后续会话仍可发现完整 Lark skill bundle，mode 仍为 `explicit_allowlist`

#### Scenario: 用户明确请求独立 Lark 事件监听

- **WHEN** 用户要求飞书绑定 Agent 监听并处理一种 Lark 事件
- **THEN** Agent 可使用内置 Lark event skill 建立独立监听
- **AND** 普通 Gateway Feishu 对话的入站与回复所有权不转交给该独立监听

### Requirement: PA Agent 从有序的工作区与用户级兼容根发现 Skill

PA 为某 Agent 解析可选 Skill、prompt preview、下一轮新回复和 `skill` 时，按该 Agent 的真实 Workspace 依次搜索 `<workspace>/.nanoassistant/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`，再依次搜索 `~/.nanoassistant/skills/`、`~/.agents/skills/`、`~/.claude/skills/`、`~/.codex/skills/`。`~/.agents/skills/` 是用户级兼容来源，不新增 `<workspace>/.agents/skills/`。同名 Skill 只采用最先命中的版本；缺失或空的可选兼容目录不影响其他来源。

#### Scenario: 工作区 Claude/Codex Skill 出现在 Agent capability 中
- **GIVEN** 某 Agent 的真实 Workspace 下 `.claude/skills/` 或 `.codex/skills/` 含有效 Skill
- **WHEN** IM 通过在线 Gateway 解析该 Agent 的 capabilities
- **THEN** 该 Skill 成为候选并携带实际命中的 location
- **AND** 同名的较低优先级副本不作为第二个候选返回

#### Scenario: PA 新回复与 capability 使用同一同名覆盖结果
- **GIVEN** 同名 Skill 同时存在于 PA 的多个受支持工作区或全局 roots，且用户在 Agent 配置中选择该 name
- **WHEN** 用户保存配置后在既有聊天开始下一轮新回复
- **THEN** 该轮使用与 capability 中同一优先级、同一 location 的 Skill 内容

#### Scenario: 缺失兼容目录不阻断 PA Agent
- **GIVEN** Agent Workspace 未创建 `.claude/skills/` 或 `.codex/skills/`，或用户主目录未创建 `.claude/skills/`
- **WHEN** Gateway 解析 capabilities、开始新回复或处理 `skill`
- **THEN** 操作正常完成
- **AND** 其他有效 roots 中的 Skill 仍可使用

#### Scenario: 新建页只取得全局 Skill candidates
- **GIVEN** IM 正在为尚无 canonical Workspace 的新 Agent 查询 node capabilities，且 Gateway repo root 中存在工作区 Skill
- **WHEN** Gateway 返回该 node 的创建页 Skill candidates
- **THEN** 返回的候选只来自 PA 的共享全局 roots
- **AND** repo root 或其他未绑定 Workspace 中的 Skill 不作为新 Agent 可选择项

### Requirement: 历史自进化创建的 Skill 在前台轮次结束前后均按原结果调和

历史已成功的知识更新事实保持 session 级消费，重放不重复调和、不修改禁用选择。后台 Skill 自进化及 combined 触发暂停，历史成功事实不被抹掉。显式文件 legacy 回退中的 Memory review 继续父前缀/快照和完成后计数规则；默认 document 使用当前入口和版本失效机制，Dreaming 用独立受限会话、持久源流进度，不继承父 prompt。

#### Scenario: fast review 与 slow review 使用同一调和结果
- **GIVEN** 已有 self-evolution review 成功创建 agent-scope 或 global-scope Skill 的持久事实
- **WHEN** 事实在前台 terminal 之前或之后完成调和
- **THEN** 按真实结果保留历史事件和可发现资产，已存在的同名禁用选择不被覆盖；不因此恢复后台 Skill fork。

#### Scenario: 后续前台轮次与 stream 重连不重复调和
- **GIVEN** 同一 session 的持久事件消费已建立
- **WHEN** 历史创建事件被实时接收或重放
- **THEN** 同一结果不重复处理，未禁用的新 Skill 在后续 session 可用。

### Requirement: 模型可在配置中声明各自的上下文窗口

运维者可在 Gateway config 的 `llm.providers[].models[]` 条目上为某模型声明 `context_window`（与 `extra_request_body` 同级，可选）。该值随模型配置流入内核，并在用该模型的对话中决定上下文压缩的边界。未声明 `context_window` 的模型条目按内核默认上限处理；Gateway 回写 config 时保留已声明的 `context_window`，未声明的不写该字段。

#### Scenario: 某模型声明 context_window 后生效
- **GIVEN** config 某模型条目声明了 `context_window`（≠ 内核默认）
- **WHEN** 运维者用该模型经 Gateway 跑一个持续增长的对话
- **THEN** 压缩在该声明值对应的边界触发,而非内核默认上限边界

#### Scenario: 未声明 context_window 的模型按内核默认上限判定
- **GIVEN** config 某模型条目无 `context_window` 字段
- **WHEN** 运维者用该模型经 Gateway 跑对话
- **THEN** Gateway 正常启动并对话,按内核默认上限判定压缩,不因缺少该字段而报错

#### Scenario: context_window 配成非法值时回退
- **GIVEN** config 某模型条目把 `context_window` 写成非正整数
- **WHEN** 运维者用该模型经 Gateway 跑对话
- **THEN** Gateway 不崩溃,按未声明处理回退内核默认上限

### Requirement: Workflow 是 Agent 可选且默认关闭的完整能力

#### Scenario: 能力列表提供 Workflow
- **WHEN** IM 查询节点或 Agent 可选工具
- **THEN** Gateway 报告 `Workflow` 为可选择、默认关闭的工具，并提供描述

#### Scenario: 保存启用 Workflow
- **WHEN** 用户把 `Workflow` 加入 Agent tool allowlist 并保存成功
- **THEN** Agent 的下一轮完整采用 Workflow tool、prompt、commands 与 ultracode 入口

#### Scenario: 保存禁用 Workflow
- **WHEN** 用户从 Agent tool allowlist 移除 `Workflow` 并保存成功
- **THEN** Agent 的下一轮完整移除相同能力，不保留 hidden Workflow prompt

#### Scenario: 运行中配置更新
- **WHEN** Agent 正在回复或已启动 Workflow 时保存新的 Workflow 工具选择
- **THEN** 当前整轮及其 Workflow 保持启动时配置，下一轮整体采用新配置

### Requirement: 全局主 Agent 保留默认工具并具备固定基础能力

#### Scenario: 新建全局 Agent 时保留正常执行能力
- **WHEN** 用户新建全局 Agent
- **THEN** 除读取收件箱、查阅聊天、显式发言及委派的固定基础工具外，仍默认拥有现有创建流程提供的工具
- **AND** 不因选择全局模式变成只能统筹、不能正常查询或执行的空工具 Agent

#### Scenario: 固定基础工具与可配置工具区分
- **GIVEN** 用户创建或编辑全局 Agent
- **WHEN** 查看和调整工具配置
- **THEN** `inbox`、`conversations`、`read_messages`、`search_messages`、`threads`、`send_message`、`delegate_worker` 作为固定基础工具，不可关闭
- **AND** Personal Global 另外固定 personal_sources；其他工具继续按默认选择及依赖规则配置，single_thread 和子 Agent 不继承 Global 根会话固定项

### Requirement: 恢复历史后台创建的 Skill 时保留既有会话提示词

#### Scenario: 后台新增技能保持当前上下文缓存前缀
- **GIVEN** Agent 的历史后台自进化已成功创建技能
- **WHEN** Gateway 保存该技能且原生发现刷新，既有会话开始下一轮
- **THEN** 技能可由工具读取，但不因该自动增量重建提示词目录或生成配置分界线
- **AND** 新会话及压缩等既有重建边界可吸收新目录；该保护以当前进程内会话快照为界，重启不保留旧快照

#### Scenario: 手动取消或重新启用技能后，下一轮采用显式选择
- **GIVEN** 技能曾由后台自动新增并启用
- **WHEN** 用户手动取消，或取消后重新启用该技能
- **THEN** 下一轮按显式配置更新目录并保留既有配置分界行为

### Requirement: 可替代能力采用原生工具名称与用法并允许受控升级

#### Scenario: 使用通用工具
- **WHEN** 助手使用已由DSH提供的等价工具或Skill调用入口
- **THEN** 使用其原生名称、参数及命令方式；迁移后的既有Skill仍能完成工作，不依赖旧名字或旧schema兼容层。

#### Scenario: 截断读取与后台输出
- **WHEN** 文件超过单次读取范围，或后台工具完成
- **THEN** 截断明确可继续读取；助手通过原生输出工具读取后台结果后正常向用户交付，不要求用户手动操作内部工具。

#### Scenario: 升级上游工具
- **WHEN** 维护者升级受支持的DSH版本并完成产品接入验证
- **THEN** 可使用更新后的原生工具能力；身份、权限、Skill引用及结果交付仍有效，不被复制的旧实现固定住。

### Requirement: 自建工具支持节点全局与workspace两层

#### Scenario: 共享、局部及同名覆盖
- **GIVEN** 本节点owner共享工具和workspace A的同名工具，另有workspace B
- **WHEN** A或B的主会话及被允许的子任务使用工具
- **THEN** A优先使用局部版本，B使用共享版本；A的私有工具不出现在B，工具名单继续限制可用能力。

#### Scenario: 重启和同workspace多会话
- **WHEN** 同一workspace建立多个会话或服务重启
- **THEN** 按该workspace的同一份持久扩展声明装配，局部工具不因为包已安装而自动全局启用。

### Requirement: Feature可独立启停并撤销其后续影响

#### Scenario: 关闭和重新开启单项能力
- **WHEN** 用户合法关闭再开启 Task Graphs、Cron 或 Heartbeat
- **THEN** 原有依赖、工作保护和工具选择规则保持，其他 Feature/Agent 不受影响，不累积重复监听；不恢复后台 Skill 自进化。
- **AND** 记忆是内置能力，旧 Memory Curation 和 Skill Creation 开关不出现在客户端；skill-creator 固定内置，无需选择；document 的 Dreaming 独立控制自动整理，关闭保留记忆读取和当前对话响应，暂停长期记忆自动更新，手动请求仍通过 Dreaming。

#### Scenario: 关闭期间重启与在途工作
- **WHEN** 已关闭的 Feature 经历节点重启，或在工作已接受后尝试关闭
- **THEN** 不擅自重新启用；业务 Feature 仍按既有在途责任拒绝不合法关闭。Dreaming 允许停用新自动准入并取消未应用的自动部分，保留实际已保存结果及未完成范围。
- **AND** 配置持久化但应用尚未确认时显示 pending，不伪报 effective 或回滚。

### Requirement: 由节点验证并持久化模型连接

模型路由由 Node 持有，新 API/OAuth 凭据保留在节点的 DSH 原生凭据存储。原生 Codex 接入沿用 DSH 执行运行时；发现 CLI 不等同于授权或验证成功。已运行的兼容代理可以复用，无需安装第二套执行引擎。

#### Scenario: API 或已有代理
- WHEN owner 通过 IM 完成连接设置与验证
- THEN 新助手可使用通过验证的模型，节点重启后配置仍可用，回传状态不包含密钥。

#### Scenario: Codex 登录
- WHEN 用户选择 Codex 订阅连接
- THEN 在需要时显示一次性登录指引与取消/重试动作；成功后才允许验证模型，不复制 CLI refresh token 制造另一刷新所有者。

### Requirement: 模型服务修改经验证后持久生效

#### Scenario: 同名上游模型分属不同服务
- **WHEN** 用户给不同服务配置相同上游模型 ID
- **THEN** 助手可以明确选择其中一个，调用使用所选服务的连接与该上游 ID，原有模型引用保持有效。

#### Scenario: 成功编辑与失败恢复
- **WHEN** 用户修改连接地址、凭据或模型并保存
- **THEN** 候选连接实际测试成功后才替换原配置；既有助手保持引用并在后续调用使用更新连接，刷新及节点重启后保持。
- **AND** 验证失败或提交前取消不会使原来可用的连接变成失败候选。

#### Scenario: 拒绝旧版本与在用引用移除
- **WHEN** 提交基于旧版本的模型配置，或移除当前主模型、备用模型、默认模型隐式依赖或审批模型引用
- **THEN** 拒绝本次修改并保留有效配置，不静默替换助手选择；Agent 配置与模型服务并发保存仍不能留下悬空引用。

#### Scenario: 凭据限于执行电脑
- **WHEN** 用户提交或再次编辑 API key
- **THEN** 密钥保存在执行电脑的凭据存储中，不经状态查询返回，也不写入 IM 数据库或非敏感配置投影；空输入保留现有凭据。

### Requirement: Workspace 和全局 Skill 使用禁用名单

Agent 使用 `skills_selection_mode=explicit_denylist`，`skills` 保存禁用名称。配置界面仍以勾选表示启用；保存的是取消项，暂时缺失的禁用名称保留。工具白名单不受影响。

#### Scenario: 新建或复制导入的技能默认可用
- **WHEN** 在 Agent 可发现的 Workspace 或共享全局 roots 新增有效 Skill
- **THEN** 后续模型步骤可发现并按名加载，无需修改启用名单或重启；共享全局新增技能对可访问该目录的 Agent 默认可用
- **AND** 其他 Workspace 的私有 Skill 不泄漏；同名覆盖仍按已有 roots 优先级

#### Scenario: 明确禁用在所有消费者一致生效
- **WHEN** 用户合法取消勾选不再被开启 Feature 需要的 Skill 并保存
- **THEN** 后续回复的目录、按名加载、显式命令、preview、distillation readiness 和 SlashPicker 一致排除该名称
- **AND** 重启、重新扫描或同名技能重新创建不会自动启用；旧回复沿配置安全边界收口

#### Scenario: 旧配置升级保留已有选择
- **WHEN** 节点连接 IM 后迁移旧 default-discovery 或 explicit-allowlist 配置
- **THEN** default 转为空禁用名单；allowlist 以该 Agent 迁移时的完整候选集合减去旧已选名称形成禁用名单，包括旧显式空名单
- **AND** 经已有版本化配置操作同时提交 Node YAML、runtime 与 IM profile；离线不猜候选，已经迁移的配置不重复转换
- **AND** 迁移后新增名称默认可用；旧配置没有记录候选历史，迁移只保证迁移当时已有候选的选择状态

#### Scenario: 创建事实不覆盖用户禁用
- **WHEN** 前台或后台成功创建 Skill 并产生知识更新事实
- **THEN** 继续记录真实来源与通知，但不追加任何 Agent 的启用配置；是否可用由发现及禁用名单共同决定

#### Scenario: 禁用蒸馏技能时明确不可用
- **GIVEN** Agent 禁用了会话蒸馏 Skill，或离线旧模式的显式 allowlist 不包含它
- **WHEN** 用户请求生成或蒸馏 Skill
- **THEN** 返回明确的 distiller unavailable 结果，不因文件存在而放行

#### Scenario: 离线历史配置保持原模式
- **GIVEN** 节点尚未完成认证迁移
- **WHEN** 节点离线工作或旧模式会话继续执行
- **THEN** 历史 default discovery 保持发现行为，显式 allowlist 包括空名单仍按原选择限制；不凭缺失候选推断禁用名单

### Requirement: Agent 可在 workspace 自助安装原生工具

Agent 启用 `plugin_manager`（含通过默认开启的 `plugin_management`「插件开发与管理」运行特性启用，或独立勾选该工具）后，可以在可信配置确定的 workspace 创建标准 DSH bundle（包括工具、提示词和其他适用 workspace scope 的插件贡献），安装、启用、停用和移除。宿主只读运行时检查工具（`cordis_inspect_list`、`cordis_inspect_query`）作为默认开启的标准可选工具随 `plugin_management` 特性联动启用，也可在特性关闭后按静态工具选择单独启用或停用，用于查询宿主已注册的服务、事件、配置 Schema 与当前可见工具声明。新增且不与既有工具名冲突的已启用 workspace 插件工具自动并入该 Agent 的有效集合，并在能力目录中携带 `source_group="workspace"` 及所属插件包的标识与显示标题，不要求人工修改静态白名单。静态工具选择和禁用保持；关闭 `plugin_manager` 或显式空工具集不自动获得自装 workspace 业务工具；升级前已保存配置按既有 `plugin_manager` 权限平滑承接特性与只读检查工具状态。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

#### Scenario: 安装后既有聊天立即使用
- **WHEN** Agent 成功安装并启用 workspace 工具
- **THEN** 同 workspace 既有及新聊天可使用它，不需重启；其他 workspace 不可发现或执行

#### Scenario: 失败不声称已启用
- **WHEN** 包安装或实际加载失败
- **THEN** Agent 收到失败状态和真实诊断；包管理成功不代替执行可用证据

#### Scenario: 重启和撤销
- **WHEN** 节点重启或 Agent 停用/移除已安装 bundle
- **THEN** 重启保留持久选择，停用/移除后后续调用不可执行对应工具，且已停用或移除插件的工具从当前运行时能力目录中移除

#### Scenario: 保留其他工具选择
- **GIVEN** 已有禁用工具或显式空集
- **WHEN** 该 workspace 安装新增工具
- **THEN** 既有禁用选择不改变，空集不自动扩宽

#### Scenario: 非工具插件及整体停用
- **WHEN** Agent 安装不注册工具的提示词插件，随后用户停用或重新启用
- **THEN** 当前 workspace 的提示词贡献生效、撤销或恢复，其他 workspace 不受影响；DSH 生命周期管理的资源一并回收

#### Scenario: 网页与聊天管理同一原生插件状态
- **WHEN** 已认证的所属用户从 Agent 设置管理插件
- **THEN** Node 从可信 Agent 配置解析 workspace，网页与聊天操作同一份持久安装和启用状态，不修改宿主全局 profile
- **AND** 忙碌时网页操作等待 workspace 执行空闲，状态查询仍可用，并发管理明确返回忙碌而不死锁；未完成操作不报成功

#### Scenario: 停用状态在更新时保留
- **GIVEN** 已安装包处于停用
- **WHEN** Agent 更新同名包且没有显式要求开启
- **THEN** 包仍停用，重启保持已完成的选择

#### Scenario: 第三方插件的宿主依赖与 workspace 配置
- **WHEN** Agent 安装声明兼容当前 DSH 的第三方 bundle，并通过 workspace 原生 user overlay 配置其服务作用域
- **THEN** 插件可复用宿主公开依赖，配置在该 workspace 热应用；不要求复制运行时、修改宿主 profile 或静态工具白名单
- **AND** 该 preset 提供压缩引擎时，自动与人工压缩由该引擎负责；停用后恢复默认引擎，其他 workspace 保持原有行为

#### Scenario: 只读运行时检查与插件开发管理特性联动并支持独立选择
- **WHEN** Agent 开启 `plugin_management` 运行特性，或在关闭该特性后单独在工具选择中启用 `cordis_inspect_list` 或 `cordis_inspect_query`，且当前会话属于拥有可信 workspace 的根会话或显式 `subagent_fork`
- **THEN** 模型可调用被选中的只读运行时检查工具读取宿主服务、事件、插件配置 Schema 与可见工具契约，不因此开放动态代码定义或运行能力，单独启用检查工具也不反向开启 `plugin_management` 或 `plugin_manager`
- **WHEN** Agent 未选中对应检查工具（含在线撤回后），或当前会话属于无 workspace、普通子 Agent 或 Global 一级执行者
- **THEN** 模型下发工具集不含对应检查工具，直接调用被拒绝

#### Scenario: 存量配置平滑承接插件管理权限
- **GIVEN** 升级前已保存且未显式记录 `plugin_management` 特性的存量 Agent 配置
- **WHEN** 节点启动校验、上报能力或创建会话
- **THEN** 原先允许使用 `plugin_manager` 的配置自动具备 `cordis_inspect_list` 与 `cordis_inspect_query` 有效权限（`nano-plugin-development` 仍处于有效选择且所需能力可用时 `plugin_management` 特性按开启解释），不因新增伴随工具触发依赖缺失阻断；原先显式工具白名单不含 `plugin_manager` 的受限配置保持 `plugin_management` 关闭且不扩宽可用工具集

### Requirement: Agent 获得适用版本的 workspace 插件开发指导

启用插件管理的 Agent 应能发现基于 DSH 原始 Skill 适配并随安装版本提供的专门开发指导，并按任务读取适用能力的当前公开 API 资料。指导覆盖工具、提示词、插件私有服务、受支持局部监听及高级压缩扩展，明确 workspace 共享范围、宿主保留职责与可信本地代码边界。显式技能选择仍生效，接口可发现不等于所有宿主能力开放。

#### Scenario: 自然语言目标驱动创建与实际使用
- **WHEN** 用户要求创建可重复使用的业务插件
- **THEN** Agent 能按随包指导查询当前版本适用接口、创建并安装插件，在实际使用成功后报告可用；无需用户提供开发教程

#### Scenario: 按需发现与禁用选择
- **WHEN** Agent 查询插件开发信息，或用户禁用了对应开发 Skill
- **THEN** 只提供当前支持主题的版本与公开资料入口，不泄露其他 workspace 配置；技能禁用选择不被强制加载绕过

#### Scenario: 宿主与客户端范围说明
- **WHEN** 用户要求插件修改客户端界面、宿主身份审批或其他 workspace，或询问能否隔离任意来源代码
- **THEN** Agent 明确这些不属于当前插件支持承诺，不把 DSH UI 安装视为 Nano 客户端扩展，不把 workspace 作用域视为操作系统沙箱

#### Scenario: 验证与修复真实结果
- **WHEN** 插件安装后不可用，或用户要求更新、停用与恢复
- **THEN** Agent 区分安装、实际业务效果与持续生效，提供真实诊断并按现有管理路径修复；停用后不再产生对应受管贡献，已有用户数据不被擅自删除

#### Scenario: 保持原生安装与更新结果
- **WHEN** Agent 安装新插件、启停已有插件或覆盖安装已存在的包
- **THEN** 指导与结果区分在线启停和代码替换；覆盖安装保留 DSH 原生待重启语义，不承诺额外热更新、不将 restart-required 报告为新版已经可用，正常重启后再实调验证新版

### Requirement: 任意 Agent 可按任务需要交付通用交互回复

普通与 Global/Personal Agent SHALL 能为 Web IM 任务选择通用交互表达；简单文字任务不被强制转成表单。交互选择按真实用户来源进入既有任务执行链，界面不能绕过当前权限与公开交付约束。

#### Scenario: 不同任务选择表达方式
- **WHEN** 用户提出知识讲解、条件探索、方案比较、草稿修改或信息提醒
- **THEN** Agent 能组合适合的交互形式，并理解用户实际选择；不要求进入专用业务页面。

#### Scenario: 用 UI 表达答复
- **WHEN** Agent 选择用交互 UI 回答
- **THEN** Agent 按内容选择便于读者理解的结构、图形或交互方式；普通、Global 与 PA 均可单独发送有效 UI。
- **AND** 接收 Agent 的上下文将公开 UI 标为发送方的消息内容，提供源码和适用的消息替换引用，省略渲染协议元数据；无 UI、无正文的空回复仍被拒绝，既有权限、审核与回执语义不变。

#### Scenario: 群内纯 UI 回复可投递
- **WHEN** Agent 向群聊发布正文为空的有效 UI 回复
- **THEN** 其他群内 Agent 按既有接收与提醒策略获得这条公开 UI，不因没有摘要而漏送；空白流式占位消息仍不作为回复转发。

#### Scenario: 不支持交互的渠道
- **WHEN** Agent 向不支持交互的外部 channel 交付
- **THEN** 使用可读文字答复；没有文字时明确拒绝，不把 UI 静默丢弃后发送空内容，也不泄露界面源码。

### Requirement: Intelligent UI Feature 可配置

#### Scenario: 默认启用和显式关闭
- Agent 配置页 Features 提供 `intelligent_ui`，默认勾选，缺失值按开启解释。
- 合法取消勾选并保存后，运行时移除交互生成指导，按共享依赖规则默认取消关联工具/Skill；有效 send_message 的显式合法 interactive 参数仍能发布新卡片，文字交付保留。重新勾选恢复完整依赖及指导。
- 关闭不删除已发布卡片、个人草稿或选择，历史卡片继续按原消息权限读取与提交。

#### Scenario: Feature 关闭但工具独立可用
- **GIVEN** Intelligent UI Feature 关闭，send_message 仍为固定或独立启用
- **WHEN** 普通、Global 或 Personal Agent 使用显式合法 interactive 参数发布
- **THEN** 不因 Feature 关闭而拒绝新卡片，仍执行既有 schema、身份权限、审批和交付检查；不反向恢复额外交互生成指导
- **AND** 不支持交互的外部渠道使用文字答复；支持交互的聊天不要求独立摘要，历史卡片权限与提交行为不变

### Requirement: 普通提问能主动获得适用交互表达

#### Scenario: 无界面提示的知识提问
- **WHEN** 用户只提出“给我讲解下冒泡排序”这样的普通问题
- **THEN** Agent 能主动用有助于理解过程的交互回复，不要求用户点名界面形式；实现与提示不含该题专用逻辑。
- **AND** 跨领域普通问题同样按内容选择表达，单一事实仍可简短文字回答。

#### Scenario: 保留 OpenUI 能力并遵守既有执行权限
- **WHEN** Agent 使用上游组件、局部状态、计算、动作或已接入查询/修改工具
- **THEN** 不因静态表单切片额外裁剪界面能力；真实业务工具执行继续受既有身份与审批约束，未接入能力如实说明。

### Requirement: Agent 按用户话语理解交互背景

#### Scenario: 指代、换题与授权
- **WHEN** 私聊自然消息携带了发问时的卡片改动
- **THEN** Agent 只把这条消息实际携带的每张卡片最新状态当作可参考的私人背景，各自保留来源，不混合不同卡片字段，根据用户原话判断是否使用，换题可忽略，指代不明时可澄清
- **AND** 背景数据不替代正文、不构成业务授权；由 IM 判定这次是否携带以及范围，Agent 不据此推断其他卡片状态，也不索要更多未提交内容

#### Scenario: 未携带背景的追问
- **WHEN** 用户上一条消息曾携带卡片改动，本条普通消息没有携带
- **THEN** Agent 不把上次的卡片状态当作本条消息的背景，需要时按用户原话澄清或请用户再说明

#### Scenario: 群聊不读取私人操作
- **WHEN** 用户在群聊操作卡片后正常发言
- **THEN** 所有 Agent 均不取得未提交状态；明确提交后按公开消息读取已提交快照。

### Requirement: 所有 Agent 默认使用无摘要换窗并支持显式回退

#### Scenario: 新建与既有 Agent 默认生效
- **WHEN** 新建或升级前已存在的普通、Global、Personal 或子 Agent 开始工作，用户未显式停用该能力
- **THEN** 默认使用无摘要换窗及配套恢复工具，无需逐 workspace 安装或修改业务工具 allowlist
- **AND** 不扩大业务操作权限

#### Scenario: 用户显式停用后重启
- **GIVEN** 用户通过现有 workspace 插件入口停用了该能力
- **WHEN** 节点重启或该 workspace 创建新 Agent
- **THEN** 保持停用并使用原摘要压缩，直至用户重新启用；其他 workspace 的选择不改变

### Requirement: 上下文恢复引用简短且稳定

#### Scenario: 首次阅读任务与工具结果
- **WHEN** Agent 首次阅读普通用户材料或最终工具结果
- **THEN** 正文末尾提供窗口内有序短编号，无需另查引用表
- **AND** assistant 与窗口控制消息不加正文标记

#### Scenario: 新窗口独立编号
- **WHEN** 成功切换到一个新窗口
- **THEN** 该窗新内容从短编号 1 开始，不同窗口可以重号，并通过 window_id 与 item_id 成对定位
- **AND** 同一规则下已发出的窗口编号及恢复引用保持不变；同窗内裁剪、进程重启或失败换窗不重排编号；不迁移旧版本会话级编号

#### Scenario: 裁剪、换窗与重启后恢复原文
- **GIVEN** Agent 已记录当前窗口与材料的短编号
- **WHEN** 经历裁剪、换窗或同一会话进程重启后恢复材料
- **THEN** 原编号保持有效，可恢复原始内容并分段继续读取，原文中形似引用标记的内容仍保留
- **AND** 物理替换副本不形成重复 History 项，单独补标记不使活动原文成为归档项

#### Scenario: 标记不改变既有业务证据与授权
- **WHEN** 宿主读取带短引用材料的结构化审批证据、Task 消费回执或 source_history
- **THEN** 审批证据与消费回执仍对应原始业务正文，source_history 仍使用原宿主证据序号
- **AND** 既有来源、身份与访问权限范围保留，短引用不构成新的操作授权

### Requirement: 剩余上下文预算简洁表达

#### Scenario: 查询剩余预算
- **WHEN** Agent 调用 get_context_remaining 查询当前窗口预算
- **THEN** 仅获得工作预算剩余量或未知状态，并知道该数值是估算
- **AND** 默认结果不携带内部预算中间参数或引用分页

### Requirement: 无摘要换窗的 workspace 支持持续任务与按需恢复

#### Scenario: 多次换窗后继续任务
- **GIVEN** 用户在已启用该能力的 workspace 提供了目标、限制并在后续纠正过要求
- **WHEN** 同一个未完成任务经历多次上下文换窗
- **THEN** Agent 能利用已保存记录与原始历史继续工作，按最新有效要求交付，不要求用户重复提供仍可恢复的信息
- **AND** 不因换窗重复已经完成的外部副作用，不把未完成事项报告为完成

#### Scenario: 恢复原始细节或说明缺口
- **WHEN** 换窗后的任务需要早先消息或较长工具结果中的细节
- **THEN** Agent 可以按需恢复已离开活动上下文的原始记录及来源，并据此继续工作
- **AND** 缺失记录时如实说明具体缺口，不编造已经恢复的信息

#### Scenario: 新任务已读后大批工具结果造成上下文压力
- **GIVEN** 旧笔记记录旧事项已完成，而 Agent 已读到新的直接或 Inbox 请求且尚未完成
- **WHEN** 在保存新笔记前，大批工具结果使活动上下文达到工作预算
- **THEN** 系统先复用 DSH 原生工具结果裁剪并重新测量；压力已解除时保留当前窗口和新任务，继续处理与交付
- **AND** 原始工具记录及其来源仍可按需恢复，不以裁剪后的预览冒充完整资料
- **AND** 裁剪后仍超硬阈值时沿用既有无摘要换窗；不新增自动任务正文或用户未批准的恢复提示

#### Scenario: 长任务按需恢复 Skill
- **GIVEN** 会话曾使用多个 Skill 并已发生换窗
- **WHEN** Agent 继续工作或需要此前使用的操作指导
- **THEN** 新窗口根据当前能力重建可用 Skill 目录，不自动重放此前加载的正文或整个会话的已用 Skill 索引
- **AND** Agent 按需通过已获准的 Skill/文件工具读取，或从当前会话 History 恢复此前原始加载记录；无 `skill/read` 工具时也不回退自动正文、不扩大权限
- **AND** 普通工具进展与历史导航不会让未变化的 Skill 正文每步重复进入上下文
- **AND** 显式停用新模式后，旧摘要模式的 Skill 恢复行为保持

#### Scenario: Explicit Skill gestures survive later tool-history pruning
- **GIVEN** a complete successful host-observed live Inbox result contains an explicit Skill gesture from a human non-partial message
- **WHEN** native pressure pruning later shortens that tool result's active text
- **THEN** the permitted selected Skill has been recognized once from the original source; subsequent steps neither reparse the pruned text and fail nor inject the Skill again
- **AND** agent/system, partial, failed and restored results do not become new human Skill gestures

### Requirement: 换窗记录在同一会话重启后保留且不扩大访问授权

#### Scenario: 正常重启与重新启用
- **GIVEN** 当前会话已保存工作记录
- **WHEN** 节点正常重启，或能力停用后重新启用
- **THEN** 同一会话可继续访问其已保存记录；停用不删除记录，停用期间的未来工作恢复原摘要压缩行为，重新启用后使用该换窗能力

#### Scenario: 请求其他归属的记录
- **WHEN** 当前任务尝试读取既有权限之外的其他 Agent 或 workspace 记录
- **THEN** 不获得记录，恢复出的内容也不形成新的外部操作授权

### Requirement: DSH Goal 工具 SHALL 默认不选并可逐项配置

#### Scenario: 现有及新建 Agent
- **WHEN** Agent 使用默认工具集合
- **THEN** create_goal、get_goal、update_goal 默认不选，无 Goal 工具时不注入其专属引导；显式白名单包含的 Goal 工具按用户选择生效，不另设 Feature 总开关。
- **AND** Task 持续执行独立生效，不转换、双写或同步两套状态，不进行历史 Goal 迁移或清理。

#### Scenario: 用户显式开启和关闭
- **WHEN** 用户在配置页工具列表选择或取消某个 Goal 工具
- **THEN** 仅该工具的选择改变，不联动其他 Goal 工具；沿用普通工具配置的生效规则及原生语义与授权，不额外改变 Goal 生命周期，不影响 Task 的执行责任。

### Requirement: 知识维护按长期价值与明确归属保存内容

Gateway 的文档记忆保存长期理解，Skill 保存成熟可复用方法；个人偏好、专业经验、环境与项目背景按主体角色归入当前文档，保留来源、条件、反例与未知部分。完整知识只在一处维护。默认暂停旧条目记忆及其复盘，仅文件显式 legacy 回退时保留旧规则，不与新文档模式同时写入。

#### Scenario: 重复信息及明确纠正
- **GIVEN** 用户已保存一项事实或偏好
- **WHEN** 用户重复表达或明确纠正该内容
- **THEN** 文档模式的当前会话及收到纠正的原执行者立即采用新内容，正式正文和入口仅由后续 Dreaming 更新，不生成同义副本；未整理不宣称长期记忆更新完成或跨聊天即时同步。legacy 保留原新会话消费保证。

#### Scenario: 经验证的方法与临时应对
- **WHEN** 一次任务产生可复用的方法、失败尝试或临时应对方式
- **THEN** 知识保留真实结果、条件和必要原因，不把失败尝试写成可靠方法；成熟方法可以在任务中通过 skill-creator 保存为 Skill。
- **AND** 临时资源规则保留条件与退出责任，Agent 选择不冒充用户要求，普通经验不强制发布 Skill。

#### Scenario: 单项和联合维护的知识归属一致
- **WHEN** 同一纠正涉及 Memory 和 Skill
- **THEN** 完整规则保存在正确位置，不因某链路缺少另一种工具而重复保存或改变归属。
- **AND** 自动 Skill 复盘及联合复盘中的 Skill 部分暂停；普通前台仅可维护 Skill，正式记忆只由 Dreaming 更新，两者均遵守工具权限与真实结果要求。

#### Scenario: 后台维护读取当前持久知识
- **GIVEN** 前次 Dreaming 已保存新内容
- **WHEN** 后台准备修改该知识
- **THEN** 通过获准读取取得当前完整内容并核对版本，不能依赖父快照覆盖较新的文件；读取失败或未完成不写依赖该内容的修改。

#### Scenario: Memory 读取未完成但模型正常停止
- **WHEN** 后台读取被拒绝、失败或未读完整，随后模型正常停止
- **THEN** 该部分仍为未完成，不推进对应处理位置或旧维护周期；实际已保存内容与历史回执保留，不误报整体成功。

### Requirement: Skill 维护工具按单次操作报告实际结果

Skill 维护 SHALL 保留受控的 agent/global 写入范围。局部 patch 只修改唯一匹配的主文档文本，edit 替换完整主文档。多个调用不构成共同事务，后续失败不表示前序成功操作被撤销。

#### Scenario: 多步维护部分成功
- **WHEN** 一次维护的前序写入成功，后续调用失败
- **THEN** 用户收到与实际文件状态一致的结果，能区分已完成和未完成部分，不会被告知全部自动回滚或全部成功。

#### Scenario: 后台修改已有 Skill 文件
- **WHEN** 后台 review 尝试修改或移除已有 Skill 文件
- **THEN** 本轮必须通过获准的文件读取工具完整读取同一目标原文件；Skill 指令加载、父历史、搜索片段和目录列表不能代替原文件内容
- **AND** 未读完整、路径不符或当前文件与本轮已知内容不一致时，系统拒绝该写入，不发布成功结果。

### Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖

本条的静态工具选择规则适用于 `single_thread` 及 Global／PA 主会话的可配置工具；Global／PA 普通内部执行者遵循本 area 的分层工作能力条目，不套用主会话的普通工具名单。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的已启用 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制（`dsh-agent-context` 插件）启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用该插件即从运行时撤销其注册并从 `fixed_tools` 与能力目录移除。global 主 Agent 的有效集为配置集合与固定基础项的并集；其他工具（含 `cordis_inspect_list` 与 `cordis_inspect_query`）仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，插件开发与管理、任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为上述主会话构建可配置工具集时，以该 Agent 配置的 `tool_allowlist` 为静态白名单单一来源（升级前未显式记录 `plugin_management` 且包含 `plugin_manager` 的存量配置按承接规则隐式包含 `cordis_inspect_list` 与 `cordis_inspect_query`）：除已启用上下文插件的四个内部工具以及启用 `plugin_manager` 时的已启用 workspace 自建工具增量外，非空时 Agent 静态业务工具集**恰为**有效选中的这些（列表外的默认工具不提供，即默认文件/web/只读自省工具均可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按插件启停状态挂载或卸载，预览、下发和实际执行保持一致。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的合法 `tool_allowlist` 被设为不含某默认工具的非空显式集，且没有开启的 Feature 需要该工具
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单拒绝业务工具但保留上下文内部操作
- **GIVEN** single_thread Agent 的 `tool_allowlist` 显式为空，所有依赖业务工具的 Feature 均关闭
- **WHEN** 用户与该 Agent 会话，模型尝试调用业务工具
- **THEN** 业务工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈
- **AND** 已启用的上下文机制仍可调用四个内部工具；停用后它们也不可调用

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** single_thread PA agent 已持久化显式记录了 `features.plugin_management` 的合法非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除已启用上下文插件的四个内部工具外，仅在启用 `plugin_manager` 时按当前已启用 workspace 插件集合增加不冲突的自建工具名
- **AND** 若白名单不含 `skill`、`apply_patch` 或 `cordis_inspect_list`，session 不启用未列出的对应工具

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 Cron Feature 并已将其全部依赖工具保存到 `tool_allowlist`
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 schedule_create/list/update/delete/run/history 六项；合法关闭 Cron 后按最终工具选择提供，用户单独重新启用的工具不因 Feature 关闭而拒用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`、`cordis_inspect_list` 与 `cordis_inspect_query`
- **AND** 上述工具的 `default_on` 均为 true

#### Scenario: Auto 关闭不阻断会话内部上下文管理
- **GIVEN** 当前 Agent 启用了默认上下文机制，自动审批关闭
- **WHEN** 普通、Global、Personal 或子 Agent 保存笔记、恢复历史、查询预算或请求换窗
- **THEN** 仅作用当前执行会话的四工具无需额外审批即可执行，明确的底层拒绝仍保留
- **AND** 其他业务工具继续遵守原审批、选择与发送重验规则；恢复内容不生成新的授权

### Requirement: Feature SHALL 保证完整依赖并与独立工具行为分离

#### Scenario: 开启 Feature 展开完整依赖
- **WHEN** 用户开启 Feature 或创建采用默认 Feature 的 Agent
- **THEN** 交互式回复需要 send_message、skill 和 nano-interactive-ui；插件开发与管理（`plugin_management`，默认开启）需要 `plugin_manager`、`cordis_inspect_list`、`cordis_inspect_query` 和 `nano-plugin-development`；Task 需要 task_graph 与 Cron Feature；skill-creator 是固定内置指导，不再属于可选 Feature 或 Skill 名单，其实际操作遵守工具权限；Cron 需要 schedule_create/list/update/delete/run/history；Heartbeat 需要 read。
- **AND** 内置 document 消费不依赖旧 memory 条目工具；主 Agent/普通 child 对正式记忆只读，文件工具不能直接修改正式库。Dreaming 使用自己的受限维护工具集，不暗中开启父业务工具；缺少可运行所需资源须显示不可用，不能假报运行。
- **AND** 默认开启 Task 的初始配置同时开启 Cron；依赖缺失时显式启用动作失败，已关闭 Skill 不冒充可加载。

#### Scenario: 合法关闭与共享依赖
- **WHEN** 用户关闭没有需要者的 Feature
- **THEN** 取消其直接关联资源，仍被其他 Feature 需要或属于基础固定的能力保留；Dreaming 停用不撤销普通文件工具/内置记忆。
- **AND** 不级联关闭依赖 Feature，关闭 Task 后 Cron 保持开启；随后单独打开工具或 Skill 不反向打开 Feature。

#### Scenario: 独立工具不恢复 Feature 行为
- **GIVEN** Feature 关闭而工具仍被合法独立选中
- **WHEN** Agent 调用 `plugin_manager`、`cordis_inspect_list`、`cordis_inspect_query`、task_graph、skill_manage、schedule 工具，或 legacy 模式下可用的 memory
- **THEN** 操作按原授权与业务前置条件执行，不恢复 Feature 额外行为或已关闭的依赖 Skill；document 不提供旧 memory 条目工具，Skill 工具不恢复自动 fork。

### Requirement: 能力配置 SHALL 在保存边界保护真实需要者

#### Scenario: 静态依赖不能被任意配置入口绕过
- **WHEN** 完整候选配置缺少开启 Feature 的必需依赖，或移除基础固定能力
- **THEN** 配置 API、预览与运行入口明确拒绝，不静默猜测点击顺序、不写入半套能力配置
- **AND** Feature 关闭而工具单独开启的完整配置合法

#### Scenario: 在途工作保护最小能力范围
- **GIVEN** 本 Agent 已接受 legacy Memory 维护或 Heartbeat 工作，或待撤销业务工具正在调用
- **WHEN** 用户尝试关闭仍被该工作需要的能力
- **THEN** 关闭被拒，原配置和业务工作不被本次操作改变；其他无关配置可修改
- **AND** 普通 Agent running、已完成记录和未来未接收的维护机会不构成此类阻碍；Dreaming 自动停用按独立取消规则保留已保存结果，后台 Skill 维护暂停

#### Scenario: 检查后出现的新责任不能绕过关闭保护
- **WHEN** 配置关闭与新 Task 责任或新定时安排并发到达
- **THEN** 先建立的有效责任使关闭被拒；先被接受的关闭使冲突的新责任或安排被拒，不出现双方都成功而能力缺失
- **AND** 使用状态不可确认时明确失败，不把读取失败当作空闲；重试和断联恢复沿既有配置 operation 保持一致

### Requirement: 通用交互说明区分本地采用与发送请求

#### Scenario: 普通 Agent、Global 与 PA 生成草稿
- **WHEN** Agent 使用可用交互能力提供可编辑回复
- **THEN** 可以使用通用 ComposeMessage 将当前编辑内容采用到指定聊天输入框，不需要 PA 专属字段或草稿工具；SendToChat 继续表示向本会话提交请求，不能混淆。
- **AND** 工具 schema、固定提示、加载的 Skill 与示例表达同一语义；系统负责补齐固定 format/catalog_version，Agent 只填写内容及适用的更新参数。

#### Scenario: 实际注册与恢复一致
- **WHEN** 上下文经历唤醒、历史恢复、执行子 Agent 交接或独立审核
- **THEN** 工具身份、来源、已有委托范围和真实发送回执仍一致；本地采用不成为公开发送或新增业务许可；没有暴露的工具不被提示为可调用。

### Requirement: 系统知识维护不进入模型的子 Agent 管理目录

系统启动的 legacy Memory 以及历史 Skill、combined、F4 维护保留当时的继承上下文与独立执行历史；新 Dreaming 使用显式输入和独立受限会话。这些维护均不发布为模型通过 `list_agents` 管理的子 Agent。模型正常委派的 Agent 发现、续接与取消能力保持。

#### Scenario: 长期 Agent 查询受管理的执行者

- **GIVEN** 同一 Agent 已完成多次系统知识维护
- **WHEN** 模型查询直接子 Agent 或递归查询后代 Agent
- **THEN** 新维护运行不在管理目录中，查询不进入这些维护分支；维护不会因历史积累扩大受管理 Agent 集合。
- **AND** 正常模型委派的运行按既有规则列出。

#### Scenario: 维护执行失败或取消

- **WHEN** 系统维护发生模型失败、步骤上限或取消
- **THEN** 保留真实终结状态和此前成功事实，未完成工作不推进维护周期，执行结束后释放运行资源。

### Requirement: 默认原生委派允许两层执行者

#### Scenario: 执行者再委派独立子工作
- **GIVEN** 使用 Nano 默认原生委派深度，主 Agent 深度为 0
- **WHEN** 深度为 1 的执行者创建下级执行者
- **THEN** 允许深度为 2 的执行者执行并按原生机制回传结果；普通与 PA 使用同一默认深度。

#### Scenario: 默认深度不无限扩展
- **GIVEN** 使用默认深度且未显式覆盖普通 spawn/fork 的深度配置
- **WHEN** 深度为 2 的执行者继续尝试创建第三级
- **THEN** 按原生深度上限拒绝；增加一层不改变并发上限、工具选择或授权范围。

### Requirement: 所有模型调用具备匹配入口的技术恢复

#### Scenario: 各用途临时失败
- **WHEN** 主/子 Agent、审核、输入分类、摘要压缩、记忆知识处理、网页提炼或模型连接验证遇到可恢复技术错误
- **THEN** 已有 Agent 请求保持 DSH 原生恢复；当前未覆盖的独立请求通过一个共享组件补齐，按适用策略重试、支持取消并记录尝试；同一请求只由其中一条恢复路径负责，业务层和供应商不叠加重复重试额度。普通恢复默认有界；普通执行的用户显式 provider 策略保留，审核额外上限仍生效。
- **AND** 后续审核尝试仍获得正常判断预算；有效拒绝和永久配置错误不重试至允许。

#### Scenario: 模型连接恢复后继续原轮次
- **WHEN** Gateway 和 DSH 仍存活，主 Agent、各级工作子 Agent 或 Dreaming 提炼／整合 Agent 的模型请求遇到建连失败（含代理明确报告的上游建连失败）、本地流空闲超时或可识别的网络传输断开，包括合盖休眠和开盖联网过程
- **THEN** 保留原轮次和已完成的工具结果，等待期间独立退避并记录尝试，无需真人输入或重新派工，连接恢复后自动继续原步骤。
- **AND** 用户可取消等待。本地流空闲超时且仍可安全使用已配置备用模型时，沿用既有备用链继续同一逻辑任务；备用耗尽或已有工具执行／已发布内容时保留当前原生轮次等待恢复。无法核实出站发布状态时继续等待，包括已进入备用切换后的再次检查；查询挂起和退避等待均可取消。持续等待中的故障交替发生或重复超过普通重试额度不会结束任务，也不消耗普通重试额度。明确的供应商错误、缺少完成标记等协议错误和独立审核沿用各自策略。进程退出后的原任务沿[主及子会话恢复](global-agent.md#scenario-主及各级子会话在进程恢复后自动继续)处理。

#### Scenario: 部分输出与耗尽
- **WHEN** 模型流已输出一部分后失败，或恢复耗尽/被取消
- **THEN** 不把失败片段和新结果拼成伪完整响应，不重复已执行工具副作用；最终失败和取消准确交付业务层，不隐式新开一轮业务恢复。

### Requirement: 角色化文档记忆可及时消费且不扩大权限

#### Scenario: PA 与独立专家
- **WHEN** 长期 Agent 处理跨聊天相关事项
- **THEN** PA 使用主人相关背景，独立专家按实际人物、项目和专业职责使用知识，工作 worker 只获任务材料，Nano 不注入记忆正文、目录、记忆 Skill 或读写指引。文件访问服从普通工作区权限；其他内部角色仍属于原长期主体；不串用不同人的偏好。
- **AND** 当前信息充分时可直接回答，检索不足、部分读取和未知项如实说明；旧记忆、观察和第三方材料不增加业务授权。
- **AND** 所有全局模式主体（含 PA 与 `work_mode === "global"` 的独立专家；`single_thread` 单会话助手除外）的核心记忆首页 `MEMORY.md` 固定维护「主动性与介入偏好」（或对等英文标题 `Proactive & Intervention Preferences`）常驻专区，按「积极盯紧与提前备料」「低打扰挂卡与静默跟进」「免打扰禁区」「触达时机与汇总方式」四类校准自主介入深度与触达节奏（无对应已确认偏好时保留简洁空态；独立专家在首页记录岗位通用准则与单行带协作者/会话限定条件的触发级边界指针，具体协作者沟通格式、证据粒度与项目细则通过普通相对链接下沉至 `entities/` 或 `projects/` 供触发后按需读取）；单次未满阈值的隐式反馈观察专档 `knowledge/proactivity-signals.md` 仅由后台 `Dreaming` 维护，不注入常驻上下文，且宿主文件工具守卫拒绝前台全局主会话或工作子会话读取、通过命令行访问或在检索结果中暴露该观察池文件。

#### Scenario: 关键记忆按上下文窗口加载
- **WHEN** 前台主 Agent 发出初始窗口或成功换窗后新窗口的第一个模型请求
- **THEN** 加载当时的 `MEMORY.md`。同窗后续请求复用该首页快照，包括 Dreaming 改写文件或运行时重启后的请求。
- **AND** 正式记忆文件可按需读取最新内容。普通来源变化和后台整理 checkpoint 不使前台整份记忆不可用，详情页变化不注入提醒或追加上下文快照；Agent 按任务需要读取详情页。成功换窗后的请求只携带一份当前记忆首页与角色上下文，当前上下文统一提供窗口标识，检查点仅保留换窗原因和恢复提示。
- **AND** 内容保存与 Git 版本记录分别报告，正式内容仍只由 Dreaming 更新；未完成的持久更新不能声称已经保存。

#### Scenario: 主 Agent 加载超长首页
- **WHEN** 主 Agent 为新上下文窗口读取工作区的 `MEMORY.md`
- **THEN** 在 8,000 个 UTF-16 码元以内载入全文。超限时，从开头按原顺序保留预算内的完整 Markdown 块或列表项，并告知后续内容已省略，给出完整文件路径供按需读取。
- **AND** 当开头没有能完整容纳的正文时只给出读取提示。该预览仅用于主 Agent 请求，磁盘上的首页原文保留。

### Requirement: Dreaming 处理持续历史的合格增量并保持安静

#### Scenario: 统一凌晨自然日锚点、合盖唤醒补跑不漂移与主体持续工作共存
- **WHEN** 自动 Dreaming 已开启（未在节点本地文件显式覆盖固定滚动 `intervalMs` 时），到达节点同步的管理者有效时区（未同步时回退宿主系统时区）每日凌晨锚点（默认 `03:00`）且该自然日周期尚未完成、主体无条件满足距最近活动安静时长门禁（默认 30 分钟）且无前台在途模型请求
- **THEN** 所有类型 Agent（含 PA、Global 与单会话 Agent，包括进程重启后尚未收到新消息的已持久根会话）统一按同一夜间自然日规则触发：存在合格增量或正式 Git 仓有待修复问题时整理当前和旧窗口已完整保存的经历，不要求根会话结束、不截断正在进行的模型/工具；白天新建的主体从下一次凌晨锚点开始自动周期（不在创建首日白天误触发）；无合格增量且无文件校验或 Git 整理待处理时不调用模型并在整轮收口时标记当夜周期已完成，资源不足保留积压
- **AND** 若节点因半夜合盖休眠或离线错过了凌晨窗口，恢复运行后在同一周期内满足空闲安静条件时自动补跑一次，且补跑完成后下一自动周期仍严格锁定回次日凌晨锚点（不因白天补跑而滑坡漂移到白天时段）
- **AND** 保留实际发生的重复读取与回报，不对轨迹中的消息去重；区分继承背景、消息作者与工具实际结果；不消费主 Inbox、不扫描未授权源、不执行业务动作或发布 Skill

#### Scenario: 失败、冲突、输入分批与重启
- **WHEN** 整理只完成部分材料或部分保存，或保存期间到达新交流/来源撤销
- **THEN** 保留真实成功结果，不恢复已整合的过期结论或已撤销内容；本轮冻结后收到的普通纠正进入后续批次，不冒称已处理；仅确认本批已实际提供给整理者并完成应用的 Global 连续范围及已整合的任务摘要版本；任务摘要的取材省略不冒充完整历史审计，剩余材料可继续，恢复不重复追加同一记录
- **AND** 已有工作视图显示实际处理范围、变更、延期和未完成结果；普通成功不发聊天通知，模型正常停止不等于全部完成

#### Scenario: 关闭与手动整理
- **WHEN** 用户关闭 Dreaming 或明确请求手动整理
- **THEN** 关闭阻止自动运行，保留已有记忆读取和当前对话响应，长期记忆暂停自动更新；手动整理仍由唯一 Dreaming 写者执行，可不等夜间自动周期随时触发，仍遵守主体停用、权限、输入容量与并发限制

### Requirement: 旧记忆可备份导入，临时旧模式仅经文件选择

#### Scenario: 升级、导入和回切
- **WHEN** 已有 Agent 升级或用户要求整理旧记忆
- **THEN** 默认采用文档记忆并开启 Dreaming，逐字保留旧备份；收到明确导入请求后才由同一个 Dreaming 把备份整理进角色文档，保留原义与来源，重复执行不产生同义副本。
- **AND** 文件可选 legacy，切换时仅所选机制运行，两库独立保存而不双向自动转换；默认历史处理从启用点开始，不暗中扫描全部旧聊天。

### Requirement: 停止使用和撤销来源不得被后台复活

#### Scenario: 明确停止采用知识
- **WHEN** 用户明确要求忘掉或停止使用某些内容
- **THEN** 主 Agent 当前及后续适用回答立即遵守并向相关原执行者传递要求，不调用遗忘工具、不登记持久停用名单；Dreaming 后续从聊天原文理解要求的范围，修改正文和入口。
- **AND** 关闭自动整理期间仍保持明确停止采用要求；不把当前遵守当作完成清理，也不声称清除了原始消息、Git、备份和所有副本。

#### Scenario: 后台读取来源
- **WHEN** Dreaming 读取或恢复来源材料
- **THEN** 仍核对当前来源权限和明确停止采用要求，不从无权访问的来源读取新材料，不复活已停止采用的知识。

### Requirement: 后台 Skill 自进化暂停，任务中创建能力保留

#### Scenario: 自动 Skill 维护暂停期间
- **WHEN** 任一运行模式积累 Skill 使用记录、达到旧 F3/F4/combined 门槛或节点重启
- **THEN** 不启动后台 Skill fork 或自动归档，不消费待维护证据冒充已完成；保留已有 Skill、使用统计与历史结果。
- **AND** 普通 Agent 按任务需要使用迁移适配的 Codex skill-creator 创建/维护 Skill，仍遵守现有范围、权限和真实操作回执；Dreaming 不发布 Skill。

### Requirement: skill-creator 内置默认可用，无需用户选择

#### Scenario: 新建、已有和旧配置升级
- **WHEN** 普通长期 Agent 开始任务、恢复或升级配置
- **THEN** 固定获得 skill-creator 的发现入口与简短学习触发指导，按需加载全文；旧 skill_creation=false 或 allowlist/denylist 不关闭这一个产品资产，不使旧合法配置无法启动。
- **AND** 其他 Skill 选择和底层工具权限保留；禁用真实操作工具时如实说明限制，Dreaming 不获得创建能力。

### Requirement: Dreaming 按交流与任务经历组织记忆

本条中轨迹提炼及下属摘要仅适用于仍符合来源资格的执行。Global 和 PA 的工作 worker（包括旧会话及其后代）不再是合格来源；旧摘要不进入新的整合或历史回查。父级真实收到的工作汇报属于父级自身材料。

#### Scenario: Global 原文与第一层任务复盘
- **WHEN** 同一主体的 Global 跨聊天、跨窗口持续交流，存在其他合格的子执行来源或任务变更上下文
- **THEN** Global 合格交流（含已记录在主会话中的 `task-context` 任务状态变更事件，以及全局模式主体在本轮整理开始前从中心同步准入但尚未被主会话步骤消费的合格 `task-context` 事件；面向模型呈现的任务事件正文统一将所属会话与人类操作者标识投影为该主体的 `<= 8` 位短引用以对齐聊天与角色背景，同时保留内部原始消息与会话标识按消息唯一标识去重，保证同一任务操作跨周期精确整合一次、推进对应批次时间截点且不因预取而额外唤醒主会话）保留原文、按连续范围分批进入后台整理；第一层子执行形成会话级任务复盘，与已有记忆一起由一个整理者更新同一文档库。
- **AND** 整理时按可信角色选择反思关注：PA 保留用户目标、处境、关系、帮助效果以及四档主动性校准；独立专家关注领域与项目变化、已确认决定、环境条件、真实成败与多人协作，区分合作者偏好、任务要求与项目决定，并在全局模式下结合宿主提供的绑定管理者身份维护分层主动性校准。共同的证据、适用范围与主动沟通偏好规则保持，按 PA/专家现有实体、知识、事项/项目、历史和短入口维护，不新增互相隔离的知识库；更深层结果经所属任务归纳，不独立逐层摘要。
- **AND** 对 PA 与全局模式独立专家的主动性偏好统一采用快慢双速、归因解耦与多人作用域隔离规则：PA 主人或独立专家绑定管理者针对整体职责明确说出的规矩直接作为常驻规则写入 `MEMORY.md` 的「主动性与介入偏好」对应分栏；单个普通协作者在私聊或针对提给自己的候选卡明确提出的个人边界直接写入带该协作者或该会话范围限定的单行规则并把详细沟通/交付偏好沉淀至 `entities/`（或对应 `projects/`）页面，不越权封杀独立专家对其他团队成员或业务群的正常岗位职责；仅采信人类（`actor.type === "user"`）针对单张 `待拍板`（`proposed`）提议卡的拍板操作（批准、先存着、未采纳关闭或删除）或对自发提醒的单次隐式反应，以顶层列表项（保留协作者与会话作用域）记入 `knowledge/proactivity-signals.md` 观察池，同类同向在同一适用作用域内跨事项或跨天累积满两次及以上才提炼晋升入 `MEMORY.md`（单个协作者的点卡信号晋升为该协作者/会话范围边界，跨项目多方一致印证的岗位经验方可提炼为岗位通用准则）并移出待观察项，超期未复现的孤立样本自动清理；严格区分内容本身的业务评价、触达时间点抱怨（仅调时段与汇总方式，不封杀事项）、常规 `todo`/`doing` 任务的正常完结关闭以及 Agent 自身收起过期提议卡的维护操作。

#### Scenario: 从任务材料形成可复用的理解
- **WHEN** 一份任务复盘包含可复用结论、当时的任务要求和已被替代的尝试
- **THEN** 整合按当前角色判断长期价值，主题页保存有来源的现行认识和适用条件，历史页保留有助于理解或回查的关键经过。
- **AND** 保留任务要求的原适用范围，详细经历仍可通过合格来源回查。

#### Scenario: 按主题重组已有知识
- **WHEN** 一次整合有足够依据更新与本批相关的已有主题
- **THEN** 合并重复、修订过时结论、保留仍适用的例外和关键历史，并维护通往现行内容的链接。
- **AND** 日常请求中直接装入的首页保留跨任务所需的少量内容及按需阅读链接；全局模式主体（PA 与全局独立专家）的首页压缩优先将项目进展与协作者个人交付细节下沉至二级主题页，不截断或省略已确认的主动性适用条件与作用域边界。只更新详情时，仍适用的首页可以保持原样。跨页迁移的有效内容在接收页保存前仍可从原页读取。

#### Scenario: 旧子会话续做
- **WHEN** 仍属于合格来源的子会话继续产生合格历史
- **THEN** 重新从该会话截至本批边界的合格历史按预算选择材料，生成新摘要替换同一会话旧摘要；无更新复用，不生成增量阶段复盘链。
- **AND** 来源与省略清楚，不声称完整重读全部历史；其后无新增 Global 消息也能处理更新。

#### Scenario: fork 继承背景用于理解
- **WHEN** 子任务自身指令或结果依赖继承的父会话条件
- **THEN** 合格继承历史与自身经历一起按输入容量选材，标明背景及原作者、时间、来源；背景曾被整理不代表必须删除，子续做后仍重新提炼并替换摘要。
- **AND** 继承内容不计为 child 新经历，同源引用不算多份独立证据；缺失或未提供的条件保留未知，不新增背景摘要阶段或平行 fork 存储，不突破当前来源资格与允许历史范围。

#### Scenario: 保真轨迹与 History 定位
- **WHEN** 提炼或整合消费经过资格筛选的轨迹
- **THEN** 共享可读格式，保留真实角色、工具名、参数、结果、call id、Inbox 读取过程及 IM 发送者和目标；按实际 session/window 分组并使用可读时间，不显示内部 events 分段、不编造主题或把工具结果改为真人直接输入。
- **AND** 两阶段先裁剪可按来源定位回查的普通单条工具结果，再按整批预算选材，标记省略并保留工具身份及原始定位。Inbox／Conversations 返回正文原样呈现，不按会话来源删消息、不去重、不重排 JSON、不拼接多次读取的片段。原始历史回查保留未做批次裁剪的证据，实际 IM 补查仍执行宿主权限。
- **AND** 来源使用短标签；子会话的原始委派输入及真实发送者为主 Agent 的消息标记 `[main agent]`，真人输入、任务上下文变更（`[task context]`）、其他 Agent 消息、助手文本和工具调用／结果分别区分，不添加 `evidence` 权限解释。只有实际取材遗漏时才显示简短说明。
- **AND** History 指针来自实际可读 item，以 session_id/window_id/item_id 定位；独立 tool/call 不能假充可读 item。缺失定位只保留原工具身份，不生成假引用。
- **AND** 子轨迹仍优先输入及 Inbox/conversations 结果，再助手文本，再其他工具；同层最近优先、调用结果成组，呈现恢复源顺序并区分继承背景和自身经历。

#### Scenario: 固定规则与批次材料分离
- **WHEN** Dreaming 开始整合批次
- **THEN** system message 只放固定职责与工具/证据规则，动态 user message 放角色背景（全局独立专家同步携带可信绑定管理者身份引用）、当前短首页（全局模式主体若已存在 `knowledge/proactivity-signals.md` 观察池，同步内联其当前正文供跨天计数与超期清理，并一并计入首轮预算）、实际目录与来源资格截点。
- **AND** 首轮用户消息直接包含入选的主轨迹（及适用的未消费任务上下文更新）和子任务摘要，标明新增、替换或无信号。换窗后可恢复原始维护输入；详情页按需读，原始业务依据按需用 source_history/conversations 回查。提炼阶段也直接输入选定轨迹。

#### Scenario: 原生维护工具与单写者
- **WHEN** 整合 Agent 编辑或提交记忆
- **THEN** 使用普通文件工具和原生 Bash，正式记忆仓作为 cwd 与写入目标；来源材料只读，工具沿用部署 sandbox，普通主 Agent 禁写正式记忆不变。
- **AND** Dreaming scope 禁止 Bash 后台启动及超时转后台；超时/取消停止对应命令后再结束本批，普通 Agent 后台能力不变。删除和重命名可用于正常重组，同一正式仓保持唯一维护写者。
- **AND** 整合正常结束后若仓库仍有问题，宿主在同一会话最多反馈三次。仍无法完成时尝试恢复该批开始时的 Git 提交，撤销本批新增的未跟踪文件，恢复已跟踪文件至起始提交内容。因模型错误、取消或来源失效而提前结束时，保留实际文件和 Git 历史。

#### Scenario: 提炼输出与整合批次 Git 提交
- **WHEN** 任务提炼或记忆整理执行结束
- **THEN** 两阶段均不提供私有 `finish` 工具。提炼从最终 JSON 读取并校验 `rollout_summary`、`rollout_slug`，两者为空表示无信号。整合 Agent 直接编辑正式记忆仓并通过原生 Bash 执行 Git 提交；宿主观察、校验并记录实际文件及 Git 结果，不使用暂存发布计划或专用 git_commit 工具。没有改动时可以直接结束。
- **AND** 每次整合正常结束后，宿主检查正式仓物理与结构卫生（含仓库干净、根目录有符合长度上限的常规 `MEMORY.md`、一级子目录符合角色规范、库中只保留受支持的 Markdown 页面且仓内相对 `.md` 链接经安全解码后指向真实存在的页面并放行合法外部协议与应用内 `/tasks/`、`/im/v1/` 路由、全局模式主体［含 PA 与 `work_mode === "global"` 独立专家］的 `MEMORY.md` 包含唯一合规四档「主动性与介入偏好」章节且未引用 `proactivity-signals.md`、`knowledge/proactivity-signals.md` 仅在全局模式主体记忆库允许存在且以顶层列表项表达待观察信号并满足长度与条数上限、本批变更内容与 Git 版本一致且来源仍获准）；同一整合 Agent 收到可修复的问题并继续修复，全部通过后才记录成功并推进对应来源与已整合的任务上下文去重标识。
- **AND** 模型失败、取消、输出结构错误、文件核对失败或仓库状态无法确认时不推进对应进度。最终状态依据宿主回执。
- **AND** 即使没有新增来源，正式仓的问题（含未提交改动、不受支持文件及缺失或超长的 `MEMORY.md`）也能触发整合；存量尚未补齐「主动性与介入偏好」章节的正常 `MEMORY.md` 不在无新增来源时单独触发空整合。仅来源资格变更或仓内已有页面出现新的有效 Git 提交，不触发全库逐页验证。

#### Scenario: 按模型容量联合安排材料
- **WHEN** Dreaming 对积压交流和任务经历选材
- **THEN** 两阶段各自以实际模型声明上下文的 70% 为首轮完整输入估算上限，并保留输出容量；系统提示、工具、记忆入口与来源说明计入首轮请求；入选的轨迹与摘要正文计入预算，并为固定输入保留容量。默认不再固定 24K；显式材料上限仍可缩小批次，模型容量未知时如实不可用。
- **AND** Global 连续原文和对应截止时间内的任务摘要共享预算，装不下的完整摘要在继续推进下一段 Global 前补批处理；正式仓干净且核对成功后才推进实际已纳入的来源/摘要版本，未来材料、失败与取消不被误标完成。

#### Scenario: 连续批次和独立进度
- **WHEN** Global 积压超出一批预算，或任务提炼成功而整理失败
- **THEN** 成功保存后推进对应 Global 范围及已整合摘要版本，正常情况下继续本次冻结目标，无 Dreaming 专属累计时长/步数限制；真实失败终止本次并保留已保存进度，后续运行根据实际正式工作区保留已保存的变更，并按当时最新上界重新冻结，旧轮次清单不成为准入条件；已提炼但未整合且版本匹配的有效摘要可复用。
- **AND** Global 未读交流因预算延后而不丢弃；不把窗口、LLM step 或每次 child 唤起当作独立记忆事项，不向模型要求逐 step 覆盖清单。
- **AND** 业务任务未完成或执行失败仍可总结经历，无信号正常结束；真实提炼故障停止本次并重试，不承诺永久故障时仍绕过推进。旧批次不提前纳入未来 child 结果，当前对话采用较新纠正，后续批次再持久化；来源资格变更使正在处理的旧 generation 批次失效，实时 IM 补查受当前权限限制；已经记录的执行轨迹不按会话来源删改。

### Requirement: Dreaming 原始依据回查与自身上下文恢复互不混淆

即使持有旧批次的摘要，也不能通过 source_history 回看工作 worker 或其后代。

#### Scenario: 核实业务原文与缺口
- **WHEN** 后台整理需要核实摘要或交流省略的条件
- **THEN** 可按需查找、分页读取获准来源当前或旧窗口的持久原文，保留实际作者、时间、原始定位和未完成范围；执行会话范围与本批时间边界始终生效；来源 generation 变化中止旧批次，实时 IM 补查另执行当前权限。
- **AND** 缺失、实时 IM 访问撤销、越界或未完整读取如实呈现，不以无关记录替代，不因此推进增量处理位置。

#### Scenario: 维护执行自己换窗
- **WHEN** Dreaming 自身发生上下文换窗并继续整理
- **THEN** 用 history 恢复维护会话自身，用 source_history 核实获准业务来源；两种工具名称、描述及范围明确不同，共用历史查询能力，原普通会话恢复行为保持。
- **AND** 维护笔记和历史不是新增用户经历；恢复不得重复已完成应用或复活当前已失效的依据。

#### Scenario: IM 只读补查
- **WHEN** 整理者围绕本轮相关人物、事项或来源补读获准 IM 上下文
- **THEN** 复用 conversations 的只读 info/read/search，按当前主体资格和本批允许历史范围返回实际消息及来源；未具备该读取能力时如实说明。
- **AND** 不消费 Inbox 或改变未读状态，不发送或变更群聊，不推进 Global/child 处理进度；重复消息去重，未来或无法证明历史版本的内容不当作本批证据。

### Requirement: Agent Context SHALL 保留完整信息并区分稳定指导与本轮输入

#### Scenario: 首次处理请求与能力更新
- WHEN PA 或普通 Agent 首次处理请求，或有效环境／Skill 选择发生变化
- THEN 模型在决策前获得有效身份、边界、环境和可用 Skill 入口，环境／能力信息与触发本轮的消息可区分且保留来源，不因顺序改变获得真人授权资格。
- AND Nano 自有固定指导和动态行动提示使用英文；用户自定义指导、任务原文与历史消息保留，Feature 关闭和工具选择继续遵循现有契约。

#### Scenario: 去重与按需读取
- WHEN 同义指导被合并或详情改为按需读取
- THEN 独有事实、权限约束、来源语义和必要行动规则仍在消费时可获得，详情有可发现且有权限的入口；普通输入和内部对象重建不重复追加无变化信息。
- AND 新 PA 使用更新后的默认指导，既有已保存自定义指导不自动回填。

### Requirement: 用户删除 Schedule 后 SHALL 通知所属 Agent

#### Scenario: 用户删除独立或 Task 关联的 Schedule
- **WHEN** 用户通过设置页成功删除一个 Schedule
- **THEN** 所属 Agent 获得明确的 Schedule 删除 reminder，包含可识别标题、唯一 ID 及删除事实；即使没有关联 Task 也要通知
- **AND** 若该 Schedule 曾被某个 `waiting` Task 选填绑定，任务详情查询如实反映该关联定时器已失效，系统不再为此另行派发自动修复催促唤醒

#### Scenario: 重试、恢复和停止边界
- **WHEN** 删除结果或通知投递在重试／重启后恢复，或 Agent 当前处于停止／禁用边界
- **THEN** 仅确认成功后表述删除，尚未消费的通知可恢复，同一删除不重复呈现已消费提醒；通知不解除停止、恢复 `paused` 或增加行动权限

### Requirement: 产品身份与关键记忆具有明确来源

#### Scenario: 产品身份随当前配置提供
- **WHEN** 根 Agent 或内部执行者开始/恢复工作或在配置更新后开始下一轮
- **THEN** 获得真实产品名称及 Agent ID，内部执行者明确所属主体；执行窗口导航不将会话 ID 称为名称。

#### Scenario: 一页关键记忆及详细目录
- **WHEN** 有效 MEMORY.md 进入请求
- **THEN** 它直接提供一页关键记忆，明确完整文件路径及正文边界；详细记忆在固定主体目录按需查找，日常不常驻备份/缺工具导航。

### Requirement: Dreaming 使用自己的受限维护能力

#### Scenario: 自动维护独立于前台工具选择
- **WHEN** 前台未开放维护或写入工具而自动整理其他条件成立
- **THEN** 后台按自身工具与权限运行，不暗中开启前台能力；关闭、来源资格、路径边界和真实保存回执照常生效。

### Requirement: 工作指导与维护结果使用实际消费者接口

#### Scenario: 来源和交付规则
- **WHEN** 工作 Agent 消费消息和公开发送结果
- **THEN** 来源指导使用真实消息字段及工具调用语义，公开交付以实际 sent 结果为准；审批器私有记录标签不进入工作指导。

#### Scenario: 记忆维护状态
- **WHEN** Agent 查询记忆整理状态
- **THEN** 返回有界积压、实际阻塞、保存及版本记录事实，不返回内部调度游标、去重集合或要求模型操作宿主版本计数器；状态查询不推进整理进度。

#### Scenario: 仅本轮例外
- **WHEN** 用户明确限定更正只用于本轮
- **THEN** 本轮遵守新要求，不将旧记忆登记为长期停用或永久删除；Dreaming 保留该情境范围。

### Requirement: 子执行上下文服从原生执行方式

#### Scenario: 普通子 Agent
- **WHEN** Global、PA 或 SingleThread 的普通内部子执行接到委派
- **THEN** Global／PA 一级采用 DSH 工作基础上下文与完整事项职责；其普通二级只采用 DSH 原生子 agent 上下文和父级子任务，不注入额外 Nano 身份或一级职责。
- **AND** SingleThread 普通子执行保留明确内部身份与可调用工具；普通子会话均不复制父 Persona 的公开交付职责，产品权限按真实身份在宿主执行。

#### Scenario: fork 子 Agent
- **WHEN** fork 子执行开始或恢复
- **THEN** 系统提示与工具定义保持实际父级的有效工作配置一致，在历史后追加任务/回传边界，继承前缀保持可复用；父级可以是主会话或一级执行者，不能把一级 fork 重新解释为根职责。
- **AND** 宿主权限验证不因工具可见而放宽，原生深度与返回语义保持。

### Requirement: Dreaming 只获得有消费用途的上下文
#### Scenario: 提炼和整合
- **WHEN** Dreaming 组装首次输入或读取来源恢复结果
- **THEN** 保留证据定位、操作与恢复需要的信息，不暴露后台运行/周期/来源版本及原始边界字段；经过筛选的材料不宣称是完整轨迹。

### Requirement: 临时能力检查不污染或阻塞持久执行

#### Scenario: 读取与校验临时能力
- **WHEN** 节点为设置候选、提示词预览或配置校验执行临时能力检查
- **THEN** 继续使用对应可信配置与 Workspace 的真实能力来源；临时 Session 不写入持久聊天 home
- **AND** 成功、失败和取消后释放临时执行资源；异常退出的专属临时资源可在下次节点启动回收

#### Scenario: POSIX 父检查器退出
- **WHEN** 启动临时能力检查的父进程退出，检查进程仍在独立进程组内
- **THEN** 即使插件阻塞主事件循环，也终止该检查进程组，无需启动新检查器；持久执行和其他检查不受影响

#### Scenario: 检查卡住或并发超限
- **WHEN** 临时检查超过 deadline、取消或达到并发预算
- **THEN** 调用有界失败，已有聊天和其他 Agent 执行进程不因该检查而重启；释放后允许新检查成功
- **AND** 保存使用新检查验证真实候选，不以陈旧展示缓存扩大工具或 Skill 权限

### Requirement: Global 的一级执行者获得独立工作能力，二级沿用原生子 agent

以下原生工具及子角色装配规则适用于 DSH 框架。外部 worker 使用本机 CLI 的账号、默认模型和原生 helper，消费委派内容与角色指引，只通过原 Global 对外沟通。

#### Scenario: 主会话工具选择不缩减完整事项执行能力
- **GIVEN** Global／PA 主会话的工具选择满足其日常和协调需要
- **WHEN** 主会话把完整事项交给一级 subagent
- **THEN** 一级以 DSH 默认工作能力为基础执行，可使用原生 fork、子 agent 及内部通信，不因主会话未勾选普通工作工具而失去这些能力。
- **AND** 主会话自身仍按其有效选择执行；一级工作能力不反向开启主会话未选择的工具，也不恢复运行时未装载的能力。

#### Scenario: 二级无额外产品身份
- **WHEN** 一级创建普通二级 subagent
- **THEN** 二级使用 DSH 原生子 agent 上下文与父级交办的子目标，不额外注入 Nano 身份或完整事项负责者职责，不自动复制父级历史。
- **AND** fork 继续使用原生父上下文继承，不因该规则裁改其前缀；各级来源、审批、深度、workspace 与宿主产品权限限制仍有效，用户沟通逐级经过 Global。

#### Scenario: 更新与恢复保持角色边界
- **WHEN** 修改主会话工具选择，或恢复已有一级／二级会话
- **THEN** 按该层职责恢复实际工作能力与上下文，原执行者身份和已有工作保留；主会话 fork 开关不撤销一级的原生 fork 能力。
- **AND** 共享 Feature、Skill 与扩展的选择、撤回和权限继续生效；不将其他特定范围的子任务自动升级为完整工作执行者。

#### Scenario: 按消费者角色加载指导
- **WHEN** 装配普通 Global、PA 及其内部执行者的模型请求
- **THEN** 主人身份、participant／observer 和代表主人等 PA 专属说明只给 PA 根或适用的 PA 一级；普通 Global 及其一级不携带它们，普通二级继续不注入 Nano 指导。
- **AND** 普通 Global 的 Inbox 只声明 check／read；review 和 message_id 仅声明给主 PA，实际权限检查仍由宿主执行。通用 pa_agent_id 来源归属仍适用于与 PA 的平等协作。
- **AND** 一级只获得委派来源的最小授权边界和准备交互产物后回传父级的说明，不复制主会话的 Inbox／聊天交互操作流程；详细 UI 用法按需加载。Heartbeat 协议仅由已启用 Feature 向主会话提供，不进入内部执行者。 历史恢复不产生新授权的通用提醒由上下文组件在换窗时提供，主会话和一级不重复常驻注入。 Cron 也不追加通用的定时授权／交付常驻段，沿用原生提醒与各 Schedule 工具的操作说明。 Skill 常驻仅提示修正已验证错漏、提议保存可靠可复用方法及不固化一次性细节／临时故障／未验证变通方案；编写细则按需加载 skill-creator。
- **AND** PA 的记忆修改指引按当前已生效的记忆模式选择，仅提供该模式的操作要求；模式切换后的新上下文不继续携带另一模式分支，来源策略及即时停止使用的要求保持。

### Requirement: 主会话 fork 默认关闭，可按现有工具规则开启

#### Scenario: 新建和无显式工具选择
- **WHEN** 新建 Global、PA 或 SingleThread 主 Agent，或主会话配置没有显式工具名单
- **THEN** subagent_fork 默认不启用，仍可在现有工具目录发现并选择；普通 subagent 和 Global 固定基础能力不因此关闭。
- **AND** 此主会话默认值不套用到 Global／PA 一级执行者的 DSH 工作工具。

#### Scenario: 显式选择与撤回
- **WHEN** 用户选中或取消主会话 fork 并保存
- **THEN** 采用现有工具配置及生效规则，模型可调用能力和预览与有效设置一致；开启只增加原生工具，不增加专门身份提示、清理流程或新开关。
- **AND** Goal 三工具仍各自选择、默认关闭，不因启用 fork 而启用 Goal 或注入 Goal 专属指导。

#### Scenario: 保留已有选择
- **WHEN** 已保存工具名单的 Agent 升级或恢复
- **THEN** 名单保持，显式启用的 fork 仍可用，不按新默认值覆盖已有选择；原生返回和继承语义保持。


### Requirement: exit_plan_mode 默认关闭并保留显式选择

#### Scenario: 新建、未配置与手动选择
- **WHEN** 新建 Global、PA 或 SingleThread 主 Agent，或配置没有显式工具名单
- **THEN** `exit_plan_mode` 默认不启用，仍在现有工具目录可手动选择；默认值、能力预览、实际下发和执行限制一致。
- **AND** 手动开启或关闭沿用现有工具规则，不增加 Plan 模式入口、额外提示词或委派职责；内部执行者原有用户交互工具限制不变。

#### Scenario: 已有显式选择不改写
- **WHEN** 加载、更新或恢复已有显式工具名单
- **THEN** 保留其 `exit_plan_mode` 选择；新默认值不覆盖已保存的开启或关闭，不迁移历史配置。

### Requirement: 用户确认的角色约定独立于正式记忆

#### Scenario: 用主 Agent 的完整角色背景选择记忆
- **WHEN** Dreaming 开始一批长期记忆整合
- **THEN** 使用主 Agent 当前组装出的产品身份、Global／PA 系统角色定义，以及已确认 ROLE，理解该 Agent 的长期工作、服务对象、协作方式和职责；据此选择未来可能需要的信息、确定重点并组织记忆。
- **AND** 系统角色定义复用主 Agent 的现有提示段落，不另写一套副本；ROLE 未设置时仍提供系统角色背景。
- **AND** 这些背景在每批开始时固定，计入输入预算，并可随原始整合输入恢复；它们描述记忆所属的主 Agent，不使 Dreaming 接管聊天、派工或其他业务行动。经历中的事实、条件和结论仍须以原始证据为据，不将角色定义复制为记忆。


#### Scenario: 尚无约定
- **WHEN** 使用文档记忆的 PA 或独立 Agent 尚无用户确认的约定
- **THEN** 主 Agent 在与确认人的私聊中邀请建立一项有用的长期约定。PA 从主人的背景、目标或困扰了解长期帮助方式；独立 Agent 与绑定管理者讨论职责、结果和分工。每次只澄清一个关键问题，已有足够信息就拟稿。用户有当前任务或选择稍后时先处理当前意图，不反复追问，也不向普通联系人请求定义职责。
- **AND** 临时任务和未获同意的建议不写入角色约定。
- **AND** 主 Agent 可用时加载内置 `nano-role-agreement`。遇到宽泛目标，围绕一个真实情境逐步澄清长期工作选择。已有足够明确的约定时可直接拟稿。

#### Scenario: 首次确认或修改约定
- **WHEN** 首次对齐，或用户要求调整、主 Agent 识别到调整需要并向 PA 主人或独立 Agent 的绑定管理者提出修改建议，确认人在实际提议所在交流中明确同意拟写入的文本，且普通文件工具保存成功
- **THEN** 主 Agent 保存到所属工作区的 `.nanoassistant/ROLE.md`，后续主 Agent 请求及新开始的 Dreaming 整合消费同一份已保存约定。
- **AND** 主 Agent 的当前角色提示用 `<role_content>` 展示 Markdown 原文。主动询问的提示只在尚未设置时注入。
- **AND** Dreaming 只将其作为组织记忆的角色背景，权限与事实来源保持各自依据。角色约定可由管理者直接维护，也可由主 Agent 在对话确认后更新。

#### Scenario: 未确认或未保存
- **WHEN** 适用的用户尚未确认该提议，或确认后文件工具不可用、拒绝或保存失败
- **THEN** 主 Agent 与 Dreaming 继续使用原约定或占位状态。确认后保存失败时，主 Agent 如实告知用户未保存。

#### Scenario: 已有角色文件超限或读取失败
- **WHEN** 主 Agent 组装请求时发现所属工作区的角色文件超过 2,000 个 UTF-16 码元或读取失败
- **THEN** 主 Agent 在继续当前工作前先检查 `.nanoassistant/ROLE.md`，当轮通过可用的私聊向有权维护的用户报告检查结果及恢复办法。无法完成检查时也说明原因。没有私下送达路径时，在之后能私下联系维护者时报告。
- **AND** 能完整读取超限文件时，主 Agent 主动拟出保留原意且符合长度上限的 Markdown，与维护者在私聊核对。维护者明确确认拟写文本后，主 Agent 保存并回读确认可用，再报告修复成功。 读取工具无法取得完整原文时，先私下向维护者补齐缺失原文。
- **AND** 异常正文不进入常驻角色背景。仅确认未设置时主动询问长期角色，已保存文件的变更仍须用户确认。

#### Scenario: 管理者直接保存角色约定
- **WHEN** 管理者通过配置页成功保存新的角色约定或清空约定
- **THEN** 后续主 Agent 请求和新开始的 Dreaming 整合使用工作区同一份最新角色文件，清空后采用未设置状态。
- **AND** 当前整合批次继续使用其已有快照，权限与事实来源各自维持原有依据。

### Requirement: 全局模式主动筹划 Feature 与任务图依赖联动

`proactive_planning`（主动筹划）面向所有全局工作模式（`work_mode === "global"`，含个人助手 PA 与普通全局数字员工）的运行特性提供并默认开启；单会话模式（`work_mode === "single_thread"`）Agent 不暴露、不默认启用也不受该特性依赖约束，且缺省默认不在未提交配置的持久快照中改写存量配置指纹。

#### Scenario: 工作模式隔离、依赖联动与存量指纹兼容
- **WHEN** 用户创建全局模式 Agent（PA 或普通全局数字员工）、升级已有全局模式 Agent、在配置中切换其 `proactive_planning` 特性并保存，或创建与编辑单会话模式 Agent
- **THEN** 满足 `task_graph` 能力前提的全局模式 Agent 在有效特性层默认启用 `proactive_planning` 并联动要求 `task_graph` 特性与工具；未显式写入 `proactive_planning` 键的存量配置保持原持久配置指纹不变，若存量配置已显式关闭 `task_graph` 或工具白名单不含 `task_graph` 则有效 `proactive_planning` 自动降级视为关闭而不阻断启动或无关编辑；单会话模式 Agent 的候选能力、新建提交与编辑保存均不包含 `proactive_planning`，关闭 `task_graph` 或 `cron_scheduling` 不受其阻断
- **AND** 关闭任一全局模式 Agent 的 `proactive_planning` 后立即清理待执行队列并取消纯主动唤醒轮次（`proactive_review` 与 `proactive_nightly`），停止后续自动静默记账与提议立卡，保留已有目标图、正式记忆、长期角色约定、明确交办任务的推进以及显式设置的 Cron/Heartbeat 安排；重新开启后按最新状态恢复

### Requirement: apply_patch 作为默认文件修改能力提供且保持工作区与白名单边界

宿主默认启用原生 `apply_patch` 文件补丁能力，与 `write`、`edit` 一同组成标准文件修改工具集，同时不开放模型侧切换会话目录的 `working_directory` 工具、原生 `AgentTeam` 共享任务板工具及单次实验性 `subagent_oar`。

#### Scenario: 新建与未固定白名单的助手及一级原生执行者默认可用
- **WHEN** IM 查询节点可选工具，或新建 Agent、运行未显式配置 `tool_allowlist` 的 Agent 及 Global/PA 一级原生工作 subagent
- **THEN** `apply_patch` 出现在可选工具目录中且 `default_on` 为 `true`，上述执行会话默认可调用 `apply_patch` 在单次补丁中完成多文件新增、更新、删除或移动
- **AND** 任意会话均不暴露 `working_directory`、原生团队任务板工具与 `subagent_oar`，会话工作区身份保持创建时绑定的目录且不吸入工作区外指令文件

#### Scenario: 既有显式工具白名单不被静默扩宽
- **GIVEN** 存量 Agent 已持久化非空或空的显式 `tool_allowlist` 且未包含 `apply_patch`
- **WHEN** 节点升级运行时后创建或恢复该 Agent 的主会话
- **THEN** 主会话仍严格按已保存的 `tool_allowlist` 提供静态业务工具，用户可在设置页按需勾选或取消 `apply_patch`

### Requirement: 网页搜索在缺少独立搜索源时脱敏复用官方 DeepSeek 凭据

#### Scenario: 显式搜索源优先级保持不变
- **GIVEN** 节点已配置 `DSH_WEB_SEARCH_PROVIDER`、`SEARXNG_URL` 或 `BRAVE_API_KEY`
- **WHEN** Agent 调用 `web_search`
- **THEN** 按显式指定提供方、`searxng`、`brave` 的既有优先级执行搜索

#### Scenario: 未配独立搜索源时安全复用官方 DeepSeek 凭据且不外发对话原文
- **GIVEN** 节点未设置 `DSH_WEB_SEARCH_PROVIDER`、`SEARXNG_URL` 与 `BRAVE_API_KEY`，但存在可用的官方 DeepSeek 凭据（含原生 DeepSeek 凭据或指向官方 DeepSeek API 域名的节点模型服务密钥）
- **WHEN** Agent 调用 `web_search`
- **THEN** 通过原生 DeepSeek 搜索返回带来源链接的结果摘要，发往搜索端点的请求仅携带查询参数而不附带用户原始对话消息文本
- **AND** 指向非官方第三方代理的模型密钥不被转发至官方 DeepSeek 搜索端点

#### Scenario: 无专用搜索与官方凭据时回退公共搜索
- **GIVEN** 节点未配置上述独立搜索源，也无可用的官方 DeepSeek 凭据
- **WHEN** Agent 调用 `web_search`
- **THEN** 回退使用 `duckduckgo`，遇到网络失败或人机验证拦截时返回明确可读的原因说明

### Requirement: 长对话与模型切换具备工具输出修剪、超限图片卸载及小窗预压缩保护

#### Scenario: 超大工具输出与超限历史图片自动收敛后继续对话
- **GIVEN** 会话中累计了超过单条阈值的历史工具输出，或历史图片数量触发当前模型的图片预算上限
- **WHEN** 用户继续发起新请求，并在后续要求核对早先轮次的完整输出
- **THEN** 运行时在不额外消耗摘要模型调用的情况下裁剪过长旧工具输出，或在超限时将最早历史图片替换为带附件标识的只读占位后重试完成回复
- **AND** 已被换窗归档的早期完整记录仍可通过当前会话的 `history` 工具分页回查

#### Scenario: 切换至较小上下文窗口模型时平稳过渡
- **GIVEN** 既有会话已积累多轮历史，用户将模型切换为上下文窗口更小的目标模型
- **WHEN** 用户在该会话发送下一条消息
- **THEN** 运行时在请求发出前按目标模型窗口完成必要的上下文换窗或预压缩，不因沿用旧模型窗口估算而直接超限失败，既有备用模型链与粘性规则保持不变
