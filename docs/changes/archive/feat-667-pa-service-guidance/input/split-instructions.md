# 拆分 PR #414 的实施指令

请先读取同目录 `PR414-审查与拆分建议.md`。该审查固定于 head 66b49e4e0fa6be17a87466ef04fa2cbf1d4007f7 / base 85910853ebe4a7a22c5b761029cf46da2f78cd5a。若当前 HEAD 变化，先核对差异，不能把旧发现直接当新版本结论。

本次不合并原大 PR，不再扩展其范围。保留原分支、已有证据、未提交工作和用户配置；从当前确认过的 main 新建隔离分支，按审查建议逐片拆取。不要 force reset、覆盖用户更改、复制整个大型分支再靠 Feature 关闭假装已拆分。

现在先做 A：通用 PA 默认指导 + 持续工作 Skill + 轻量主动准备。
用户面对一个 PA；长事项复用原内部执行者，简单事直接处理；观察到的重要变化可在既有授权范围内核对和私人准备；已经办完不再催、没有新价值保持安静；不把观察到的承诺当外发授权。复用现有 Inbox、Task、Heartbeat、schedule、Memory、真实发送与披露规则。不要要求用户多管理流程。

本片不引入 records.json、新记忆 schema/迁移/全局 forget fence、personal_context、personal_attention 数据库及完整回执协议、文件发布新服务或新的通用调度器。相应修改 Prompt/Skills，不能引用本片不存在的工具/字段；nano-ongoing-work 内的 bind_execution/clear_execution、nano-proactive-care 内的 query_receipt_id/attention_id、nano-personal-memory 内的 v2 接口都须移除或保持原接口语义。

单独检查 A 所依赖的原生子 Agent 能力。PR #414 的 personal-delegations.ts 固定白名单会禁止执行者加载 Skills、开下级和运行命令，不可原样提取。如果当前 main 的真实能力不足，不得宣称已经完成完整委派闭环；把最小必要运行时修复放进 B 的独立变更，保留细粒度隐私/权限边界，不直接放开全部工具和私人历史。

先按既有 change 流程落实 A，不额外增加新流程。设计阶段明确：改哪些文件、复用哪些现有入口、哪些能力本片不承诺。只在真实改变用户决策或遇到不可自行解决的问题时询问，不对已明确范围反复索取批准。

适用验收必须使用真实 Agent/模型输入与工具回执：小事不机械派工；不同事项不串上下文；更正交回原执行者；实际能力允许的二级委派/Skill 消费；等待时主 PA 仍可回复；观察到承诺可做准备但不越权发送；已处理不再提醒；原自定义提示/禁用设置保持。未支持的关键行为明确标为 blocker/后续 B，不以提示写了就算完成。不能用新增工具数量或大量单测代替用户结果。

交付 A 的独立 diff、实际验证、未运行项和可回退说明，并列出 B（持续执行可靠性）、C（领域 Skills）、D（文件交付）的最小后续范围；不要在当前分支顺便实现这些。

旧 memory v2 与 personal_context 暂停，不作为 B/C/D 的依赖。若已在任何 workspace 执行过 records 迁移，先备份并说明数据兼容性；不要删除 records 或让旧代码在短投影上继续写。此次授权是开发拆分，不是部署或修改生产用户数据。
