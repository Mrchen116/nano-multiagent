# gateway (personal_assistant) - Agent Capabilities Specification

> 对齐: feat-676
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

网页模型接入与真实验证、agent 模型选择、工具白名单、Skill 选择与发现、上下文窗口和内置 skills 自举的 Gateway 契约。

## Requirements

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


### Requirement: 主模型因可用性失败时按有序备用链换模型，本轮继续回复

两种模式均保持下述候选链、可重试条件、持久 Session 粘性与配置重置规则。以下按聊天隔离、失败气泡、切换说明自动出站和 `/new` 重置的 Scenario 适用于 `single_thread`；global 的粘性归主 Session，改模型配置可重置，失败/切换记录归工作轮次，正式聊天仍显式发言，`/new` 不改变其状态。

Gateway 在每次新回复开始时先组链：有该 Kernel session 的备用粘性则第一次就用粘性模型，否则以 Agent 保存的 `default_model`（空则产品默认）为链头，再加上有序 `model_fallbacks`。本轮候选因欠费/额度、过载/5xx、超时、限流或认证失败而无法完成时，用户先看到带该模型名的失败提示；若该 run 没有产出非失败气泡的真实正文或工具时间线，Gateway 按列表顺序改用下一个候选并继续本轮，用户不必再发消息。明确不可重试的错误（如无效密钥 / 401）很快投下该提示，不对同一模型空转；网络抖动与限流才按既有预算同模型重试。上下文太长不换模型。没配备用或整条链耗尽时，每个失败候选留下带模型名的失败提示，不改用其它 Agent 的模型，也不把未配置的平台默认塞进备用链。自动切换不写回保存的 `default_model`。切到备用时使用该备用模型自己的默认推理档，不沿用主模型保存的强度，也不沿用会话 `/effort`。

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

### Requirement: Gateway 可统一选择自动工具权限分类模型

运维者可在 PA 顶层 LLM 配置中选择一个已注册模型,供当前 Gateway 内所有 Agent 与运行来源
的自动工具权限分类统一使用。该字段可省略,修改随 Gateway 重启生效。

#### Scenario: 不同 Agent 共用统一分类模型
- **GIVEN** 两个 Agent 分别使用模型 A 和 B,Gateway 配置选择已注册模型 C 作为自动工具权限分类模型
- **WHEN** 两个 Agent 从任一 PA 运行来源触发自动分类
- **THEN** 两次分类都使用 C
- **AND** 两个 Agent 的正常回复与工具后续运行仍分别使用 A 和 B

#### Scenario: 省略字段时保持按 Agent 复用
- **GIVEN** Gateway 配置未选择自动工具权限分类模型,两个 Agent 分别使用模型 A 和 B
- **WHEN** 两个 Agent 分别触发自动分类
- **THEN** 分类分别使用 A 和 B,Gateway 正常运行

#### Scenario: 配置未注册模型时拒绝启动
- **GIVEN** Gateway 配置选择的自动工具权限分类模型不在 `llm.providers` 中
- **WHEN** 运维者启动 Gateway
- **THEN** Gateway 拒绝启动并明确指出该字段的模型无效

#### Scenario: 专用分类模型失败时不改用 Agent 模型
- **GIVEN** Agent 使用模型 A,Gateway 选择模型 C 进行自动工具权限分类
- **WHEN** C 的分类调用在同一模型的既有重试后仍超时、失败或返回不可解析结果
- **THEN** Gateway 不改用 A 或其他模型重新分类
- **AND** 有人值守时进入既有显式审批,无人值守时遵守既有 unattended fallback

#### Scenario: 修改选择后重启才生效
- **GIVEN** 当前 Gateway 以模型 C 进行自动工具权限分类
- **WHEN** 运维者把配置文件中的选择改为 D,但尚未重启 Gateway
- **THEN** 当前进程继续使用 C
- **WHEN** 运维者重启 Gateway
- **THEN** 后续自动分类使用 D

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

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

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
- **THEN** `inbox`、`conversations`、`send_message`、`subagent` 作为固定基础工具，不可关闭
- **AND** Personal Global 另外固定 personal_sources；其他工具继续按默认选择及依赖规则配置，single_thread 和子 Agent 不继承 Global 根会话固定项

### Requirement: 自进化技能自动启用不打断既有会话提示词

#### Scenario: 后台新增技能保持当前上下文缓存前缀
- **GIVEN** Agent 的历史后台自进化已成功创建技能
- **WHEN** Gateway 保存该技能且原生发现刷新，既有会话开始下一轮
- **THEN** 技能可由工具读取，但不因该自动增量重建提示词目录或生成配置分界线
- **AND** 新会话及压缩等既有重建边界可吸收新目录；该保护以当前进程内会话快照为界，重启不保留旧快照

#### Scenario: 手动取消及重新启用技能仍立即生效
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

### Requirement: Auto默认采用Codex规则且可配置为CC或DSH规则

#### Scenario: 默认审核规则
- **WHEN** 用户未选择其他Auto规则
- **THEN** 工具权限审核采用 Codex 规则，保留可信来源、拒绝计数、人工审批和无人值守分流；已有显式 CC 或 DSH 配置保持有效。

#### Scenario: CC与DSH审核使用去重后的指令和来源明确的历史
- **GIVEN** 当前使用 CC 或 DSH 审核规则
- **WHEN** Agent 在含运行快照、已加载 Skill 或多轮消息的会话中请求执行受审工具
- **THEN** 审核将已加载的项目指令放在独立区，按原生指令更新顺序解释替换与移除；同一指令正文只保留最后一次出现，不重复序列化其 source 元数据。
- **AND** 历史沿用原生有效上下文，省略运行快照和 Skill 正文；保留用户原话及简短来源、工具调用和执行状态，最后一条是完整待审核动作。全局 Agent 私稿不视为已向用户提出的提议。
- **AND** Inbox 结果单独保留宿主提供的发送者、目标、消息标识、分页/部分内容及已有回复关系；只有本进程真实观察的消息具备 live 来源，恢复或继承后失去该来源的内容只作为历史背景。不会根据正文自称身份或补造回复关系。
- **AND** send_message 的结果保留实际状态和投递标识；只有 sent 证明提议已发送，accepted、held_for_revalidation、unknown 或错误不能替代送达。短确认必须结合原发送者与真实聊天理解。
- **AND** 通过 run_code 执行的 Inbox/发送子调用按公开执行事件恢复对应结果；已被原生压缩移出有效历史的调用不会因此重新进入审核。

#### Scenario: CC与DSH审核请求预计超过独立模型窗口
- **GIVEN** 当前使用 CC 或 DSH 审核规则
- **WHEN** 完整审核输入的原生估算值加本阶段输出预留超过审核模型声明的窗口
- **THEN** 不提交该次模型请求，记录为审核不可用并走既有人值守/无人值守分流；不计为安全拒绝，不裁掉授权或待审参数，不切换审核模型。
- **AND** 估算不是供应商精确分词；供应商实际返回的超限或其它错误仍按原失败路径处理。

#### Scenario: 子 Agent 统一采用委派权限
- **WHEN** 普通 subagent、Workflow child 或后台知识维护子任务执行工具
- **THEN** 使用原生 `approval=never`；Auto 放行才可执行，不放行时返回阻断原因交回父 Agent，不发起子 Agent人工审批卡，也不借无人值守 fallback 扩权。
- **AND** 既有工具范围、Auto 规则和父级指令来源继续生效；父级补充指令后的重试仍需重新判定。

#### Scenario: 配置切换规则
- **WHEN** 运维者选择DSH默认规则并重启节点完成生效
- **THEN** 后续工具权限判定使用DSH规则；独立审核模型选择仍按既有契约，不能改用另一条并行审批链或绕开产品来源规则。
- **AND** 配置生效前已发出的审批仍对应原请求，迟答不复活取消调用。

#### Scenario: 规则切换不改变审核模型失败处理
- **GIVEN** 节点配置了独立审核模型
- **WHEN** 该模型在已有重试后仍失败或无有效判定
- **THEN** 不自动换回执行Agent模型复审；有人值守/无人值守分别走既有分流。

#### Scenario: 逐Agent选择与节点继承
- **WHEN** 用户为 Agent 明确选择 CC 或 Codex，或清空选择回到节点继承
- **THEN** 明确选择优先于节点规则；空值沿用节点既有 Codex/CC/DSH 规则，节点未配置时采用 Codex，不改变 Auto 开关、工具权限、审核模型或其他 Agent。
- **AND** Codex 的证据保留和预算恢复遵循“Codex Auto 按风险与授权进行独立、有界的审查”，不沿用 CC/DSH 的不裁剪超窗处理。

#### Scenario: 下一轮切换保持进行中请求
- **WHEN** 新策略经所属节点成功应用
- **THEN** 既有聊天的下一轮新回复使用该策略并保留历史；正在执行的整轮与已发出的人工审批仍保持原策略和原动作关联。


### Requirement: CC Auto 对普通工作区文件编辑直接放行

#### Scenario: 普通 Write/Edit
- **GIVEN** CC Auto 已开启，工具自身约束允许
- **WHEN** Agent 在实际工作区创建或编辑普通文件
- **THEN** 无需分类模型审查即可执行，工具的读取与并发修改约束仍有效。

#### Scenario: 越界与受保护路径
- **WHEN** 路径在工作区外、真实目标越界、目标受保护或不能确认归属
- **THEN** 不获得工作区文件免审；目录外或符号链接不会绕过权限约束。

### Requirement: 普通工具审批遵守当前有效执行上下文

#### Scenario: PA 长期跨聊天历史
- **GIVEN** PA 的消息库含长期、跨聊天历史，当前有效执行上下文和待审动作能够容纳在审核窗口内
- **WHEN** PA 请求执行需自动审核的普通工具动作
- **THEN** 审核不另行读取全库授权或聊天历史，不因库内记录规模使该动作审核输入膨胀。
- **AND** 真实身份、Inbox 原话和实际发送回执按所选策略投影；用户选择的规则、模型和工具约束继续生效。

#### Scenario: 主会话压缩后延续
- **WHEN** 主会话压缩后继续发起工具动作
- **THEN** 审核依据当前有效历史及必要宿主事实，不从消息库重放已被压缩移除的原文。
- **AND** CC 保持既有省略普通工具正文和超窗分流；Codex 按固定策略保留与选择证据，并明确遗漏；证据不足不伪造授权。

#### Scenario: PA 消息安全保持独立
- **WHEN** PA 接收外部直接请求或向非主人私聊受众发送内容
- **THEN** 继续执行各自的独立消息检查；普通工具审批结果不替代它们，也不因此附加其全量消息证据。

### Requirement: Codex Auto 按风险与授权进行独立、有界的审查

#### Scenario: 现场事实与可信来源
- **WHEN** Agent 请求审查操作
- **THEN** 审查结合精确动作、用户授权、必要的历史工具结果与约束；可只读检查本地事实，但不能修改用户状态、联网发送或另发人工审批。
- **AND** 工具正文、私稿和历史恢复内容不伪造新授权；真实 Inbox、用户和已送达回复保留其来源语义。原始人类授权在委派和后续轮次中仍按原范围有效；父级不能创造人类权限或覆盖人类限制，限制按实际对象、数据与副作用解释。

#### Scenario: 连续、并发与预算恢复
- **WHEN** 连续或同时发起审查，或历史/配置/预算发生变化
- **THEN** 审查上下文可复用并按必要变化恢复，每个结果只对应它自己的动作；明确标记缺失证据，不将旧判定作为新授权。

#### Scenario: 判定与失败
- **WHEN** 审查完成或失败
- **THEN** 有效判定按既有策略的风险和授权规则决定放行/阻断；缺少单独明确授权本身不构成低／中风险默认放行的例外，拒绝需说明适用策略及具体禁止的影响。无有效判定进入既有失败分流，不冒充 allow，不计为安全拒绝。
- **AND** 审计区分所选策略、快速放行、模型判定与不可用，并记录可获得的耗时和模型用量；缓存命中不作保证。

### Requirement: Nano Auto 的指定查询与会话计划记录不依赖分类审核

#### Scenario: 查询已有工作与记录当前会话计划
- **GIVEN** Agent 使用已开启的 Nano Auto，且工具自身权限与作用域允许调用
- **WHEN** 用户要求查看已有 Skill 列表、任务图、提醒及其执行历史、Workflow 定义或运行记录、当前 goal，或者记录当前会话计划
- **THEN** `skill_manage list`、`task_graph list/get`、`schedule_list`、`schedule_history`、`workflow list/read`、`get_goal` 与 `todo_write` 不请求分类模型，并按原工具语义执行
- **AND** 工具可用性、确定性拒绝、作用域、ACL 与参数/执行约束保持有效；记录计划不会自动启动工作

#### Scenario: 相邻动作继续审核
- **GIVEN** Agent 使用已开启的 Nano Auto，且没有其它既有显式放行
- **WHEN** Agent 发起上述工具的其它写入、调度、编排或 goal 生命周期动作，或者执行 Bash/公开消息发送
- **THEN** 不因该工具具有查询功能而获得本批豁免，继续既有审批路径
- **AND** 缺席 action 的 Workflow 默认启动不属于查询

#### Scenario: Auto 关闭与 DSH 规则保持原路径
- **WHEN** 运维者关闭 Auto，或者选择 DSH 规则
- **THEN** 上述调用不继承本批新增豁免；Auto 关闭时保持原人工审批路径，DSH 规则下保持原审核路径

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

Agent 启用 `plugin_manager` 后，可以在可信配置确定的 workspace 创建标准 DSH bundle（包括工具、提示词和其他适用 workspace scope 的插件贡献），安装、启用、停用和移除。新增且不与既有工具名冲突的 workspace 工具自动并入该 Agent 的有效集合，不要求人工修改白名单。静态工具选择和禁用保持；关闭管理能力或显式空工具集不自动获得这些工具。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

#### Scenario: 安装后既有聊天立即使用
- **WHEN** Agent 成功安装并启用 workspace 工具
- **THEN** 同 workspace 既有及新聊天可使用它，不需重启；其他 workspace 不可发现或执行

#### Scenario: 失败不声称已启用
- **WHEN** 包安装或实际加载失败
- **THEN** Agent 收到失败状态和真实诊断；包管理成功不代替执行可用证据

#### Scenario: 重启和撤销
- **WHEN** 节点重启或 Agent 停用/移除已安装 bundle
- **THEN** 重启保留持久选择，停用/移除后后续调用不可执行对应工具

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

#### Scenario: 不支持交互的渠道
- **WHEN** Agent 向其他客户端或外部 channel 交付包含交互的内容
- **THEN** 用户得到可读文字摘要，原始界面源码不作为回复泄露。

### Requirement: Intelligent UI Feature 可配置

#### Scenario: 默认启用和显式关闭
- Agent 配置页 Features 提供 `intelligent_ui`，默认勾选，缺失值按开启解释。
- 合法取消勾选并保存后，运行时移除交互生成指导，按共享依赖规则默认取消关联工具/Skill；有效 send_message 的显式合法 interactive 参数仍能发布新卡片，文字交付保留。重新勾选恢复完整依赖及指导。
- 关闭不删除已发布卡片、个人草稿或选择，历史卡片继续按原消息权限读取与提交。

#### Scenario: Feature 关闭但工具独立可用
- **GIVEN** Intelligent UI Feature 关闭，send_message 仍为固定或独立启用
- **WHEN** 普通、Global 或 Personal Agent 使用显式合法 interactive 参数发布
- **THEN** 不因 Feature 关闭而拒绝新卡片，仍执行既有 schema、身份权限、审批和交付检查；不反向恢复额外交互生成指导
- **AND** 不支持交互的渠道保留文字摘要降级，历史卡片权限与提交行为不变

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
- **WHEN** 私聊自然消息有可用的发问时交互背景
- **THEN** Agent根据用户原话判断是否使用，换题可忽略，指代不明时可澄清；背景数据不替代正文、不构成业务授权。

#### Scenario: 群聊不读取私人操作
- **WHEN** 用户在群聊操作卡片后正常发言
- **THEN** 所有Agent均不取得未提交状态；明确提交后按公开消息读取已提交快照。

### Requirement: 所有 Agent 默认使用无摘要换窗并支持显式回退

#### Scenario: 新建与既有 Agent 默认生效
- **WHEN** 新建或升级前已存在的普通、Global、Personal 或子 Agent 开始工作，用户未显式停用该能力
- **THEN** 默认使用无摘要换窗及配套恢复工具，无需逐 workspace 安装或修改业务工具 allowlist
- **AND** 不扩大业务操作权限

#### Scenario: 用户显式停用后重启
- **GIVEN** 用户通过现有 workspace 插件入口停用了该能力
- **WHEN** 节点重启或该 workspace 创建新 Agent
- **THEN** 保持停用并使用原摘要压缩，直至用户重新启用；其他 workspace 的选择不改变

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

本条的静态工具选择规则适用于 `single_thread`。主 Agent 启用 `plugin_manager` 时，不与既有工具名冲突的 workspace 自建工具按本 area 的“Agent 可在 workspace 自助安装原生工具”有限并入有效集合；不扩大业务工具或子任务的数据权限。默认上下文机制启用时，所有 Agent（含子 Agent）固定保留 `notes/history/new_context/get_context_remaining` 四个仅管理当前执行会话的工具；停用机制即撤销其注册。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Feature 关闭不额外否决已选择工具，任务图、记忆、Skill 管理和定时工具均遵守同一规则。工具自己的操作、授权与必要服务保留；Feature 专属指导、主动注入、后台复盘或自动续跑不随单工具启用。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：除上述四个上下文内部工具和 workspace 自建工具的有限增量外，非空时 Agent 静态业务工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有可选业务工具，但启用中的上下文内部工具仍可用**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性启用时，完整 `requires` 中的工具经界面依赖展开已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——业务工具集按配置侧存储的 `tool_allowlist` 兑现；四个上下文内部工具按机制启停，预览、下发和实际执行保持一致。

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
- **GIVEN** single_thread PA agent 已持久化合法非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 的静态业务工具只启用该白名单列出的工具；除四个上下文内部工具外，仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名
- **AND** 若白名单不含 `skill`,session 不启用 `skill`

#### Scenario: 启用 Cron 能力提供允许的原生调度工具
- **GIVEN** 某 Agent 启用了 Cron Feature 并已将其全部依赖工具保存到 `tool_allowlist`
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 schedule_create/list/update/delete/run/history 六项；合法关闭 Cron 后按最终工具选择提供，用户单独重新启用的工具不因 Feature 关闭而拒用

#### Scenario: Gateway 上报能力时标记 skill 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill`
- **AND** `skill` 的 `default_on` 为 true


#### Scenario: Auto 关闭不阻断会话内部上下文管理
- **GIVEN** 当前 Agent 启用了默认上下文机制，自动审批关闭
- **WHEN** 普通、Global、Personal 或子 Agent 保存笔记、恢复历史、查询预算或请求换窗
- **THEN** 仅作用当前执行会话的四工具无需额外审批即可执行，明确的底层拒绝仍保留
- **AND** 其他业务工具继续遵守原审批、选择与发送重验规则；恢复内容不生成新的授权

### Requirement: Feature SHALL 保证完整依赖并与独立工具行为分离

#### Scenario: 开启 Feature 展开完整依赖
- **WHEN** 用户开启 Feature 或创建采用默认 Feature 的 Agent
- **THEN** 交互式回复需要 send_message、skill 和 nano-interactive-ui；Task 需要 task_graph 与 Cron Feature；skill-creator 是固定内置指导，不再属于可选 Feature 或 Skill 名单，其实际操作遵守工具权限；Cron 需要 schedule_create/list/update/delete/run/history；Heartbeat 需要 read。
- **AND** 内置 document 消费不依赖旧 memory 条目工具；主 Agent/普通 child 对正式记忆只读，文件工具不能直接修改正式库。Dreaming 使用自己的受限维护工具集，不暗中开启父业务工具；缺少可运行所需资源须显示不可用，不能假报运行。
- **AND** 默认开启 Task 的初始配置同时开启 Cron；依赖缺失时显式启用动作失败，已关闭 Skill 不冒充可加载。

#### Scenario: 合法关闭与共享依赖
- **WHEN** 用户关闭没有需要者的 Feature
- **THEN** 取消其直接关联资源，仍被其他 Feature 需要或属于基础固定的能力保留；Dreaming 停用不撤销普通文件工具/内置记忆。
- **AND** 不级联关闭依赖 Feature，关闭 Task 后 Cron 保持开启；随后单独打开工具或 Skill 不反向打开 Feature。

#### Scenario: 独立工具不恢复 Feature 行为
- **GIVEN** Feature 关闭而工具仍被合法独立选中
- **WHEN** Agent 调用 task_graph、skill_manage、schedule 工具，或 legacy 模式下可用的 memory
- **THEN** 操作按原授权与业务前置条件执行，不恢复 Feature 额外行为；document 不提供旧 memory 条目工具，Skill 工具不恢复自动 fork。

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

### Requirement: 审核请求 SHALL 使用原审核模型声明的推理能力

#### Scenario: 原模型不支持 low
- **WHEN** 所选审核模型声明可调推理能力
- **THEN** 支持 low 时使用 low，否则使用该模型声明的默认档位或首个支持档位；未声明可调能力时不强设 low。
- **AND** 保留同一审核 provider/model、完整适用证据、判定规则及失败分流，不通过换模型或删证据放行。

### Requirement: 通用交互说明区分本地采用与发送请求

#### Scenario: 普通 Agent、Global 与 PA 生成草稿
- **WHEN** Agent 使用可用交互能力提供可编辑回复
- **THEN** 可以使用通用 ComposeMessage 将当前编辑内容采用到指定聊天输入框，不需要 PA 专属字段或草稿工具；ToAssistant 继续表示向本会话提交请求，不能混淆。
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

### Requirement: 角色化文档记忆可及时消费且不扩大权限

#### Scenario: PA 与独立专家
- **WHEN** 长期 Agent 处理跨聊天相关事项
- **THEN** PA 使用主人相关背景，独立专家按实际人物、项目和专业职责使用知识，内部执行者仍属于原长期主体；不串用不同人的偏好。
- **AND** 当前信息充分时可直接回答，检索不足、部分读取和未知项如实说明；旧记忆、观察和第三方材料不增加业务授权。

#### Scenario: Dreaming 保存与入口滞后
- **WHEN** Dreaming 已保存当前记忆正文但尚未提交 Git 或入口仍旧
- **THEN** 保存后的正文立即可用，后续相关判断重读变化部分，旧入口概括不继续作为当前知识；入口只由 Dreaming 补完，明确区分正文保存、入口同步和版本记录结果。人工在线编辑不作为支持的更新入口。

### Requirement: Dreaming 处理持续历史的合格增量并保持安静

#### Scenario: 跨窗口且主体仍持续工作
- **WHEN** 自动 Dreaming 已开启、到期且存在合格增量
- **THEN** 可整理当前和旧窗口已完整保存的经历，不要求根会话结束、不截断正在进行的模型/工具；无增量不调用模型，资源不足保留积压。
- **AND** 去重重复消息、继承历史与报告，区分观察、自述与实际结果；不消费主 Inbox、不扫描未授权源、不执行业务动作或发布 Skill。

#### Scenario: 失败、冲突、输入分批与重启
- **WHEN** 整理只完成部分材料或部分保存，或保存期间到达新交流/来源撤销
- **THEN** 保留真实成功结果，不恢复已整合的过期结论或已撤销内容；本轮冻结后收到的普通纠正进入后续批次，不冒称已处理；仅确认本批已实际提供给整理者并完成应用的 Global 连续范围及已整合的任务摘要版本；任务摘要的取材省略不冒充完整历史审计，剩余材料可继续，恢复不重复追加同一记录。
- **AND** 已有工作视图显示实际处理范围、变更、延期和未完成结果；普通成功不发聊天通知，模型正常停止不等于全部完成。

#### Scenario: 关闭与手动整理
- **WHEN** 用户关闭 Dreaming 或明确请求手动整理
- **THEN** 关闭阻止自动运行，保留已有记忆读取和当前对话响应，长期记忆暂停自动更新；手动整理仍由唯一 Dreaming 写者执行，可不等自动周期，仍遵守主体停用、权限、输入容量与并发限制。

### Requirement: 旧记忆可备份导入，临时旧模式仅经文件选择

#### Scenario: 升级、导入和回切
- **WHEN** 已有 Agent 升级或用户要求整理旧记忆
- **THEN** 默认采用文档记忆并开启 Dreaming，逐字保留旧备份；收到明确导入请求后才由同一个 Dreaming 把备份整理进角色文档，保留原义与来源，重复执行不产生同义副本。
- **AND** 文件可选 legacy，切换时仅所选机制运行，两库独立保存而不双向自动转换；默认历史处理从启用点开始，不暗中扫描全部旧聊天。

### Requirement: 停止使用和撤销来源不得被后台复活

#### Scenario: 排除已有知识或来源
- **WHEN** 用户明确停止使用知识或来源资格被撤销
- **THEN** 当前知识与入口不继续采用被排除内容，后台从源资格和当前排除范围核对，不能从旧材料重新引入。
- **AND** 前台不能修改正文或解除待核对状态，只有 Dreaming 完成正文清理；关闭自动整理期间仍保持停止采用，对未完成的派生清理如实报告，不把当前文件删除称为清除 Git、备份、原始消息和所有系统副本。

### Requirement: 后台 Skill 自进化暂停，任务中创建能力保留

#### Scenario: 自动 Skill 维护暂停期间
- **WHEN** 任一运行模式积累 Skill 使用记录、达到旧 F3/F4/combined 门槛或节点重启
- **THEN** 不启动后台 Skill fork 或自动归档，不消费待维护证据冒充已完成；保留已有 Skill、使用统计与历史结果。
- **AND** 普通 Agent 按任务需要使用迁移适配的 Codex skill-creator 创建/维护 Skill，仍遵守现有范围、权限和真实操作回执；Dreaming 不发布 Skill。

### Requirement: skill-creator 内置默认可用，无需用户选择

#### Scenario: 新建、已有和旧配置升级
- **WHEN** 普通长期 Agent 开始任务、恢复或升级配置
- **THEN** 固定获得 skill-creator 的发现入口与短创建指导，按需加载全文；旧 skill_creation=false 或 allowlist/denylist 不关闭这一个产品资产，不使旧合法配置无法启动。
- **AND** 其他 Skill 选择和底层工具权限保留；禁用真实操作工具时如实说明限制，Dreaming 不获得创建能力。

### Requirement: Dreaming 按交流与任务经历组织记忆

#### Scenario: Global 原文与第一层任务复盘
- **WHEN** 同一主体的 Global 跨聊天、跨窗口持续交流，第一层子执行开展具体任务
- **THEN** Global 合格交流保留原文、按连续范围分批进入后台整理；第一层子执行形成会话级任务复盘，与已有记忆一起由一个整理者更新同一文档库。
- **AND** 兼顾用户变化、关系与互动反思及任务经验，按 PA/专家现有实体、知识、事项/项目、历史和短入口维护，不新增互相隔离的知识库；更深层结果经所属任务归纳，不独立逐层摘要。

#### Scenario: 旧子会话续做
- **WHEN** 已提炼的子会话继续产生合格历史
- **THEN** 重新从该会话截至本批边界的合格历史按预算选择材料，生成新摘要替换同一会话旧摘要；无更新复用，不生成增量阶段复盘链。
- **AND** 来源与省略清楚，不声称完整重读全部历史；其后无新增 Global 消息也能处理更新。

#### Scenario: fork 继承背景用于理解
- **WHEN** 子任务自身指令或结果依赖继承的父会话条件
- **THEN** 合格继承历史与自身经历一起按现有过滤和输入容量选材，标明背景及原作者、时间、来源；背景曾被整理不代表必须删除，子续做后仍重新提炼并替换摘要。
- **AND** 继承内容不计为 child 新经历，同源引用不算多份独立证据；缺失或未提供的条件保留未知，不新增背景摘要阶段或平行 fork 存储，不突破当前来源资格与允许历史范围。

#### Scenario: 两阶段正常完成后由宿主保存
- **WHEN** 任务提炼或记忆整理执行结束
- **THEN** 两阶段均不提供私有 `finish` 工具；提炼从最终 JSON 读取并校验 `rollout_summary`、`rollout_slug`，两者为空表示无信号；整理在原生正常完成后由宿主核对暂存文件、生成应用计划并保存，无变化也可成功。
- **AND** 模型失败、取消、输出结构错误或文件核对失败不冒充成功，不推进对应进度；正常模型结束仍不等于正式文件已经保存，最终状态依据宿主回执。

#### Scenario: 连续批次和独立进度
- **WHEN** Global 积压超出一批预算，或任务提炼成功而整理失败
- **THEN** 成功保存后推进对应 Global 范围及已整合摘要版本，正常情况下继续本次冻结目标，无 Dreaming 专属累计时长/步数限制；真实失败终止本次并保留已保存进度，后续运行核对应用回执后按当时最新上界重新冻结，旧轮次清单不成为准入条件；已提炼但未整合且版本匹配的有效摘要可复用。
- **AND** Global 未读交流因预算延后而不丢弃；不把窗口、LLM step 或每次 child 唤起当作独立记忆事项，不向模型要求逐 step 覆盖清单。
- **AND** 业务任务未完成或执行失败仍可总结经历，无信号正常结束；真实提炼故障停止本次并重试，不承诺永久故障时仍绕过推进。旧批次不提前纳入未来 child 结果，当前对话采用较新纠正，后续批次再持久化；来源撤销立即限制消费。

### Requirement: Dreaming 原始依据回查与自身上下文恢复互不混淆

#### Scenario: 核实业务原文与缺口
- **WHEN** 后台整理需要核实摘要或交流省略的条件
- **THEN** 可按需查找、分页读取获准来源当前或旧窗口的持久原文，保留实际作者、时间、原始定位和未完成范围；当前来源资格与本批时间边界始终生效。
- **AND** 缺失、撤销、越界或未完整读取如实呈现，不以无关记录替代，不因此推进增量处理位置。

#### Scenario: 维护执行自己换窗
- **WHEN** Dreaming 自身发生上下文换窗并继续整理
- **THEN** 用 history 恢复维护会话自身，用 source_history 核实获准业务来源；两种工具名称、描述及范围明确不同，共用历史查询能力，原普通会话恢复行为保持。
- **AND** 维护笔记和历史不是新增用户经历；恢复不得重复已完成应用或复活当前已失效的依据。

#### Scenario: IM 只读补查
- **WHEN** 整理者围绕本轮相关人物、事项或来源补读获准 IM 上下文
- **THEN** 复用 conversations 的只读 info/read/search，按当前主体资格和本批允许历史范围返回实际消息及来源；未具备该读取能力时如实说明。
- **AND** 不消费 Inbox 或改变未读状态，不发送或变更群聊，不推进 Global/child 处理进度；重复消息去重，未来或无法证明历史版本的内容不当作本批证据。
