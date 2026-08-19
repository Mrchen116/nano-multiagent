# gateway - Agent Capabilities Specification — feat-541 delta

> 落点: `docs/specs/gateway/agent-capabilities.md`
> 投影自: feat-541 spec.md 验收标准 + design.md 决策 1–6（含 2026-08-19 Q10/Q11 试用对齐）

## ADDED Requirements

### Requirement: 主模型因可用性失败时按有序备用链换模型，本轮继续回复

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

## MODIFIED Requirements

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

## REMOVED Requirements
