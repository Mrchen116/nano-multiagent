# kernel (agent) - Skills Specification

> 对齐: feat-530
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

Skill 发现、按名读取、管理、生命周期、使用统计与能力预览一致性的对外契约。

## Requirements

### Requirement: Skill 自动发现走 prompt 列表,显式调用改写为自然语言

存在可见 skill 时,内核在 system prompt 注入 `<available_skills>` 列表(名称 + 描述 + 路径),模型按需用 `skill_view(name=...)` 加载 SKILL.md 全文;消费者输入的 `/skill:<name>` 被改写为自然语言指令;命令前可选的一个或多个 `[..]` 标注段被原样保留(内核不解析其内容),多 part 输入中改写作用于命令所在的那个 part。

#### Scenario: 显式 skill 命令被改写
- **WHEN** 消费者输入 `/skill:doc`(或带参数 `/skill:doc fix heading spacing`)
- **THEN** 内核将其改写为 `Use the "doc" skill for this request.`(带参数时追加 `User input:` 段), 然后走常规推理,不在改写阶段直接展开 SKILL.md 原文

#### Scenario: 命令前带一个或多个标注段时改写保留全部标注
- **WHEN** 消费者提交 `[Alice] /skill:doc fix spacing`,或提交 `[Feishu Tue 2026-08-11 15:53 CST] [Alice] /skill:doc fix spacing`
- **THEN** 内核改写命令并原样保留前面的全部标注段,带参数时追加 `User input:` 段;内核不解析标注内容

#### Scenario: 多 part 输入中命令所在 part 被改写
- **WHEN** 消费者提交多 part 输入(如群聊缓冲上下文,或文本命令 + 末尾图片),其中一个 text part 是 `/skill:doc`
- **THEN** 改写作用于该命令 part(不因命令不在首行或末位而漏改),其余 part 原样保留

#### Scenario: skill_view 启用时 available skills guidance 引导按名加载
- **GIVEN** 消费者创建的 session 启用了 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** 每个 skill 仍包含 name / description / location,且 guidance 指示 agent 通过 `skill_view`按名字加载 skill 内容

#### Scenario: skill_view 关闭时不渲染 skill_view 调用 guidance
- **GIVEN** 消费者创建的 session 未启用 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** guidance 不指示 agent 调用 `skill_view`

### Requirement: skill_view 工具按名字加载 skill 并记录可审计使用

消费者可在会话工具集中启用 `skill_view`。agent 调用该工具后,内核按当前会话可见 skill 搜索根解析同名 skill,返回命中的内容与位置,并把成功读取记录为 skill 使用统计。

#### Scenario: agent 调用 skill_view 读取 skill
- **WHEN** agent 调用 `skill_view(name="some-skill")`
- **THEN** 返回 `{success: true, name, content, location}`,其中 `content` 为命中的 SKILL.md 全文

#### Scenario: skill_view 调用不存在的 skill
- **WHEN** agent 调用 `skill_view(name="nonexistent")`
- **THEN** 返回 `{success: false, error: "..."}`,不抛异常

#### Scenario: skill_view 同名 skill 按候选优先级读取
- **GIVEN** 当前会话可见集合中存在多个同名 skill
- **WHEN** agent 调用 `skill_view(name="same-name")`
- **THEN** 内核按 `<available_skills>` / `/skill:` 候选使用的既有 search root 优先级读取第一项
- **AND** 返回结果中的 `location` 指向实际命中的 SKILL.md

#### Scenario: skill_view 调用记录使用统计
- **WHEN** agent 调用 `skill_view(name="some-skill")` 成功
- **THEN** 该 skill 的 `use_count` 增加、`last_used_at` 更新,且当前 session 引用记录到使用统计

#### Scenario: 重放同一次 skill_view 不重复计数
- **GIVEN** 同一次 `skill_view` 成功调用已经以 `{session_id, tool_call_id}` 记录过
- **WHEN** 系统因恢复或事件重放再次处理该调用
- **THEN** 使用次数不再增加,session 引用不重复追加

#### Scenario: skill_view 调用注册 compaction 存活
- **WHEN** agent 在 session 中调用 `skill_view` 成功
- **THEN** 该 skill 的 name/location 被注册到 invoked skills 列表,compaction 后以内核 reminder 重新注入当前 SKILL.md 内容

### Requirement: skill_manage 工具 action 枚举保持写入与列表语义

`skill_manage` 是写入/维护 skill 的工具,不承担读取全文的 view action;读取全文由 `skill_view` 承担。

#### Scenario: skill_manage 不含 view action
- **WHEN** 消费者查看 `skill_manage` 的 input schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file,不含 view

#### Scenario: skill_manage create 支持受控写入范围
- **WHEN** 消费者查看 `skill_manage` 的 input schema
- **THEN** create action 支持可选 `scope: "agent" | "pa"`,默认 `"agent"`

#### Scenario: skill_manage create 写入 PA root
- **GIVEN** 当前产品启用了 PA 产品级 skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="pa", ...)`
- **THEN** 新 skill 写入 PA 产品级 skill root,而不是当前 agent workspace skill root

#### Scenario: PA root 不可用时不回退
- **GIVEN** 当前产品未启用 PA 产品级 skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="pa", ...)`
- **THEN** 工具返回 `success=false`,不写入 agent root

### Requirement: Skill 生命周期状态影响可见集合与自动优化

Skill 使用统计中的生命周期状态影响候选集合;创建动作确定 Skill 来源,读取动作不得把当前会话的创建来源误套到既有 Skill;自动创建的 Skill 在使用越线后可触发 per-skill batch review。

#### Scenario: stale skill 仍可发现和读取
- **GIVEN** skill A 的 usage state 为 stale
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 仍在候选中,并可通过 `skill_view(name="A")` 读取;读取成功后恢复为 active

#### Scenario: archived skill 退出日常候选
- **GIVEN** skill A 的 usage state 为 archived,且目录已移动到 `.archive/`
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 默认不出现在候选中,`skill_view(name="A")` 按找不到处理

#### Scenario: 自动 Skill Review 创建记录自动来源
- **GIVEN** 消费者启用了 Skill 自动 Review
- **WHEN** 后台 Review 通过 `skill_manage(create)` 成功创建 Skill
- **THEN** 新 Skill 的使用记录来源为自动创建 `F3`
- **AND** 仅 memory Review、普通 fork 或普通用户创建不虚构该自动来源

#### Scenario: 查看无记录的既有 Skill 不推断为自动创建
- **GIVEN** 一个既有手工或遗留 Skill 尚无使用记录
- **WHEN** 自动 Skill Review 通过 `skill_view` 成功读取它
- **THEN** 首次使用记录沿用非自动来源 `F1`,不因当前 Review 可创建自动 Skill 而记为 `F3`

#### Scenario: 查看已有自动来源的 Skill 保留来源
- **GIVEN** Skill A 的使用记录来源已经是 `F3` 或 `F4`
- **WHEN** 任意会话通过 `skill_view` 成功读取 Skill A
- **THEN** 读取只更新使用统计,不覆盖已有来源

#### Scenario: 自动 skill 使用计数越线后触发 batch
- **GIVEN** 自动创建的 skill A 在一次成功 `skill_view` 后达到自动优化阈值
- **WHEN** 该 `skill_view` 调用完成
- **THEN** 内核 enqueue skill A 的 per-skill batch review,不等待周期性 curator 扫描

#### Scenario: 手工 skill 越线不自动 batch
- **GIVEN** skill A 来源为用户创建、历史会话蒸馏、manual 或 unknown
- **WHEN** 一次成功 `skill_view` 让它达到同一使用阈值
- **THEN** 内核不 enqueue 自动 batch review

### Requirement: 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致

`build_kernel()` 的消费者可提供有序的工作区 Skill 目录布局以及有序的共享 Skill roots。对同一 `(workspace_root, skills)` 配置，`assemble_prompt_preview`、`list_skills(workspace_root)`、真实 session turn 注入的 `<available_skills>`，以及该 session 的 `skill_view`，必须从同一有序 root sequence 解析同一集合和同一同名覆盖结果。工作区 roots 先于共享 roots；同名 Skill 采用最先命中的 root，且返回实际命中的 `location`。未声明扩展工作区布局的 consumer 保持其既有单个 workspace config Skill 目录行为。

#### Scenario: 多个有序工作区目录在各读取路径中一致
- **GIVEN** 某 SDK consumer 为一个 workspace 声明多个有序的工作区 Skill 目录，且这些目录与共享 roots 中存在独有或同名 Skill
- **WHEN** 消费者查询 `list_skills`、组装同一 skills 配置的 prompt preview、执行一轮 session 并调用 `skill_view`
- **THEN** 四条路径发现相同的 Skill names 和实际 `location`
- **AND** 同名 Skill 均采用有序 root sequence 中最先命中的版本

#### Scenario: 预览与运行时技能一致
- **GIVEN** `build_kernel()` 装配的 Kernel 为某 workspace 声明 Skill root layout，某 session 的 `skills` 含若干可发现的 Skill names
- **WHEN** 取 `assemble_prompt_preview(skill_ids=…, workspace_root=…)` 展示的技能，与该 session 真实执行一轮后 LLM 请求中 `<available_skills>` 列出的技能
- **THEN** 两者为同一集合（同名 + 同路径），不会出现预览齐全而运行时使用另一组 roots 的情形

#### Scenario: 未提供额外 workspace Skill layout 时保持既有单目录默认
- **GIVEN** 经 `build_kernel()` 未传入新的 `workspace_skill_dirnames`
- **WHEN** 取 preview、`list_skills` 或运行时注入的技能
- **THEN** 三者只从有效 `workspace_config_dirname` 派生一个 workspace Skill root，再叠加消费者显式传入的共享 roots
- **AND** 连 `workspace_config_dirname` 也省略时，保持 SDK 当前使用 `.nano` 的默认，不因本 unit 改变外部 consumer 行为

#### Scenario: list_skills 返回项携带 SKILL.md 路径
- **WHEN** 消费者调用 `list_skills(workspace_root)`
- **THEN** 返回的每个 `SkillInfo` 携带实际命中 Skill 的 `location`（该技能 SKILL.md 路径，可空），消费者据此区分当次解析来源

### Requirement: Skill 管理写入不因兼容读取 root 改变目标目录

消费者为 session 声明多个只读兼容 Skill roots 时，`skill_manage` 的 agent scope 仍只写入该消费者声明的原生 agent Skill root；兼容 roots 参与候选和 `skill_view` 读取，不成为 agent scope 的写入目标。

#### Scenario: 管理工具从兼容 root 读取但写入原生 root
- **GIVEN** 某 session 可从兼容工作区或共享 root 发现一个 Skill，且消费者声明了原生 agent Skill root
- **WHEN** agent 读取该 Skill 后以 agent scope 创建另一个 Skill
- **THEN** 读取返回兼容 Skill 的实际 location
- **AND** 新 Skill 写入原生 agent Skill root，不修改兼容目录中的已有文件

### Requirement: SDK 消费者可在没有真实 workspace 时只查询共享 Skill roots

当 SDK consumer 尚未拥有一个将实际执行 session 的 Workspace（例如准备创建 Agent 时），它可请求只从其声明的共享全局 roots 发现 Skill，而不以 build-time repo root 或任意占位路径派生 workspace roots。已拥有真实 Workspace 的 session/list/preview 继续使用完整有序 layout。

#### Scenario: prospective Agent capability 不把 repo workspace Skill 当候选
- **GIVEN** 某 consumer 的 build-time repo root 含 workspace Skill，但待创建 Agent 尚无 canonical workspace
- **WHEN** consumer 查询仅用于创建表单的共享 Skill candidates
- **THEN** 返回项只来自消费者声明的共享全局 roots
- **AND** repo root 下的 workspace Skill 不作为可选择的 prospective Agent Skill 返回

### Requirement: 经 agent 工具新建的子会话继承父会话 skills 配置

经 `agent` 工具新建子 agent 时，子会话的 `skills` 配置与父会话相同（`None` 表示未收窄、非空为白名单、空序列为零可见 skill），不得比父会话更宽。`agent` 工具不再接受单独的 skill 列表参数来加宽或覆盖。

#### Scenario: 子会话 skills 与父会话一致且不更宽
- **GIVEN** 父会话 `skills` 为某一配置（未收窄 / 白名单 / 空）
- **WHEN** 消费者经 `agent` 新建子 agent（不传已删除的 skill 列表字段）
- **THEN** 子会话面向模型可见的 skill 集合与父会话在同一 workspace 解析口径下一致，且不出现父不可见而子可见的 skill
