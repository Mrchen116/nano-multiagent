# gateway (personal_assistant) - Agent Capabilities Specification

> 对齐: feat-519
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

agent 模型选择、工具白名单、Skill 选择与发现、上下文窗口和内置 skills 自举的 Gateway 契约。

## Requirements

### Requirement: Agent 选定的模型在每次新回复开始时生效

Gateway 在每次新回复开始时按 Agent 当前 `default_model` 选择模型；未选模型时回退产品层全局默认。这个结果是 Agent 的有效模型。有效模型声明可调推理能力时，Gateway 为该轮使用 Agent 已保存的 `reasoning_effort`；未保存时使用该模型配置的推荐 default。`default_model` 为空时也可以保存属于平台默认模型的 `reasoning_effort`，且不因此把 Agent 固定到该模型。既有聊天改模型或推理强度不创建空会话，模型与同代 prompt、skills、tools、features 一起生效并保留历史。已经开始的整轮及其采纳的插话继续使用启动时的完整配置。

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
- **AND** Agent 的 `default_model` 仍为空，不持久化该模型名

#### Scenario: heartbeat 复用专用会话时采用当前完整配置
- **GIVEN** heartbeat 专用会话已用配置 A 形成历史
- **WHEN** Agent 更新为配置 B 后开始下一 heartbeat tick
- **THEN** tick 使用 B 的 model、prompt、skills、tools 与 features，并保留该专用会话历史

#### Scenario: cron 新会话使用 Agent 当前完整配置
- **WHEN** cron 为某 Agent 创建会话并开始执行
- **THEN** 新会话使用创建时该 Agent 当前的完整配置；未选模型时使用产品默认兜底

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。公开 Agent profile 提供的提示词文本仅为可见的 Custom Instructions：它作为产品规则后的 `PromptSlots` 追加段出现，不能覆盖公共 PA 提示词，也不走 Kernel 内部完整 override。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。

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

Gateway 对 `agent.create` 与 `agent.config.apply` 接收稳定 operation id、候选 fingerprint 与协商后的 fingerprint schema。在任何 workspace、local config 或 live publication 变更前，Gateway 先持久化不含 secret 的 `prepared` intent；再以 expected-previous 保护 local config 写入，并将结果变为 terminal applied/rejected receipt。IM 可在 ACK 丢失或重连后查询 `agent.config.operation.status`。同一个 operation 与同一 schema/fingerprint 可安全重试，operation id 不得重用到不同候选。旧端未声明 schema 时按升级前的 v1 canonical payload 处理；新版 schema 可表达 Skill selection mode，且不得把 v1 无法表达的意图静默降级。

#### Scenario: applied operation 重试不重复写入或发布
- **GIVEN** Gateway 已为某 operation id 持久化同一 schema 与候选 fingerprint 的 applied receipt
- **WHEN** IM 因超时再次发送相同 create 或 apply operation
- **THEN** Gateway 返回同一 canonical applied result，不第二次创建 workspace 或重复发布该配置

#### Scenario: operation status 使丢失 ACK 可恢复
- **GIVEN** Gateway 已落盘某 operation 的 applied 或 rejected receipt，但结果 frame 未送达 IM
- **WHEN** IM 查询该 operation id 的 status
- **THEN** Gateway 返回已持久化的终态和 canonical payload 或 rejected reason

#### Scenario: Gateway 在任意 config operation 持久边界崩溃后能恢复
- **GIVEN** Gateway 已持久化一个 prepared intent
- **WHEN** 它在 workspace 初始化前、workspace 初始化后、local config 写入后或 live publication 后但 terminal receipt 前崩溃
- **THEN** 同一 operation 的 retry 或 status 以同一 schema 下的 expected-previous/candidate fingerprint 重新协调该 intent
- **AND** create 不创建第二个 workspace，apply 不第二次持久写入或发布

#### Scenario: operation id 不得重用到不同候选
- **GIVEN** Gateway 已见过某 operation id
- **WHEN** 调用方以不同 schema 或候选 fingerprint 重试该 operation id
- **THEN** Gateway 稳定拒绝，不改变本地 Agent 配置或既有 receipt

#### Scenario: 新旧 IM 与 Gateway 滚动升级不误解释 Skill 选择
- **GIVEN** IM 与 Gateway 正在滚动升级，任一端仍只支持升级前的 config fingerprint
- **WHEN** IM create/apply 一个旧协议可无损表达的 Agent 配置，或新版 Gateway 恢复旧版 prepared receipt
- **THEN** operation 按旧 schema 幂等完成，不因新增字段产生 fingerprint 冲突
- **WHEN** 新 IM 要向旧 Gateway 写入旧 schema 无法表达的 Skill selection 意图
- **THEN** IM 在写入前返回明确的 `gateway_upgrade_required`，不把选择静默改成另一种语义

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

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时 Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单的 Agent 会话拒绝一切工具调用
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用工具
- **THEN** 工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill_view`,session 不启用 `skill_view`

#### Scenario: 启用 cron 能力使 cron 工具进入该 Agent 工具集
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="cron"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `cron` 工具；停用 cron 能力则 `cron` 工具随之移出

#### Scenario: Gateway 上报能力时标记 skill_view 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill_view`
- **AND** `skill_view` 的 `default_on` 为 true

### Requirement: PA 产品说明书按需回答产品问题

PA 随当前安装版本提供可选的产品说明书 skill，覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、外部渠道、启动和常见故障处理。入口经 `skill_view` 按需加载，再由默认启用的 `read` 只读取当前问题所需的随包专题资料；普通任务不因其启用而加载。用户显式关闭 `read` 后，产品不保证详细手册可读。coding CLI、Kernel 内部和开发流程不属于该手册。

#### Scenario: 在 PA 对话入口询问产品问题

- **GIVEN** 当前 Agent 已启用产品说明书、`skill_view` 与 `read`
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

### Requirement: PA Agent 从有序的工作区与全局 Claude/Codex 兼容根发现 Skill

PA 为某 Agent 解析可选 Skill、prompt preview、下一轮新回复和 `skill_view` 时，按该 Agent 的真实 Workspace 依次搜索 `<workspace>/.nanoassistant/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`，再依次搜索 `~/.nanoassistant/skills/`、`~/.claude/skills/`、`~/.codex/skills/`。同名 Skill 只采用最先命中的版本；缺失或空的可选兼容目录不影响其他来源。

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
- **WHEN** Gateway 解析 capabilities、开始新回复或处理 `skill_view`
- **THEN** 操作正常完成
- **AND** 其他有效 roots 中的 Skill 仍可使用

#### Scenario: 新建页只取得全局 Skill candidates
- **GIVEN** IM 正在为尚无 canonical Workspace 的新 Agent 查询 node capabilities，且 Gateway repo root 中存在工作区 Skill
- **WHEN** Gateway 返回该 node 的创建页 Skill candidates
- **THEN** 返回的候选只来自 PA 的共享全局 roots
- **AND** repo root 或其他未绑定 Workspace 中的 Skill 不作为新 Agent 可选择项

### Requirement: PA Agent 配置区分默认发现与显式空 Skill 选择

PA Agent 的 Skill 配置必须区分“按当前可发现集合默认使用”和“显式 allowlist”。显式 allowlist 可为空；保存空 allowlist 后的下一轮新回复不得回退为默认发现。升级前未携带该选择意图的历史空 Skill 配置保持其既有默认发现行为，除非用户以新版配置界面显式保存选择。

#### Scenario: 用户显式清空全部 Skill 后下一轮不再发现 Skill
- **GIVEN** 某 Agent 在新版配置页中将其 Skill allowlist 显式保存为空
- **WHEN** 用户在既有聊天发送下一条消息
- **THEN** 新回复不获得任何可见 Skill
- **AND** 正在进行的旧回复不在中途改变

#### Scenario: 旧空配置升级后保持历史行为
- **GIVEN** 某历史 Agent profile 只有空 Skill names，且未表达显式选择意图
- **WHEN** Gateway 升级并开始该 Agent 的下一轮新回复
- **THEN** 该轮保持升级前的默认 Skill discovery 行为
- **AND** Gateway 不静默把该 Agent 改写为显式空 allowlist

#### Scenario: 自动 Skill 写回保留 selection mode
- **GIVEN** Gateway 因托管 channel 调和或 `skill_created` 事件需要更新某 Agent 的 Skill names
- **WHEN** Gateway 通过 IM config operation 或本地 YAML 持久化更新
- **THEN** 更新显式携带并保留该 Agent 的 `skills_selection_mode`，不因只修改 names 就退回长度推断

#### Scenario: 成功创建 Skill 后按当前 mode 变为可用
- **GIVEN** Agent 成功创建一个 agent-scope 或 global-scope Skill
- **WHEN** Gateway 处理该 `skill_created` 事件
- **THEN** default-discovery Agent 保持 default 且由 discovery 自然看到新 Skill
- **AND** explicit-allowlist Agent 保持 explicit 并将新 name 加入 allowlist，包括原 allowlist 为空的情形

#### Scenario: 显式空 allowlist 不提供 Skill 蒸馏
- **GIVEN** Agent 的 mode 为 `explicit_allowlist` 且 names 为空，或其显式 names 不含会话蒸馏 Skill
- **WHEN** 用户请求生成或蒸馏 Skill
- **THEN** Gateway 在生成 prompt 前返回明确的 distiller unavailable 结果
- **AND** 不因磁盘上可发现该 Skill 而按 default discovery 放行

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
