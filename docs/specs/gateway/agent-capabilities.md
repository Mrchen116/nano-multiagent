# gateway (personal_assistant) - Agent Capabilities Specification

> 对齐: bugfix-468
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

agent 模型选择、工具白名单、上下文窗口和内置 skills 自举的 Gateway 契约。

## Requirements

### Requirement: agent 选定的模型在对话中生效,按当前配置每轮路由

Gateway 在每个新 run(用户消息、heartbeat、cron 触发)按 agent 当前 `default_model` 选择模型,传给内核
生效;agent 未选模型时回退到 Gateway 配置的产品层全局默认。

#### Scenario: agent 选定模型后对话用该模型
- **GIVEN** 某 agent 配置 `default_model = codex_oauth:gpt-5.5`
- **WHEN** 用户与该 agent 对话
- **THEN** 该轮 LLM 请求用 `codex_oauth:gpt-5.5`(而非全局默认)

#### Scenario: 改模型后旧会话继续聊用新模型
- **GIVEN** 某 agent 曾用模型 A 聊过、存在历史会话
- **WHEN** 在配置页改为模型 B 后回到该历史会话发新消息
- **THEN** 新消息用模型 B

#### Scenario: agent 未选模型时用产品层默认兜底
- **GIVEN** 某 agent 的 `default_model` 为空
- **WHEN** 与其对话
- **THEN** 用 Gateway 配置的全局默认模型正常回复,不报错

#### Scenario: heartbeat/cron 触发的轮次也用 agent 当前模型
- **WHEN** heartbeat 或 cron 为某 agent 触发一轮
- **THEN** 该轮用该 agent 当前 `default_model`(或产品默认兜底)

### Requirement: 动态新建 agent 的模型选择持久化

#### Scenario: IM 动态新建 agent 选模型后重启保留
- **GIVEN** 用户在 IM 新建 agent 并选模型 B
- **WHEN** Gateway 重启
- **THEN** 该 agent 仍在、其模型仍是 B,继续用 B 对话

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时
Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式
为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥
的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如
cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，
Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

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

Gateway 启动时把产品包内置的 PA skills 安装到运行态全局 skill root,只补缺失,不覆盖用户已有文件。

#### Scenario: Gateway 启动时安装缺失的 PA 内置 skill
- **WHEN** Gateway 启动并发现包内 `builtin_skills/<skill-name>/SKILL.md`
- **THEN** 若运行态全局 skill root 中不存在同名 `SKILL.md`,复制整个内置 skill 目录
- **AND** 复制后的 skill 可被 PA agent 的 skill discovery 发现

#### Scenario: 用户已有同名内置 skill 时不覆盖
- **GIVEN** 运行态全局 skill root 中已存在 `<skill-name>/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** 不覆盖该目录中的用户文件

### Requirement: 模型可在配置中声明各自的上下文窗口

运维者可在 Gateway config 的 `llm.providers[].models[]` 条目上为某模型声明 `context_window`（与
`extra_request_body` 同级，可选）。该值随模型配置流入内核，并在用该模型的对话中决定上下文压缩的边界。
未声明 `context_window` 的模型条目按内核默认上限处理；Gateway 回写 config 时保留已声明的
`context_window`，未声明的不写该字段。

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

### Requirement: 内置 skills 启动自举

Gateway 随包携带 PA 产品级内置 skills。启动时，Gateway 将包内内置 skill 目录安装到用户全局 skill root；目标已存在时默认不覆盖用户本地版本。启用飞书 channel 的 agent 必须能发现 `feishu-doc` skill，使用户在飞书中要求云文档操作时，agent 能按该 skill 给出授权和文档操作路径。

#### Scenario: 新安装用户启动后获得 feishu-doc
- **GIVEN** 用户本机没有 `~/.nanoassistant/skills/feishu-doc/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** Gateway 从包内内置资源安装 `feishu-doc` 到用户全局 skill root
- **AND** 后续 capabilities 查询和会话 prompt 均能解析到 `feishu-doc`

#### Scenario: 已存在的用户 skill 不被覆盖
- **GIVEN** 用户本机已存在自定义的 `~/.nanoassistant/skills/feishu-doc/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** Gateway 保留用户已有文件，不以包内版本覆盖

#### Scenario: 飞书绑定 agent 自动启用 feishu-doc
- **GIVEN** Gateway 配置了 `feishu:plato` channel 且 plato agent 的 skills allowlist 未包含 `feishu-doc`
- **WHEN** Gateway 启动
- **THEN** Gateway 将 `feishu-doc` 加入 plato 的本地 skills 配置
- **AND** 用户从飞书向 plato-bot 请求云文档操作时，plato 的会话可见 `feishu-doc`
