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

按已对齐的 CC 风格投影实现：独立 agent_instructions、工具名 JSONL、最后一个完整动作；Inbox 使用 inbox_result + observation，send_message 使用实际结果状态。移除 runtime-context/Skill 和 source 正文副本，保留已加载指令的原生基线/更新语义；相同指令正文保留最后出现顺序，避免文件 A→B→A 时误应用 B。没有重新读盘或解析上游指令正文。

保留单聊天已交付提议；全局私稿不进入审核。通过 DSH 公开 PTC 事件补全可见 root 的内部调用与结果，并按 turn/step 绑定，避免重用 ID 或压缩后把旧 Inbox 复活。既有持久委派条目在读取时去掉旧快照和完整来源，恢复后 Inbox 降为背景。

用已声明的 DSH token-meter/estimate 和 llm.resolveModelInfo 检查完整请求与输出预留；它是启发式估算，供应商实际错误仍按原流程处理。未新增分词器、依赖补丁、模型切换或历史裁剪。

## 验证

- Red：新投影回归 4 项在修改前均失败，分别暴露快照重复、Inbox/投递缺失、来源格式与 PTC 结果缺失。
- 测试归属：将 approval.test.ts 原来源测试 rewrite-merge 到 approval-sources.test.ts，扩展同一投影风险；原审核路由/本人免审/委派边界测试 keep，只适配最后动作的格式。
- 原生子进程：通过真实锁定 DSH 加载 AGENTS.md、产生动态长 runtime snapshot、读取两次 Inbox、发送提议并执行受审动作，捕获最终审核请求。独立小窗口 reviewer 在提交前被阻断且无副作用；LLM fixture 只证明组装、路由和执行接线，不声称真实模型判定准确率。
- 完整检查、独立 review 与最终基线在交付时回填。
