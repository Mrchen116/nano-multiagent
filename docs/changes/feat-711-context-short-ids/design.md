# feat-711: 短引用与简洁预算 — 技术方案

> 对齐 spec.md。实施前设计。参考调查 output/context-codex-dsh-comparison.md；本设计取代其中完整 UUID/callId 与超硬线仍保证保存一步的建议。

## Changelog

- 2026-11-05 (M1): 真实模型验收发现 DSH 会在 pre-step 后、待接纳用户记录前写入 skill-catalog / agent-instructions，误计它们会使用户首次 id1 重建为3。两类原生控制与 runtime-context / compact-checkpoint / agent-context 一起排除短编号及自身 History；宿主 createHistoryView 保持原 seq 视图。补原生控制延后提交、实际 Skill/AGENTS 注入的首次编号与重启恢复回归。

- 2026-11-05 (M1): Task 原文回执同样需要规范化：TaskContextDriver 向产品提交消费证据时剥离插件自有标记，使正文严格匹配原业务输入；模型请求和持久记录仍保留短标记。覆盖停启恢复及已消费去重。
- 2026-11-05 (M1): 实际审批回归证明有效工具 JSON 的尾部标记会改变结构化证据类型；插件公开 stripContextItemId，Nano policy/sources 在拼接供结构化读取的正文时剥离仅插件自有标记。原文形似标记的 block 不删除；metadata 随日志保留，但 adapter 只发送 text。

## 现状分析

### 涉及范围

插件基线 dsh-agent-context 00f6196 / rc.7；Nano 基线 edc84dc。插件 src/index.ts 的 pre-step 管理换窗，src/history.ts 用事件序号寻址；预算工具展开全部计算参数。Nano packages/dsh-integration 固定 GitHub release 包。当前 gateway 能力契约见 docs/specs/gateway/agent-capabilities.md 的无摘要换窗条目。

### 既有约束

只用 DSH 0.2.1-alpha.1 公共 exports，不 fork/patch。原始记录及来源保留；宿主 Memory source_history 的序号引用契约不变。主仓未跟踪内容不纳入提交。

### 可复用能力

- 用 freezeMessage 改写新输入副本，在原 pre-step 返回前入库；不修改 frozen request。
- 用原生 tool/result 单节点 surface replacement 给最终工具结果补标记，保留 message.id、错误和元数据，引用被替换 seq。该机制用于原生裁剪，允许只改 content。每次替换必须同步相邻追加 compaction/prune 影子计价事件，shadowedTokenCount 使用 tokenMeter.estimateMessage(当前投影消息)，随后原生 replacement；此公共协议支持 signed delta，新增标记也须计价。
- 用原始事件日志重建短编号，无自定义持久事件、旁路索引文件或进程内唯一状态。
- 保留原生 pruner、换窗事务、预算硬线和溢出处理。

### 相关历史

feat-627 采用按需引用，bugfix-629 防止动态快照自增长。新方案不改变 systemPrompt.context 的稳定窗口身份，不改 Nano Skill 恢复。

## 架构总览与关键决策

1. **会话内短整数由日志确定。** 依原事件顺序，为 History 已收录的 user/assistant/tool 消息的首次 message.id 分配 1、2、3…；同 message.id 的裁剪/补标记副本复用编号。assistant 仍可被 History 列出与恢复，但正文不加标记，因此可见编号允许有间隔。候选新 user 按 decision.messages 顺序接在已提交编号后；取消前未提交的输入不保留号码。重启、换窗和 fork 由完整继承日志重建，不依赖压缩后的 surface，也不截取 UUID。
2. **首次模型可见之前附加。** 在同一个 pre-step 中，完成下游 decision 后先将待采纳 user 标记，再以最终被返回的批次测量预算；控制来源 runtime-context/compact-checkpoint/agent-context/skill-catalog/agent-instructions 排除；后二者会在 pre-step 之后、待采纳 user 之前提交，不能占用短编号。已有工具结果在原生压力裁剪后、返回模型前补标记；采用公开 tool/result replacement，覆盖正常、错误、取消和恢复产生的结果。若执行了换窗，被移出 surface 的工具无须再次标记；新输入仍需标记。工具最终格式化发生在前一 step，故无 post-execute 的分支覆盖问题。
3. **只追加一个专用 text block。** 标记为 `\n[id: N]`。已有活动副本包含相同末尾专用 block 时不重复写；History 只剥离自身可识别的末尾标记，不对正文做全局正则替换。写入/剥离必须覆盖正文中原有 `[id:]`、多 text block、Unicode 和重复接纳。
4. **恢复原文并隐藏物理副本。** 自身 history 的 item_id 改为短编号；按 message.id 合并物理副本，read 始终读取最早原记录并剥离其标记。只补标记不使原文变成可归档项：若当前副本去标记后的正文与原文相同，视为仍活动；真实裁剪移出的完整正文可恢复，换窗后整项可恢复。列表不重复显示补标记/裁剪副本；seq 保留用于排序、方向游标与原窗口归属。
5. **保留宿主 API。** createHistoryView 默认继续返回 seq item_id，供 source_history 及记忆证据使用，不混入自身恢复短编号；共享正文归一化但显式选择编号模式。Nano policy/sources 消费有效结构化正文、TaskContextDriver 提交严格原文消费回执前使用插件公开的 stripContextItemId；Nano 的 source_history/证据编号不变；memory-source-view.safeBoundary 必须跳过合法 tool/result surface replace（不是新的调用完成），继续处理后续 step，真正无对应调用的 append 结果仍阻断。旧 Notes 的 seq 引用不提供兼容，保留原文件；旧日志仍可经新 list/search 取得短编号。
6. **预算工具默认只给 tokens_left 和 estimated。** tokens_left=现有工作余量或 null；保留内部 budget() 用于引擎，不返回 references/T/W/H/C/O/B/R 等，不保留 references_cursor。普通模型 text 使用简短估算句，结构化值为 `{tokens_left, estimated:true}`。提示词只依赖就地标记与当前窗口身份。
7. **容量策略不扩展。** 保留当前提醒距离的窗口约束、W/H 区间、硬线与 overflow，不承诺超硬线必给保存一步。此次不改 reminderTokens 默认值，避免将模型专用 6144 无条件扩成跨模型策略。

## 接口与 Context 生命周期

Consumer 为所有开启插件的 Agent。宿主生成 UUID 是内部身份，LLM 只看短整数。例：user `[id: 1]`，assistant 工具调用项 2（无正文标记），tool `[id: 3]`；Notes 保存当前 window 与 1/3；裁剪、重启、换窗后自身 history.read 用相同编号回原文。工具错误状态、source 与授权不变。控制提示、窗口导航和 Notes 路径沿用现状。

预算返回从整包诊断 JSON 改为 `Approximately N tokens left in this context window.`，未知时明确 unavailable。普通 guidance/reminder/fallback 移除 references 查询要求，改为普通 user/tool 内容末尾短标记；不虚称所有 developer/system 消息均有标记。空 references checkpoint 删除。Codex 数值也含客户端估算，不声称其全部服务端精确计数或服务端未公开的 ID 算法。

## 契约层增量 (delta-spec)

- gateway agent-capabilities.md：specs/gateway/agent-capabilities.md；归档 feat-627 文档保持历史，新适配差异记在本 unit。

## 风险与回退

逐消息标记少量 token 必须进入最终 pre-step 测量；工具补标记增加的 token 经相邻影子计价协议及重新测量计入，并核对重放后的 meter.measure 结果一致。以原始 message.id 去重保证重建稳定；物理补标记替换不能污染用户/助手配对、History 原文和分页。禁用后保留日志但不再追加标记；回滚到 rc.7 不删除数据。实际 API 与原始内容变动须覆盖审批来源回归。

## 一次性部署迁移

无生产迁移、清空数据或生产重启。插件发新不可变版本后更新 Nano 固定 URL/integrity；不得覆盖旧 release。包发布是实施交付的依赖安装步骤，生产部署需另行授权。

## Runbook for Reviewer

无新增常驻服务。插件测试使用隔离 home/会话；Nano E2E 依 docs/development/worktree-runtime.md 起停 daily 环境。Review 驱动方式：不改客户端，使用客户端同一接口提交连续任务、观察结果并经现有原生轨迹检查工具返回。前置：本机已配置 LLM 入口；先 scripts/dev_host.py check 核对，无可用真实模型时报告缺口，不用 stub 冒充自主恢复。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-short-ids | 短引用与恢复闭环 | 无 | 串行 | 插件 src/tests/README 与固定包；Nano 依赖、policy/sources 结构化证据正文、TaskContextDriver 消费回执、memory-source-view.safeBoundary、必要集成测试及本 unit | [worker] 先取得首次入模/短 ID/工具失败/裁剪重复项/Unicode 续读/重启/换窗的失败证据，再通过窄测试、build/typecheck；createHistoryView 序号与预算简洁返回回归；safeBoundary 对替换后后续完成步骤继续推进而真实未配对 append 仍阻断；标记 signed token delta 与重放一致；最终实际模型请求有短标记且快照不随步数增长。[reviewer] 长任务在裁剪、换窗与重启后按最新要求正确交付，预算工具结果简洁，既有访问边界保留。 |
