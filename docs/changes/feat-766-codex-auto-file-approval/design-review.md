# Design review

## Round 1

- Reviewer target `/root/design_review`
- Review mode `full`。首次独立 Gate 2，覆盖文件审批、子会话恢复、Gateway delta 和 milestone。
- Started at `2026-11-13T16:48:38+08:00`
- Completed at `2026-11-13T16:53:37+08:00`
- Duration `4m59s`
- Verdict **Issues Found**（1 CRITICAL / 3 WARNING）

### Coverage

- **产品组装与职责。** Gateway 以受信 Agent 配置启动 RuntimeSupervisor，DSH integration 安装 Nano 审批并从执行作用域读取配置。现有 `tools/pre-execute` 已先取得下游决策，适合在原生允许且审批开启后、构造模型请求前增加 Codex 放行。这样可复用现有审计、拒绝计数和工具硬限制，保留 CC 和其他工具已有入口。DSH 的公开 `agent/created` 生命周期带 `source`，支持在恢复后的首次模型调用前处理审批配置。Nano 的现有历史配置选择和 DSH 委派来源足够承载变更，无需独立审批链或数据迁移。[Gateway 初始化](../../../apps/node/src/main.ts#L163) · [产品组装](../../../packages/dsh-integration/src/index.ts#L269) · [审批调用链](../../../packages/dsh-integration/src/policy/approval.ts#L118)
- **Agent Context 设计模式。** 免审动作由执行层直接作决策，无需改变执行 Agent 的工具说明或任务输入。恢复后需要模型审批的动作继续交付原始待审工具参数、cwd、已持久化的委派证据和当前适用的配置。`NanoApproval.attach` 只在满足初次记录条件时写委派证据，恢复读取有跨进程来源降级，不能把旧背景变成 live 授权。`ReviewSession` 指纹包含配置和审核模型，更新后可重建相应上下文。已发人工审批继续用原请求 ID，现有 RuntimeClient 测试覆盖更新等待和拒绝迟答。应复用此回归，并在恢复 fixture 捕获受控模型实际接收的规则、模型标识和原委派来源。[委派证据](../../../packages/dsh-integration/src/policy/approval.ts#L53) · [Codex 审核计划](../../../packages/dsh-integration/src/policy/codex.ts#L31) · [审核指纹](../../../packages/dsh-integration/src/policy/review-session.ts#L63) · [进行中审批回归](../../../packages/dsh-integration/tests/approval.test.ts#L116)
- **Milestone 与验收方法。** 单个 milestone 涵盖共享审批与恢复链路，范围无并行冲突。隔离 DSH 进程、受控模型出站捕获、审计记录及文件副作用足以判断确定性分流。模型调用数可以直接验证免审效果，隔离 fixture 时间不能代替生产延迟。沿用现有设置及 Work 入口，无需原型。没有一次性迁移。运行与行为验收留在实施阶段，本轮核对基线 `a82e5e85f` 的组装、契约、锁定的 DSH `0.2.1-alpha.1` 路径语义和验证方案。

### Issues

#### R1-C1 · CRITICAL · Codex 放行所核对的路径必须和原生工具实际目标一致

[设计第 5 行](design.md#L5) 指向既有普通文件检查及新文件祖先解析。当前辅助函数先以 `path.resolve` 折叠父目录段，再调用 `fs/promises.realpath`。锁定 DSH 的 `dsh-fs-local/lib/index.js` 中，`localDisplayPath` 在 POSIX 保留物理父目录遍历，`resolveLocalTarget` 使用 `realpath.native`。路径中遇到符号链接再返回上级时，审批候选可能显示为 cwd 内文件，原生工具却命中范围外目标。本机只读对照也确认普通 Node realpath 保留 `aGeNtS.mD` 的传入大小写，而 native realpath 返回受保护文件名 `AGENTS.md`。现有根比较还缺少 `/tmp` 与 `/private/tmp` 这组别名的统一处理，本机的 `tmpdir()` 另指向 `/var/folders/…`，所以生产样本的直接 `/private/tmp` 路径不能靠现有 cwd 检查覆盖。

请在 Codex 设计中明确使用与原生执行一致的真实路径及根别名处理。无法确认的物理遍历交回审核。隔离 fixture 覆盖两种临时路径拼写、带父目录段的符号链接以及适用卷上的受保护名称大小写别名，同时保留原 CC 行为。[现有路径判断](https://github.com/Mrchen116/nano-multiagent/blob/a82e5e85f3626d981307626bf6d3cb8ceb3b7b58/packages/dsh-integration/src/policy/cc-workspace.ts#L5)

#### R1-W1 · WARNING · 自定义环境事实需要保留 Codex 审核

[设计第 5 行](design.md#L5) 沿用既有自定义规则条件，但 CC 快速路径只检查 `allow`、`softDeny`、`hardDeny`。Codex 把 `environment` 一并交给审核模型，用来判断目标是否为生产、共享或敏感位置。只配置了这类事实时，直接复用 CC 条件会绕过审批所需事实。请明确 Codex 的自定义配置条件包含非默认 `environment`，并以只有该字段的配置覆盖原有审核链路。[CC 条件](https://github.com/Mrchen116/nano-multiagent/blob/a82e5e85f3626d981307626bf6d3cb8ceb3b7b58/packages/dsh-integration/src/policy/cc-workspace.ts#L33) · [Codex 规则组装](../../../packages/dsh-integration/src/policy/codex-context.ts#L30)

#### R1-W2 · WARNING · 恢复审批需要覆盖历史配置选择的所有分支

[设计第 9 行](design.md#L9) 只明确了已有有效覆盖和首次创建。当前 `NativeHistory.configuration` 在覆盖缺失或 revision 失配、父会话已加载时，仍沿父级配置并写回覆盖。常规配置更新可能改变 revision，历史分支的父级执行配置也可能来自快照。仅在有效覆盖分支叠加当前审批会让这些恢复路径继续以父级历史审批为准。设计与 delta 也需要用同一条件指明普通子会话，以及与 seeded fork、Workflow child 的边界。请说明通过公开 `source === 'resume'` 与子会话角色识别受影响恢复，在现有历史配置选择之后从有效 owner 模板应用审批，原委派证据继续由既有路径读取。验证至少覆盖同一 revision 的冷启切换，以及失配覆盖恢复后审核使用 owner 规则与模型，并复用进行中审批测试。[历史覆盖和父级回退](../../../packages/dsh-integration/src/history.ts#L103) · [恢复组装](../../../packages/dsh-integration/src/index.ts#L316) · [角色判断](../../../packages/dsh-integration/src/child-role.ts#L44)

#### R1-W3 · WARNING · MODIFIED delta 缺完整 canonical 条目

[delta 第 20 行](specs/gateway/agent-capabilities.md#L20) 以散文描述追加位置，缺少可替换的同名 Requirement 及既有场景。按规范投影修改后的完整条目并保留原有进行中请求、子 Agent 委派及其他场景。运维文档在实施时也须修正当前“每个 child 保留委派时的有效 Auto 配置”的范围描述。[delta 规则](../../specs/CONTRIBUTING.md#L128) · [现有 Gateway 条目](../../specs/gateway/agent-capabilities.md#L523) · [运维说明](../../operations/auto-permissions.md#L15)

### Author Resolutions

- C1 accepted. Design now matches native path case identity, preserves both temp spellings and sends parent traversal to review.
- W1 accepted. Non-default environment requires review, as do custom rule lists.
- W2 accepted. Approval replaces the selected execution copy after history selection for resumed continuable children, including fallback. Existing idle-update path preserves in-flight execution.
- W3 accepted. Delta now includes the complete Requirement. Operational documentation will align during canonical merge.

## Round 2

- Reviewer target `/root/design_review`
- Review mode `closure`。修订集中在 R1 的路径解析、自定义配置、恢复条件及 delta 格式，其他基线结论沿用 R1。
- Started at `2026-11-13T16:55:12+08:00`
- Completed at `2026-11-13T16:55:43+08:00`
- Duration `31s`
- Verdict **Approved**（0 CRITICAL / 0 WARNING）

### 历史问题闭环

- **R1-C1 closed。** Author 接受按原生目标判断的修订。Codex 对带父目录段的路径保留模型判断，用 native realpath 解析已存在目标和最近存在的祖先，并同时覆盖系统临时目录的原始与真实拼写。设计明确悬空链接和特殊文件仍经审批，CC 保留自己的路径入口。Milestone 以两种临时路径拼写、范围外拒绝及原生文件结果取证。[文件审批与验证](design.md#L3)
- **R1-W1 closed。** Author 将非默认 `environment` 纳入需由模型判断的配置。修订后的设计保留 Codex 审核器原本收到的环境事实。[文件审批](design.md#L5)
- **R1-W2 closed。** Author 将当前 owner 的完整审批配置应用于原历史选择之后的执行副本，明示覆盖有效、缺失及失配分支。修订范围限于 DSH 恢复的 continuable 子会话。锁定 DSH 在恢复完成前执行公开 `agent/created` hook，子会话描述符包含持久的 continuable / one-shot 区分。当前 native 审批边界、既有 idle 更新和原委派来源继续有各自所有者。验收设计通过同一子会话的双向切换、实际审核模型及原始授权输入判断配置及 Context。[恢复与验证](design.md#L7) · [生产组装](../../../packages/dsh-integration/src/index.ts#L316) · [现有 continuable 区分](../../../packages/dsh-integration/src/owned-sessions.ts#L81)
- **R1-W3 closed。** Author 改为完整同名 Requirement。与 canonical 逐行比较，只增加恢复行为一条，原场景完整保留。现有运维说明的对应修订已在 milestone 范围及 Author Resolution 中记录。[Gateway delta](specs/gateway/agent-capabilities.md#L20) · [当前 Gateway 契约](../../specs/gateway/agent-capabilities.md#L523)

本轮核准设计。原生路径、版本失配恢复、自定义环境和进行中审批的运行证据由实施阶段验证。
