# gateway Agent Capabilities Specification (delta for bugfix-507)

> 对齐 canonical: `docs/specs/gateway/agent-capabilities.md`。

## MODIFIED Requirements

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
