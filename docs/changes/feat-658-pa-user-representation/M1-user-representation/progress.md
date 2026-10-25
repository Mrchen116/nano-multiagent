# M1 实施与验证记录

## 实施基线与职责

- 2026-10-25：用户授权按已讨论的真实场景方案实施并交付。基线 `origin/main` / `8e4054197`，Gate 2 Round 4 Approved、0 CRITICAL / 0 WARNING；从受审基线至此只有文档变化，不使代码 grounding 失效。
- 专属 checkout：`.worktrees/unit-feat-658`，分支 `unit/feat-658`；主 checkout 保持原状。
- 主 Agent：IM/PA 代表发送事务、原始证据/relay/历史传递、集成与最终交付。
- 首轮独立切片：ComposeMessage 和双端消息/输入框体验；运行时发送工具与上下文/审核适配。共享文件分工明确；后续门禁发现由主 Agent 修复。

## 用户确认的真实验收方法

此处细化 design 既有 runbook 的实施方法，不改变接口、需求范围、M1 或既有门禁；设计结论 retained。

1. **真实委托 → 真执行 → 联系 PA**：daily 栈中 Q 实际准备测试 Git 报告；主人只用自然语言在 PA 私聊委托回复，禁止提示工具名或人工伪造来源。PA 读取上下文、代表发送；Q 经正常审核提交推送隔离仓库而不合并/部署、不重复索权。之后主人要求直接联系 PA，Q 用来源 ID 定位且真实发到正确 PA。核心旅程三次独立自然表述，至少一次含已有聊天历史；保存首次结果/重复确认次数/失败原因，不能挑成功样例。
2. **普通 Agent/PA 起草 → 编辑采用 → 手动发送**：只自然要求草稿，不提示动作名。编辑后采用须只填指定目标输入框，无消息/模型运行；手动发送后接收者收到最终文字并遵守修改后的范围。Web/iOS 各实际一次，涵盖取消/替换已有草稿、无权限保留编辑；ToAssistant 另行提交本会话请求。
3. **已有任务恢复与子 Agent**：同一任务先完成一个步骤，经产品支持路径恢复节点/会话，再读取原消息、交给子 Agent完成剩余步骤；原范围/PA ID保持，已完成步骤不重做，用户后续暂停时收敛。
4. 边界对照：自身报告仍为 Agent；PA 非成员不能用普通发送但真实委托可代表主人；普通 Agent 自称批准/超范围动作不获额外许可。

证据同时记录用户可见结果、实际模型 context/工具参数/审核材料、消息和接收者 ID/Git commit+ref/真实运行副作用。模型 context 覆盖普通/PA/SingleThread、恢复/子 Agent和两种审核输入；接口手工调用只承担低层边界检查，不能替代自然模型旅程。所有验收使用隔离 daily、测试身份和测试仓库，不使用生产聊天或真实项目。

## 测试策略与进展

- 实施中按最低有效 seam 扩展已有 personal-disclosure/personal-sources/personal-assistant、Inbox/source-provenance、interactive 和客户端测试，优先合并/改写旧 reply_draft 路径覆盖；具体命令与结果随实际执行追加。
- 当前：开始实施，尚无功能通过或产品验收结论。


## 服务端与编排实施（2026-10-25）

- 已新增有意义的失败复现：owner 发送仍是 Agent 作者、self 发送放过非成员；实现后 identity/event/authorization/idempotency 两项通过。
- frozen payload 写明 self/owner，服务端 prepare 与 commit 核验所选作者当前权限；owner provenance 在 card record / message.created 之前入库，原生用户 relay 排除实际 PA。
- 用户身份与卡片 executor 分离；退出会话使卡片不可用并使许可失效，重新加入仍须重新审核。对应三项 representation 场景通过。
- Inbox、历史、SingleThread input 保存 pa_agent_id；代表消息不进入主人授权/guard，也不触发 slash 控制命令。旧 reply_draft 参数明确拒绝，新旧数据库历史不回填。
- 服务端/PA 首轮 57 文件 414 测试中 411 通过，三个失败为已变更成员资格 fixture 与迁移 fixture 缺列；相关 fixture 修正后 personal-agent 17 项通过，迁移/PA/Inbox/control 合计 33 项通过。无需因此重复无关测试。
- 新迁移 CLI 支持 dry-run/apply/verify，后者对照停流量前的数据库副本校验消息、旧操作、事件、relay 与草稿记录完整不变；自动化覆盖重复执行、旧列 NULL 和修改历史后 verify 失败。
- 真实模型/真实 Web、iOS 连续旅程尚未执行；上述测试不替代 V1–V4 产品证据。


### 真实旅程 A 首次失败（保留）

- daily node `wt-unit-feat-658-74505`，主人 Web 原话消息 `630493e593d94f30bb970a1ef7625d4c`；审核 operation `11aa962a-1a0b-4bb3-906c-085fa41ac234` allow，代发消息 `1a1c4efc89b2466aa0603b7eebbd84c3` 确认为用户作者与实际 PA 来源。
- 失败点：正文仅“Q，请…”；relay 的 mentioned_agent_ids 为空，mention_only 的 Q 未被唤醒。不能将“已发送”计作端到端成功。
- 修复：在两个工具共享的 target/text schema 中明确先查实际成员 user_id、按现有正式 mention 语法点名。没有更改群注意力策略或审核门禁；本地完整证据 `/Users/czj/.codex/reports/feat658-acceptance/journey-a-first-attempt.md`。
