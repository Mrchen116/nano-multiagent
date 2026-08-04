# gateway (personal_assistant) - Agent Capabilities Specification

> 对齐: bugfix-471
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

agent 模型选择、工具白名单、上下文窗口和内置 skills 自举的 Gateway 契约。

## Requirements

### Requirement: Agent 选定的模型在每次新回复开始时生效

Gateway 在每次新回复开始时按 Agent 当前 `default_model` 选择模型；未选模型时回退产品层全局默认。既有聊天改模型不创建空会话，模型与同代 prompt、skills、tools、features 一起生效并保留历史。已经开始的整轮及其采纳的插话继续使用启动时模型。

#### Scenario: Agent 选定模型后对话用该模型
- **GIVEN** 某 Agent 配置模型 B
- **WHEN** 用户与该 Agent 开始一轮新交流
- **THEN** 该轮使用 B

#### Scenario: 改模型后旧会话继续聊用新模型且保留历史
- **GIVEN** 某 Agent 曾用模型 A 形成历史会话
- **WHEN** 配置改为模型 B 后回到该历史会话发新消息
- **THEN** 新回复使用 B，并仍能引用模型 A 代次的聊天历史

#### Scenario: 正在进行的回复不在中途换模型
- **GIVEN** Agent 正在用模型 A 回复
- **WHEN** 配置改为模型 B，且用户插话被纳入当前回复
- **THEN** 当前整轮仍使用 A，下一轮新回复才使用 B

#### Scenario: Agent 未选模型时用产品层默认兜底
- **GIVEN** Agent 的 `default_model` 为空
- **WHEN** 与其开始一轮新交流
- **THEN** 使用 Gateway 产品默认模型正常回复

#### Scenario: heartbeat 复用专用会话时采用当前完整配置
- **GIVEN** heartbeat 专用会话已用配置 A 形成历史
- **WHEN** Agent 更新为配置 B 后开始下一 heartbeat tick
- **THEN** tick 使用 B 的 model、prompt、skills、tools 与 features，并保留该专用会话历史

#### Scenario: cron 新会话使用 Agent 当前完整配置
- **WHEN** cron 为某 Agent 创建会话并开始执行
- **THEN** 新会话使用创建时该 Agent 当前的完整配置；未选模型时使用产品默认兜底

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。

#### Scenario: 增加工具后继续既有聊天
- **GIVEN** Agent 因未配置某工具而无法完成既有聊天中的任务
- **WHEN** 用户增加该工具后在同一聊天继续
- **THEN** 新回复可使用该工具并理解此前的问题与回复

#### Scenario: 删除工具后保留既成工具历史
- **GIVEN** 既有聊天历史中已有某工具调用及结果
- **WHEN** 用户删除该工具后继续聊天
- **THEN** 新回复不能再执行该工具，但能理解历史调用与结果

#### Scenario: 修改 prompt、skills 或 features 后继续历史
- **GIVEN** 某聊天已形成历史
- **WHEN** 用户修改会影响后续模型请求的 prompt、skills 或 features 后发起新交流
- **THEN** 新回复体现完整的新运行配置，并仍能引用修改前历史

#### Scenario: 连续保存多次只采用最终运行配置
- **GIVEN** 某聊天空闲或消息仍在等待处理
- **WHEN** 用户连续成功保存多份 Agent 运行配置
- **THEN** 下一轮新回复使用真正开始时最新的完整配置，不依次重演中间版本

#### Scenario: 配置替换失败不使用混合配置回复
- **WHEN** Gateway 无法把最新完整运行配置持久应用到既有会话
- **THEN** 当前消息以真实失败结束，不以新 model 搭配旧 prompt 或 tools 的混合配置运行

### Requirement: 动态新建 agent 的模型选择持久化

#### Scenario: IM 动态新建 agent 选模型后重启保留
- **GIVEN** 用户在 IM 新建 agent 并选模型 B
- **WHEN** Gateway 重启
- **THEN** 该 agent 仍在、其模型仍是 B,继续用 B 对话

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

### Requirement: PA 内置 skill 启动自举

Gateway 随包提供 PA 内置 skills 与当前产品定义的完整 Lark skill bundle。启动时只把
运行态全局 skill root 中缺失的目录安装进去，不覆盖用户已有文件。绑定 Feishu
channel 的 agent 能发现完整 bundle，并默认沿用 Gateway 所在机器已登录的 Lark 用户
身份；只有各 skill 的既有规则明确要求时才使用其他身份。

#### Scenario: 新安装的飞书 agent 发现完整 Lark bundle
- **GIVEN** 用户本机尚未安装任一同名的 Lark skill
- **WHEN** Gateway 启动并为 agent 启用飞书 channel
- **THEN** agent 的 capabilities 和会话可发现产品随包的完整 Lark skill bundle
- **AND** 用户可从飞书要求该 agent 操作文档、云盘、表格、日程、任务、审批、邮件、知识库、会议或其他由 bundle 覆盖的 Lark 资源

#### Scenario: 显式 skill allowlist 的飞书 agent 获得完整 bundle
- **GIVEN** 飞书绑定 agent 的本地 skills allowlist 非空且缺少一个或多个 Lark skill
- **WHEN** Gateway 启动静态 `config.channels` 中的该飞书 channel，或调和 IM 托管的该飞书 channel
- **THEN** Gateway 保留已有条目并将完整 Lark skill bundle 加入 allowlist
- **AND** 重复调和不会重复写入或重复列出 bundle skill

#### Scenario: 空 skill allowlist 保持默认发现语义
- **GIVEN** 飞书绑定 agent 的本地 skills allowlist 为空
- **WHEN** Gateway 启动或调和该飞书 channel
- **THEN** Gateway 不将完整 bundle 物化写入该 allowlist
- **AND** 该 agent 仍按默认全局 skill discovery 发现 Lark bundle

#### Scenario: 静态 Feishu agent 的 IM profile ingress 保留完整 bundle
- **GIVEN** Gateway 的静态 `config.channels` 绑定了一个 skills allowlist 非空的 Feishu agent
- **AND** IM 中该 agent 已存在一个尚未包含完整 Lark skill bundle 的 mirror profile
- **WHEN** Gateway 连接、重连 IM，或接收该 agent 的 `config.sync` profile 更新
- **THEN** Gateway 将完整 Lark skill bundle 补齐到该 agent 的显式 profile 后再应用到本地运行态
- **AND** 该 agent 后续会话仍可发现完整 Lark skill bundle

#### Scenario: 用户已有同名内置 skill 时不覆盖
- **GIVEN** 运行态全局 skill root 中已存在 `<skill-name>/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** 不覆盖该目录中的用户文件

#### Scenario: 用户明确请求独立 Lark 事件监听
- **WHEN** 用户要求飞书绑定 agent 监听并处理一种 Lark 事件
- **THEN** agent 可使用 bundle 中的 Lark event 能力按其既有身份、授权和生命周期规则建立独立监听
- **AND** 该监听不取代 Gateway 对普通飞书对话的消息接收和回复

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
