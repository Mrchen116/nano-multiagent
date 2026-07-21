# gateway Agent Capabilities Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: Agent 运行能力更新在既有聊天的下一新 run 整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。配置保存不打断 active run，也不重建既有聊天会话；某聊天下一次开始新 run 时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开跑时的最终配置。

#### Scenario: 增加工具后继续既有聊天
- **GIVEN** Agent 因未配置某工具而无法完成既有聊天中的任务
- **WHEN** 用户增加该工具后在同一聊天继续
- **THEN** 新 run 可使用该工具并理解此前的问题与回复

#### Scenario: 删除工具后保留既成工具历史
- **GIVEN** 既有聊天历史中已有某工具调用及结果
- **WHEN** 用户删除该工具后继续聊天
- **THEN** 新 run 不能再执行该工具，但能理解历史调用与结果

#### Scenario: 修改 prompt、skills 或 features 后继续历史
- **GIVEN** 某聊天已形成历史
- **WHEN** 用户修改会改变后续模型请求的 prompt、skills 或 features 后发起新 run
- **THEN** 新 run 体现完整的新运行配置，并仍能引用修改前历史

#### Scenario: 连续保存多次只采用最终运行配置
- **GIVEN** 某聊天空闲或消息仍在等待新 run admission
- **WHEN** 用户连续成功保存多份 Agent 运行配置
- **THEN** 下一新 run 使用 admission 时最新的完整配置，不依次重演中间版本

#### Scenario: 配置替换失败不提交混合配置 run
- **WHEN** Gateway 无法把最新完整运行配置持久应用到既有会话
- **THEN** 当前消息以真实失败结束，不以新 model 搭配旧 prompt/tools 的混合配置运行

## MODIFIED Requirements

### Requirement: agent 选定的模型在对话中生效，按新 run admission 时的当前配置路由

Gateway 在每个新 run admission 时按 Agent 当前 `default_model` 选择模型；未选模型时回退产品层全局默认。既有聊天改模型不创建空会话，模型与同代 prompt、skills、tools、features 一起生效并保留历史。active run 与纳入该 run 的插话继续使用启动时模型。

#### Scenario: agent 选定模型后对话用该模型
- **GIVEN** 某 Agent 配置模型 B
- **WHEN** 用户与该 Agent 开始新 run
- **THEN** 该 run 使用 B

#### Scenario: 改模型后旧会话继续聊用新模型且保留历史
- **GIVEN** 某 Agent 曾用模型 A 形成历史会话
- **WHEN** 配置改为模型 B 后回到该历史会话发新消息
- **THEN** 新 run 使用 B，并仍能引用模型 A 代次的对话历史

#### Scenario: active run 不在中途换模型
- **GIVEN** Agent 正在用模型 A 执行一轮
- **WHEN** 配置改为模型 B，且用户插话被纳入当前轮
- **THEN** 当前整轮仍使用 A，下一新 run 才使用 B

#### Scenario: agent 未选模型时用产品层默认兜底
- **GIVEN** Agent 的 `default_model` 为空
- **WHEN** 与其开始新 run
- **THEN** 使用 Gateway 产品默认模型正常回复

#### Scenario: heartbeat 与 cron 新 run 使用 Agent 当前模型
- **WHEN** heartbeat 或 cron 为某 Agent 开始新 run
- **THEN** 使用 admission 时该 Agent 当前模型或产品默认兜底

## REMOVED Requirements

N/A.
