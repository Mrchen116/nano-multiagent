# IM Agents and Nodes Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: Agent 配置保存与聊天实际采用状态分离

IM 持久化 Agent 配置并用 `profile_version` 做乐观锁；保存成功表示新的期望配置可供 Gateway 同步，不表示所有既有聊天已经采用。名称、头像、描述等展示字段不会被解释为模型上下文缓存边界。运行配置真正应用到某个聊天时，由 Gateway 单独上报实际采用事实。

#### Scenario: 运行配置成功保存后由各聊天惰性采用
- **GIVEN** 同一 Agent 有多个既有聊天
- **WHEN** 用户成功保存会改变后续模型请求的配置
- **THEN** IM 持久化新配置并通知 Gateway
- **AND** 不在保存时向所有休眠聊天批量插入配置边界

#### Scenario: 纯展示字段保存不产生运行边界
- **WHEN** 用户只修改 Agent 名称、头像或描述并保存
- **THEN** 配置读取反映新展示信息，但既有聊天不出现上下文缓存边界

#### Scenario: 保存失败不产生实际采用事实
- **WHEN** Agent 配置因版本冲突、校验或网络错误未保存
- **THEN** IM 不产生配置已采用的聊天边界，既有配置保持权威

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天的下一新回复采用

前端经 `/im/v1/agents/*` 读写 Agent 展示与运行配置，配置以 `profile_version` 乐观锁持久化。展示字段更新立即反映在 UI；model、system/custom prompt、skills、tools 与运行 features 等配置由 Gateway 在每个既有聊天下一次新回复开始时采用，并保持该聊天历史。已在进行的整轮不切换。IM 自有字段在 live 快照合并时仍以持久值为准。

#### Scenario: 读配置暴露稳定字段集
- **WHEN** 前端读取 Agent 配置
- **THEN** 响应保留既有稳定配置字段及 profile version

#### Scenario: PATCH 持久化运行配置并保持乐观锁
- **WHEN** 前端带当前 profile version 保存配置
- **THEN** 成功响应与随后读取反映持久值；过期 version 被拒且不覆盖新值

#### Scenario: 既有聊天下一新回复采用成功保存的运行配置
- **GIVEN** 某聊天已形成历史且当前没有新回复在开始
- **WHEN** 用户成功更新 Agent 运行配置后回到该聊天发消息
- **THEN** 下一新回复使用更新配置并延续原聊天历史

#### Scenario: live 合并保留 IM 自有字段
- **GIVEN** 持久 profile 含 IM 自有运行字段
- **WHEN** IM 拉取并合并 Gateway live snapshot
- **THEN** live payload 省略这些字段时不把持久值清空

## REMOVED Requirements

N/A.
