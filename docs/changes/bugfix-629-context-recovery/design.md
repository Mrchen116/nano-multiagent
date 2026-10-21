# bugfix-629: 上下文导航与当前 turn 恢复

## Changelog

## 现状分析

### 涉及范围

- Nano 生产 `be6c1271b`；当前主线 `45d87e671` 在生产基础上仅增加 feat-628 与本事故文档，相关实现一致。
- 独立插件仓 `Mrchen116/dsh-agent-context`，基线 `621278d`（实现 `7f0a2b78`）、固定包 `0.3.0-rc.1`。改动 `src/index.ts`、`checkpoint.ts`、`history.ts`、`tools.ts`、提示词及相应测试；Nano 更新固定包与 lock。
- Nano `knowledge/runtime.ts` 从 `.usage.json` 的 session references 恢复已用 Skill；`model-policy.test.ts` 覆盖压缩与重启，现断言自动全文恢复，需要替换为可按需恢复的行为断言。
- 不修改客户端面，不产生前端原型。

### 既有约束

只经 DSH 已声明公开 exports、Cordis hooks 与 Session API 工作；不修改、fork、patch 或 private-import DSH。固定 `0.2.1-alpha.1`。无 LLM 摘要、无普通对话 tail、无 Notes 正文自动注入，不制造新的授权或第二套任务数据库。保留完整工具配对、原始日志、业务白名单和 workspace 生命周期。

### 可复用能力

- **用** `systemPrompt.context` 的完整快照语义：它适合低频有效环境，不承担每步引用目录。
- **改** 插件引用：`get_context_remaining` 已支持当前引用及分页；fallback 已附 bounded 引用，无需新增每步通知服务。
- **改** History：已有规范化事件、来源保真、off-surface 读取、分页、长结果偏移；加原生 turn 定位，复用同一工具。
- **用** `turn/start` / `turn/end` 的原生日志边界生成恢复导航，不推断自然语言任务完成，不另存任务状态。
- **改** Skill 恢复：现有 references 与 `skills.get` 已受当前 scope/selection 约束；只给名称、位置与按需读取指引，不自动注入正文。
- **不用** 更大 buffer、第二次摘要或丢弃旧笔记作为修复；压力阈值及换窗时机保持。

### 相关历史

feat-627 的 Notes/History 和默认启用契约保留。其 R1 算错汇总与本故障不混同；原13窗验收是有用证据但不覆盖本次压力组合。独立原始调查见 incident 所引本地报告；不提交私人请求或日志。固定 Codex 参考的差异更新只用于解释设计失配，不移植其 runtime 或声称线上行为一致。

## 架构总览

之前：每步引用变化 → 整份 runtime snapshot 追加 → 已用 Skill 全文重复 → 默认 buffer 被跨过 → 全窗移出 → 仅旧 Notes 指引。

之后：窗口身份只随边界变化；引用通过已有查询/保存前提示按需提供。Skill 只恢复导航。整窗移出仍由同一 compaction owner 执行，同时 checkpoint 给出当前未结束原生 turn 的精确 History 入口；Agent 据原始输入和交付证据判断继续什么。

## 关键决策

1. **移除高频动态引用和 Notes 目录贡献，不实现另一套 context diff。** `agent-context:references` 改为仅窗口身份贡献（可重命名为 identity）；不再在每次 assemble 调用 `notes.hint()` 或拼 `referenceText()`。完整引用仍由 `get_context_remaining` 查询及 fallback 提示提供。Notes 目录只在换窗 checkpoint 展示。正常工具调用、写 Notes、读取 Skill 均不改变插件的环境 contribution。DSH 自身因真正环境变化追加快照的语义保持。

2. **已用 Skill 恢复为可发现的位置索引。** 只在成功压缩后的会话提供当前仍可用的 Skill 名称与实际路径，说明正文需用 `skill` 按需重读。持续保留索引而非“assemble 后立即删掉”的一次性标记，避免下次 assemble 因 context 消失再次制造快照。对默认无摘要和显式回退统一使用该恢复规则；当前已加载的正文仍在普通历史，权限/目录选择仍由 native skills 决定。修改现有“自动全文还在”的测试，以确实能重读正文且无无请求的重复全文替代。

3. **用不可歧义的原生 turn 边界定位已读任务，不做语义任务提取。** HistoryItem 增加 `turn_id: string | null`，值为该事件所属 `turn/start.seq` 的字符串，限定当前执行 session；不能用容易混淆父子 session 的全局 turn number。`history list_items/search` 增加 `turn_id` 精确过滤，跨多个 window 仍属于同一 turn。窗口/item/source/工具调用结果语义保持。不存在的 turn 返回空页，非法类型仍按工具 schema 校验；所有读仍只针对归档项。

4. **每次重置都明确当前执行边界及恢复入口。** `perform` 在提交前从原生日志计算未结束 turn；若该 turn 有即将移出的普通记录，checkpoint 加 body-free `<interrupted_turn>`，包含 turn_id、记录范围/数量、第一条与最近若干条记录的 window/item/role/tool/source-kind 定位，以及可直接调用的 `history list_items` 参数。全部导航有固定大小上限，完整项可分页取得。提示明确：换窗不是任务完成；旧 Notes 可能早于该 turn 的直接输入或 Inbox 结果，继续或结束前必须恢复此 turn 的原始输入与已发生的交付。读完后按真实状态工作，不能因为有未结束 turn 就重复发送已经完成的结果。无未结束 turn 的人工压缩不虚构待办；本 step 尚未持久化的 claimed 输入仍沿原有路径保留。

5. **不增加任务完成分类器或工具拦截状态机。** 当前缺陷是恢复入口缺失，框架不应根据任意 Note 文案猜测任务状态。恢复导航是控制元数据，模型必须通过实际 History 调用取得内容，最终是否恢复以真实请求和交付检验；脚本预定的最终答案不算验收。若真栈发现该导航不足以让任务恢复，作为本单元的实际缺陷回到设计收口，不能用fixture预设成功遮盖。

6. **当前环境重建保持原有公开事务。** checkpoint 仍带有效 runtime context，并过滤插件窗口身份 contribution；随后 native projection 可补充新窗口快照。这一边界上有限的环境重建不随普通步骤增长。测试区分重建边界的固定成本与每步增长，不能只比较最终 token 数。无为减少这次边界成本而伪造 native runtime-context 消息或修改 DSH projection。

## 接口与数据流

- `normalizedItems(session)` 扫描原生事件时跟踪当前 `turn/start.seq`，`turn/end` 后清空；每个用户/助手/tool 项携带该 turn_id。来源保持原字段，含 Inbox 的结果仍是 tool，未知/系统来源不升级为用户。
- `searchHistory(session, {turn_id, ...existing})` 先在当前 session 的归档项内筛选，再沿现有稳定 cursor 分页。`read` 仍使用 window/item，长结果仍用 offset。
- `interruptedTurn(session, shadowedSeqs)` 只在当前 open turn 与本次 shadowed 项有交集时生成恢复描述；metadata 中的 item refs 来源于 normalizedItems。多次换窗查询同一 turn_id 可以跨窗定位；新请求的 seq 不被旧 Notes 隐去。checkpoint 持久化恢复描述，因此节点重启不会丢掉已写入的入口。
- 控制提示先列当前 turn 恢复入口，再列旧 Notes 路径，明确二者不是同一时刻的状态。重启后沿已持久化 checkpoint 恢复；不改旧 Note，不把恢复内容重标为新的 `nano-human`。
- `get_context_remaining` 返回的 references 保持现 schema，供保存笔记前获取新提交 item ID。调整 guidance 中“下一份 snapshot 自动出现”措辞，明确按需查询；提示词 golden 同步并在本单元记录相对原 Codex 适配的原因。
- 插件发布新的不可变 prerelease `0.3.0-rc.2`，Nano dependency/lock 精确指向带校验的 tgz。发布安装包与生产部署分开；不发布新的 Nano 安装 release。

## 契约层增量 (delta-spec)

- `docs/specs/gateway/agent-capabilities.md`：补充强制换窗时旧 Notes/新已读任务组合及按需恢复 Skill 的场景；见 `specs/gateway/agent-capabilities.md`。其余 package 无行为增量。

## 风险与回退

Skill 全文不再自动重放，必须验证 Agent 真正会按需读取正确 Skill，并保留禁用、fork 与显式回退约束。导航只是定位，不是已恢复正文或已完成任务的证据。大工具结果仍可能越过保存区间，因此必须在该情况也通过原始历史恢复；不承诺永不压力换窗。控制信息有界且不保留对话尾部。若更新不健康，可用现有 workspace 开关恢复摘要引擎或回退固定包，保存 Notes/History；不清空生产状态。

## Runbook for Reviewer

**Review 驱动方式**：不改客户端面；端到端真栈，使用 Web IM 实际调用的注册/登录、Agent 配置、聊天与消息 API；不可用私有 `session.submit` 替代产品入口。检查落库消息、原生会话与实际 provider 请求，以确认新输入确实在恢复后重新入模和结果真正投递。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | `./scripts/e2e-down.sh --wt "$WT"` | 在最终 unit checkout `pnpm install --frozen-lockfile && pnpm build`，然后 `./scripts/e2e-up.sh --wt "$WT"` | `$WT/.e2e-ports.env` 中实际端口的 `/health`、测试 owner 登录、Node connected、真实消息完成 |

`WT=/Users/czj/.codex/worktrees/bugfix-629-context-recovery/nano-multiagent`。仅使用此 worktree 产生的端口、config、workspace、identity 和数据库。外部模型使用仓库默认隔离 E2E config 的既有 provider；启动前检查 provider URL 可用。凭据不写文档。测试 owner 只存在于隔离实例，不使用生产身份或外部聊天。

验收前置由实施者准备并在派发时提供具体 API 地址、测试 owner 登录方式、合成日记 workspace、Agent/conversation IDs、最终包 hash 和请求日志目录。默认预算 C=258,400、O=32,768、B=16,384、R=6,144，无提高 buffer。合成日记/只读 fixture 提供足够大的实际工具结果，使已有新 Inbox 请求在未保存新 Notes 前跨过硬阈值；不向模型塞预定答案。若实际模型输出未触发目标路径，判未覆盖，调整 fixture 规模，不能宣称通过。

必验矩阵：

1. **主故障 PA**：先完成旧事项并保存“已完成” Notes；新消息要求读取合成日记并列 todo，实际 Inbox read 后、未保存新 Notes 前强制换窗；检查 History 真实恢复最新输入与日记事实，结果完整且只投递一次。请求/原生事件证明压力触发、恢复及最终交付。
2. **导航成本**：使用七个合成 Skill（总正文至少52,400字符）后经历换窗；普通工具与 Notes 操作不少于六步。统计请求中各 Skill sentinel 次数和 runtime snapshot 贡献，证明没有每步追加未变化 Skill/Memory 正文；确实需要的 Skill 可通过原生入口重新读取。
3. **直接输入及多窗**：普通 Agent 的当前 turn 强制/主动换窗并用 turn_id 跨窗读原始直接输入与工具结果；至少两个有内容窗口。通过原生 integration + 真模型结果覆盖，不能仅断言 tool 名存在。
4. **恢复与边界**：隔离 Node 正常重启后 checkpoint/History 可读；显式 off/on 继续工作；既有来源、tool pairing、会话隔离、Auto off/空业务 allowlist 保留。复用未变路径的有效证据，变化的 Skill 和 turn filtering 需新测试。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-recovery | 消除重复上下文并恢复强制换窗任务 | 无 | 单主线 | 插件 index/history/tools/checkpoint/guidance/tests；Nano knowledge/runtime、相关测试、固定包 lock、契约与运行指导 | [worker] 旧版真实 request fixture 先红；默认预算强制/overflow、已有Inbox任务、turn过滤、长内容分页、来源/配对/隔离及Skill按需读取通过；包构建与完整CI通过。[reviewer] 上述真栈矩阵证明当前请求恢复、正确交付、无重复副作用与无每步全文膨胀。 |
