# 迁移设计意图核对（2026-10-10）

范围：迁移基线 `4915c44cb`、原 change 的理由/约束、refactor-581 已确认的取舍，以及当前接入实现。按用户要求做有界源码核对、修复和测试环境加载；统一产品验收仍留到反馈批次结束。下表“保留”表示找到对应机制和回归落点，不表示重新完成真实平台验收。

## 本次发现与处理

1. **Memory 快照遗漏**：[feat-385 决策 2—5](../../feat-385-system-prompt-runtime-and-memory/design.md) 要求首次使用才读取、会话内冻结、压缩后刷新、关闭时零读取。此前接入每次 assembly 都读磁盘。现在每个 Agent 用弱引用持有快照，原生 fork 继承父快照，压缩完成后重新读取；关闭的历史分支在读取前退出。运行时重启重新读取，沿用原挥发性快照边界。
2. **反思触发口径偏差**：[feat-349 决策 2/6](../../feat-349-self-evolving-skills-memory/design.md) 以模型迭代和主会话轮次计数。此前按每个 `tool/call` 累加，并行工具会放大计数，纯文本模型轮次又会漏计。现在从原生 ownEvents 的 `step/start` / `turn/start` 取得读数，不把 fork 的继承历史算成新执行。新计数键隔离旧“工具个数”读数，避免单位改变后长期不触发。
3. **失败反思误消耗周期**：此前 child 启动就推进重置点。现在仅 `completed` 后推进；失败/取消保留待反思差额。F4 使用批次的“已接收”标记仍保持独立原语义。
4. **前台维护重置点未落实**：原设计要求主 Agent 成功调用 `memory` / `skill_manage` 后重置对应计数。旧基线 `self_improvement.py` 也未完整实现，不把它描述成迁移独有回归。本次从原生成功工具结果恢复重置点，失败不重置，两种维护互不抵消，包含该调用所在的当前主轮。

实现只涉及 Nano Feature/knowledge consumer，使用原生事件和公开生命周期；无 DSH 内置代码、依赖补丁或私有接口修改。

## 其他有明确理由的约束

路径简称：I=`packages/dsh-integration`，P=`packages/personal-assistant`；测试均在对应包 `tests/`。本表记录当前源码与已有测试的匹配，本次没有把这些历史测试结果重新包装成新验收。

| 原约束 / 理由来源 | 当前机制与核对落点 | 处置 |
|---|---|---|
| feat-349：后台复用父请求前缀，降低反思成本；声明不能代替执行授权 | I `knowledge/runtime.ts` 的父 system/tools 快照、原生 fork、`tools.guard`；`llm-attribution.test.ts` 实际 pi-ai wire 与禁止写文件 | 前一轮已修复；本次回归保留 |
| bugfix-422：父子请求在 Inspector 同组，同时保留执行归因 | I `llm-attribution.ts` 分别发送产品根和原生 child ID；并发根隔离 | 前一轮已修复；本次 wire 回归保留 |
| bugfix-429 / feat-349：child 继承实际模型，review 输出预算独立 | I `model-policy.ts` route 继承、保留 native child maxTokens；`knowledge.test.ts` 检查 8192 | 保留 |
| feat-349：review 不递归触发、前台结束不等待 side-chain、关闭 Feature 取消对应维护 | 仅产品 binding 的 completed turn 入队；active 按 root/kind；subscribe disposal / stop；`knowledge.test.ts` | 保留 |
| feat-349：只报告实际写入，不把读/list/失败说成更新；维护成功也不泄漏 child 正文 | I `changed` 只在写提交后记录事实；P `knowledge.ts` 等 review 结束、按真实 fact 发结构化 notice；对应 `knowledge.test.ts`；原 bugfix-525 | 保留 |
| feat-349：workspace 隔离、受控 Memory/Skill 修改、来源稳定、原子更新 | I `knowledge/files.ts` 路径约束、锁/rename、限额、创建来源和调用身份去重；`knowledge.test.ts` | 保留 |
| K01—K05：选中名单统一作用于发现、加载、命令和 preview；显式空不能扩大 | I `capabilities.ts` 单一 scoped provider、显式 allowlist、关闭默认 roots；`capabilities.test.ts`、`knowledge.test.ts` | 保留 |
| K06：自动新增 Skill 不破坏已有前缀；压缩后恢复已使用技能 | DSH tool-skill 在 `agent/pre-step` 追加完整 replacement catalog，不重写历史；I `knowledge/runtime.ts` 从使用记录经当前允许的 registry 重新注入正文 | 采用 capability-plugin-map K06 已允许的 append-only 接入；不另造发现器 |
| K09：前台结束后仍完成 Skill 自动启用、真实归属与通知重试 | P `knowledge.ts` 独立调和持久事实，核对 root/owner，版本化 enable，receipt 后 ack；`knowledge.test.ts` | 保留 |
| feat-541：只有可用性失败切备用；粘性只属当前会话；公开输出后不切；配置变化重置 | I `model-fallback.ts` 分类/持久 run/revision/等待 idle/发布检查；`model-policy.ts` session selection；I/P `model-fallback.test.ts` | 保留 |
| bugfix-580 / PR #326：任务删除只在统一工具权限层判断授权，执行链不重复索要当轮真人消息或固定口令 | 本轮用户指出后补核，原审计漏项。TS IM 删除正则和 PA 当轮来源 gate 同步移除，保留身份/可选来源真实性/子树/revision/幂等；真实 native approval、WS 和 service 回归覆盖 | 已补迁；这不是需要保留的旧框架约束 |
| 权限来源不能因换核被提升；专用 reviewer 不能失败后偷换模型 | I `policy/approval.ts` 先尊重原生 deny，再单一 consumer；`sources.ts` 区分 live Inbox/human/parent 与历史/工具事实；`approval.test.ts` | 保留 |
| Feature 撤销、显式空工具集和历史配置不能从父模板重新扩大权限 | I `agent-config.ts` 立即收窄后等待 idle 应用；`capabilities.ts` 空集关闭 PTC transport，child 不加 global 固定项；`capabilities.test.ts`、`history.test.ts` | 保留 |
| Inbox 真正进入模型上下文才可消费；图片不能只凭 descriptor 算读完 | P `inbox.ts` 冻结分页、准确片段、持久工具结果校验、事务 cursor；`inbox.test.ts` | 保留 |
| feat-544：群内新更正应挡住旧草稿，发送检查与接受边界不能隔 await | P `global-agent.ts` publication gate 紧接同步准备与发送状态；`single-thread.ts` 保留 withheld 草稿并注入复核；Inbox blocking 只看同目标注意消息 | 保留，真实群旅程待统一验收 |
| bugfix-535：并发结束路径不能重复发，平台回执前不能报成功 | P `external.ts` 同一 output 的 dispatch promise + 持久 confirmed/unknown；unknown 不自动重发；`external.test.ts` 包含延迟回执与重启 | 保留 |
| Heartbeat 忙时跳过、活跃时段、错过周期不积压；不把低优先级唤醒排在人类之后 | P `heartbeat.ts` durable pending identity、`onlyIfIdle`、消耗 due；`heartbeat.test.ts` | 保留；不同于已确认的 Cron 补发 |
| Workflow 逻辑 child 与尝试分离、重启先清理旧执行、共享预算和完成前缀可复用 | I `workflow/` engine/control/state/budget，原生 child/JS 执行；`workflow-control.test.ts`、`workflow-lifecycle.test.ts`、`workflow-budget.test.ts` | 保留 |
| Workflow 原会话审批、父前台结束后结果仍可达；不能先 ack 再投递 | I `policy/approval.ts` workflowParent；P `workflows.ts` durable acceptance 后 checkpoint；`workflow-approval.test.ts`、P `workflows.test.ts` | 保留 |
| 新历史 fork 保留消息锚点、压缩前缀和当时配置，分支互不污染 | I 历史控制接原生 fork；`history.test.ts` 含冷恢复；旧聊天转换明确排除 | 保留新格式契约 |
| 搜索后端/代理不能因换核被偷偷换服务；扩展全局/工作区分层仍在 | I `web.ts` DDG/Brave/SearXNG 与失败直报，公开 extract consumer；`extensions.ts` / `agent-config.ts` 分层 mount；`web.test.ts`、`runtime-profile.test.ts` | 保留；协议实际前缀由 wire 回归覆盖 |
| 统计要区分未缓存输入、缓存输入和当前上下文；缺失不能伪造为零 | P `presentation.ts` 合并不重叠 buckets，只有已知 pi-ai 缺省零规则才补零，按 turn 投影；已有 presentation/store 测试 | 保留 |

已确认的产品变化继续遵守 [pending-decisions](../pending-decisions.md)：原生工具名/schema/截断续读、标准插件格式、Cron 主会话投递与过期一次性补发、JS Workflow、新历史格式。后台普通 jobs 跨 runtime 仅依据仍存在的持久结果对账，不承诺恢复任意 JS 栈或不存在的持久 mailbox。

## 本次验证

- `pnpm --filter @nano/dsh-integration build` 通过。
- `knowledge-policy.test.ts` 3 项：真实文件快照/关闭零读取/继承与压缩边界；并行工具计数与成功维护重置；真实 DSH child 首次失败后再次触发、成功后不提前触发。
- `knowledge.test.ts` 4 项：受控实际写入、使用统计/归档、native Memory/Skill/F4 review 与关闭/重启，以及可信显式 Skill 调用。
- `llm-attribution.test.ts` 1 项：实际 pi-ai HTTP 传输、双 root/fork 前缀、身份和执行白名单。
- 以上共 8 项分两次定向执行通过；未重复运行全套、浏览器旅程、真实 LLM 缓存命中实验或生产部署。

加载：确认无活动前台轮和 running review 后，仅重启现有隔离 Node；PID 47268 / DSH 47273，ready=true；IM PID 18390 未重启，health=ok。现有数据和配置保留。
