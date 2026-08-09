# gateway (personal_assistant) - Agent Capabilities Specification (delta for feat-519)

## MODIFIED Requirements

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

## ADDED Requirements

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
