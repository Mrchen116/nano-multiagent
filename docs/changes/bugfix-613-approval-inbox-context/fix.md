# bugfix-613: 审核上下文去重并明确 Inbox 来源

## Relations

- Related: feat-552
- Related: refactor-581

## 原始报告与已确认范围

用户报告 Mac mini Personal Agent 编辑面试记录时审核上下文超限，追问“审核输入比主agent自己的输入还大？？”；讨论 CC 和 DSH 原生审核后确认：“我觉得和cc一样，但是把inbox接受信息当作特殊函数”，并授权“在最新远端代码开始改”。

用户已确认：安全规则、AGENTS.md 指令区、投影后的历史与最后的待审动作；Inbox 结果保留系统提供的身份、聊天和回复关系，send_message 保留真实投递结果；移除完整 source 与运行快照重复内容，不使用笼统 role: fact。保留审核模型、两阶段判定、恢复与委派权限边界。发送前估算完整审核输入，超限走既有审核不可用分流，不裁掉用户授权或待审参数、不绕过审核。

本次单一 M1-fix 修改 Nano 审核投影和请求组装，不改 DSH 依赖、主 Agent 上下文、生产配置或部署。主仓 dirty 内容保持原样；按用户要求在最新 origin/main 的隔离 worktree 建档和实施。

## 现象 / 复现

2026-10-15 生产只读取证：主 Agent 最近输入 151638 tokens，两个编辑审核输入分别为 277114、278132，超过配置的 258400 窗口。上游返回完成及 allow，DSH 适配器根据 usage 将其标记为 CONTEXT_WINDOW_EXCEEDED，Nano 因无有效判定阻止写入。缩短编辑内容没有缓解历史膨胀。

审核 transcript 中 6 份 runtime-context snapshot 同时包含正文与 source.sections 的相同内容，尤其重复已加载 Skills。回归应在带多份大快照的会话中检查最终审核请求，确认保留完整待审编辑、有效指令及来源，却不再携带快照正文及元数据副本。

## 根因

8a608c771e9a911fcf4fac5987944806941825b3 在原生运行时迁移时直接序列化原生消息 source。runtime-context 的 source 本身含正文副本，普通 user 分支又早于 instructions 判断，造成重复。旧 Python transcript 只序列化选择后的正文。原始 feat-552 的目的是保留用户授权来源、短确认、委派和恢复边界，而不是把运行时元数据原样发给审核。

现有 approval.test.ts 保护来源、审核路由和恢复，却没有带 runtime-context/Skill 快照的长上下文输入；工具结果统一 host_context 也没有明确表示 Inbox 与真实消息投递的区别。

必须保住：真实用户与其他来源不可混淆；成功投递和 accepted/held/unknown 不混淆；恢复的 Inbox 不提升为本进程新授权；子 Agent 不获得新的人工审批通道；未知来源不能自行声明人类身份；原有明确工具限制和本人私聊免审边界继续生效。

## 修复

实施中。

## 验证

扩展现有审核投影保护；通过原生 DSH 子进程捕获最终审核请求验证接线。窄回归稳定后执行本地 CI 和独立代码审查。测试与最终版本证据在完成时回填。
