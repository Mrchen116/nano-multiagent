# gateway Agent Capabilities Specification (delta for feat-635)

## ADDED Requirements

### Requirement: DSH Goal 工具 SHALL 默认不选并可逐项配置

#### Scenario: 现有及新建 Agent
- **WHEN** Agent 使用默认工具集合
- **THEN** create_goal、get_goal、update_goal 默认不选，无 Goal 工具时不注入其专属引导；显式白名单包含的 Goal 工具按用户选择生效，不另设 Feature 总开关。
- **AND** Task 持续执行独立生效，不转换、双写或同步两套状态，不进行历史 Goal 迁移或清理。

#### Scenario: 用户显式开启和关闭
- **WHEN** 用户在配置页工具列表选择或取消某个 Goal 工具
- **THEN** 仅该工具的选择改变，不联动其他 Goal 工具；沿用普通工具配置的生效规则及原生语义与授权，不额外改变 Goal 生命周期，不影响 Task 的执行责任。

## MODIFIED Requirements

### Requirement: Agent 运行能力更新在下一轮新回复整体生效

Gateway 对 model、PromptSlots、skills、tools 与内核 features 使用同一份有效运行配置。公开 Agent profile 提供的提示词文本仅为可见的 Custom Instructions：它作为产品规则后的 `PromptSlots` 追加段出现，不能覆盖公共 PA 提示词，也不走 Kernel 内部完整 override。配置保存不打断正在进行的回复，也不重建既有聊天；某聊天下一次开始新回复时采用最新完整配置并延续自己的历史。排队期间连续保存多次只采用真正开始时的最终配置。可调用工具的取消选择先立即收缩，后续 dispatch 不再允许该工具，但不中断已开始的调用；新增工具等待当前执行空闲后的完整配置应用。收缩从当前有效选择计算，未配置白名单时默认未选的工具不会因候选名单包含而提前启用。

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
