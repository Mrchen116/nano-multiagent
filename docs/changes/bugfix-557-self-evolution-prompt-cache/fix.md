# bugfix-557: 自进化新增 Skill 不打断既有会话提示词缓存

## Relations

- Related: feat-349-self-evolving-skills-memory, bugfix-525-self-evolution-output-leak

## 原始报告

用户：“为啥我啥配置没改，突然说改了？”、“当时的skill自进化的设计，就是这样的吗，会破坏缓存”、“我们参考的是hermes的设计对吧，看看hermes的代码”、“改下这个问题”。

## 现象 / 复现

2026-09-15 nano CEO 的 c_ypme696c 会话中，08:03:56 后台创建 skill-discovery-diagnostics；08:04:28 下一轮采用新增技能的运行配置，出现配置边界。模型请求前后 system 唯一差异是新增 Skill 目录条目，下一轮观察到 5.6% 缓存命中。目标：后台产出成功保存、可用于后续会话，不因自进化创建/修改 Skill 而主动改写既有会话提示词、生成配置边界。新会话应发现新技能；既有明确手动配置更新仍按原规则生效。压缩等既有提示词重建边界可吸收新内容。覆盖普通显式技能选择及默认发现路径，不更改生产配置或部署。

## 根因

feat-349 原始要求为后台静默保存并回显，且 review 复用父提示词缓存。参考 Hermes 本地 e20ff352b 中 skill_manage 只清技能目录构建缓存；主会话 _cached_system_prompt 保持冻结，直到压缩/新会话等重建边界。Nano 的 handle_skill_created 自动将技能加入 Agent desired 配置，下一轮运行投影将此变化视作需要替换整个 session runtime 的配置变更，重建提示词。根因是未区分自进化产出的能力可用性与当前会话冻结的提示词快照。不能通过关闭自动沉淀、禁止新技能生效或隐藏分界线掩盖问题。实现需要核对内核提示词重建和 Gateway 自动配置同步的实际接口，以最小方式保留上述不变量。

## 修复

- 内核以 ConversationState 冻结技能目录快照，压缩/正常 reconfigure/载荷重建时更新；技能读取继续使用当前文件与 allowlist。默认发现改为使用当前 workspace resolver，确保新会话与压缩后的目录包含新技能。
- SDK `reconfigure_session(..., defer_skill_prompt_refresh=True)` 只允许纯技能扩充；持久更新 allowlist，但保留当前目录与 memory 快照。同时修改模型、工具、权限或其他字段会被拒绝。
- Gateway catalog 记录自动新增技能；聊天与后台 admission 对纯自动技能扩充延后目录更新且不发送配置 boundary。手动移除清除自动来源，重新启用仍走显式更新。
- 将技能同步串行锁与配置操作锁分开：原先自动 PATCH 等待 IM 回调配置操作，而回调等待同一锁，真实链路会超时。创建技能更新的来源在正在进行的 PATCH 对应配置首次发布时携带，失败后不留下 pending 来源。
- 保持现有进程内快照边界，不增加持久 schema；进程重启/会话载荷重建允许吸收当前目录。


## 验证

- 原始 src 基线 f15feb87d + 新真实 E2E 断言：1 failed（21.46s），原会话下一轮 system 仅新增技能目录。
- 修复后隔离 IM + Gateway + 受控 OpenAI HTTP 服务：1 passed（21.05s），覆盖后台真实 skill_manage 创建/自动启用、原会话 system 字节不变/无 boundary、新会话目录包含技能、手动取消/再启用立即更新并各产生 boundary。
- SDK/Gateway/contract 相关回归：200 passed；新增失败 PATCH 后手动更新覆盖单独纳入 config-sync 参数化回归。
- 完整定位、命令、覆盖与限制见 [M1-fix/progress.md](M1-fix/progress.md)。未修改生产配置、部署或重启生产服务。
