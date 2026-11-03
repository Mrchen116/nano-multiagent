# M1-create implementation and evidence

## 实施范围

- Web 和 PA 共用 owner-scoped 节点目录及配置创建准备；既有 ConfigOperations 继续持有 apply、commit、恢复。
- pa_agent_creations 只关联 binding/request key 到宿主 operation id，不复制 apply 状态机；目标 node_id 经 target_node_id 与 PA 传输身份分离。
- 主 PA 固定 agent_creation 入口，options/create/status；随包 nano-agent-creation 按需加载，明确交办并对齐选项后提交。普通工具审批和根 PA 身份限制继续生效。
- 传输无法判断是否已受理时返回 unknown（不同于已接受配置操作的 pending），两者均指导查询原 request_key。属已设计的未确认结果细化，不扩大恢复或授权范围。

## 测试策略与既有保护

- 新建 IM personal-agent-creation.test.ts：该产品语义此前没有 owner；保护独立长期创建、真实目录、跨自有节点、主人/观察来源、offline、key冲突及精确 operation 恢复。首次5项全部以 unsupported_personal_operation 失败，接入后通过。
- control/configuration-edits/approval-configuration/catalog-reads 原覆盖 keep：共享提取继续由其保护 Web 创建、候选和回执语义。
- 扩展现有 personal-assistant.test.ts：保护目标与传输身份分离、child/非PA拒绝和传输unknown。
- 扩展现有 native personal-security.test.ts：保留 ordinary/PA catalog 对照，新增真实 DSH + HTTP stub 捕获；模型响应为受控机制fixture，不充作真实模型能力证据。

## 已执行结果（实施工作树，随后由代码提交锁定版本）

- narrow IM/PA/configuration/catalog: 72 tests passed。
- native PA/context + PA host + contract selection: 50 tests passed。
- pnpm build、pnpm typecheck passed（后续最终版本再核一次增量）。
- 原生 HTTP fixture 共4次模型请求：首次只有 Skill摘要；下一次含实际 Skill正文；后续含 options 与 created 结果；所有请求 tools 和 system 的序列化值保持相同。没有真实 provider cache 命中率声明。
- daily 真栈位于本 worktree：.e2e-daily.json；正常主人聊天“只是讨论，不要创建”得到澄清建议，Agent总数保持4。真实模型为模板 PA Astra/medium、Codex审批，Auto开启，未跳过权限。

## 待完成

真实创建旅程、独立产品验收、代码审查/一致性验证、完整CI、契约归并与PR。所有运行数据、日志和原请求留本机，不提交。

## 独立审查修复

- 静态审查在 6a588bde1 确认：首次创建在 per-Agent 队列等待时，源 PA 被停用后仍能提交。接受此 finding，在共享 createAgent 的队列及目录等待之后、首次 operation insert 之前加入同步 admission callback，复核当前 binding、原执行代次和主人来源；已接受 operation 仍按原回执恢复。新增排队期间 disabled/binding/source 变化回归。
- 自检真实模型的讨论/选项/创建全程主 session: 0b464064-b456-4264-b49d-c6cc1de5d625；主人确认消息 bd1d5916b6804ee0b1e080efe4583cf3，真实返回 english-speaking-703，Agent列表从4变5，聊天 c_wt9hukyw 的首任务未自动发送。模型 Astra/medium，Codex Auto审核。该自检先于异步权限修复；最终版本另由独立产品 reviewer 验收。
- 完整后端：210 files / 1121 tests passed（.feat703-backend-tests.log）。Python129 passed /28 deselected；ruff check、format、typecheck通过。上述结果适用于未变部分，权限修复另跑窄回归。
